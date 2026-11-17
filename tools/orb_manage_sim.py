"""Amelioration de la strategie ORB : gestion de position teste sur donnees reelles.

Variantes testees (bar-level, donnees M15 reelles 2016-2026) :
- baseline     : cible 2R, max 2 trades/jour, fresh-cross (config actuelle)
- be075        : stop a breakeven des +0.75R flottant
- be100        : stop a breakeven des +1.0R flottant
- partial1r    : 50% ferme a 1R, reste a BE, cible 2R
- timestop13   : sortie forcee 13:00 NY si position ouverte (flux vendeur l'apres-midi)
- timestop_be  : timestop 13:00 + breakeven 0.75R

Sortie : out_orb_manage/ + graphiques PNG (test visuel).
"""
import importlib.util
import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out_orb_manage"
OUT.mkdir(exist_ok=True)

spec = importlib.util.spec_from_file_location("orb_oos", ROOT / "tools" / "orb_both_oos.py")
mod = importlib.util.module_from_spec(spec)
sys.stdout = io.StringIO()
spec.loader.exec_module(mod)
sys.stdout = sys.__stdout__

ACCOUNT = mod.ACCOUNT
TICK_VALUE = mod.TICK_VALUE
MIN_LOT = mod.MIN_LOT
MAX_LOT = mod.MAX_LOT


def normalize_lots(lots):
    lots = max(MIN_LOT, min(MAX_LOT, round(lots / 0.01) * 0.01))
    return round(lots, 2)


def simulate_manage(bars, risk, cost, target_r, max_trades,
                    be_r=None, partial_r=None, partial_frac=0.5,
                    time_stop_min=None, eod_bars_back=1,
                    rank_max=None, stop_buffer_frac=0.0,
                    require_break_close=False,
                    req_or_dir=False, req_prev_dir=False):
    """Sim bar-level avec gestion : breakeven, partial TP, time stop,
    filtre OR-rank (percentile de la taille du range sur 20 jours),
    buffer de stop au-dela de l'extreme du range."""
    balance = ACCOUNT
    peak = balance
    max_dd = 0.0
    rows = []
    or_sizes = []  # tailles du range des jours precedents (pour le rank)
    for ny_date, g in bars.groupby("ny_date", sort=True):
        if ny_date < mod.PERIODS[0][1] or ny_date > mod.PERIODS[-1][2]:
            continue
        day = g[(g["ny_min"] >= 570) & (g["ny_min"] < 960)].sort_values("time")
        day = day.reset_index(drop=True)
        if len(day) < 3:
            continue
        opening = day.iloc[0]
        if int(opening["ny_min"]) != 570:
            continue
        or_high = float(opening["high"])
        or_low = float(opening["low"])
        if not np.isfinite(or_high) or not np.isfinite(or_low) or or_high <= or_low:
            continue
        or_close_pos = (float(opening["close"]) - or_low) / (or_high - or_low)
        trend = float(opening["trend_daily"])
        long_setup = np.isfinite(trend) and trend <= mod.LONG_TREND_MAX and or_close_pos >= mod.LONG_OR_MIN
        short_setup = np.isfinite(trend) and trend >= mod.SHORT_TREND_MIN and or_close_pos <= mod.SHORT_OR_MAX
        if rank_max is not None:
            window = or_sizes[-20:]
            if len(window) >= 10:
                rank = sum(1 for s in window if s < or_high - or_low) / len(window)
                if rank >= rank_max:
                    or_sizes.append(or_high - or_low)
                    continue
        or_sizes.append(or_high - or_low)
        or_range = or_high - or_low
        if stop_buffer_frac > 0.0:
            long_stop_level = or_low - stop_buffer_frac * or_range
            short_stop_level = or_high + stop_buffer_frac * or_range
        else:
            long_stop_level = or_low
            short_stop_level = or_high
        if not long_setup and not short_setup:
            continue

        def ny_min_of(k):
            return int(day.iloc[k]["ny_min"])

        trades_today = 0
        pos = None
        cooldown = 0
        last_high = None
        last_low = None
        j = 1
        while j < len(day):
            row = day.iloc[j]
            high = float(row["high"])
            low = float(row["low"])
            mom6 = float(row["prev_mom6"])

            if pos is not None:
                exit_price = None
                reason = None
                frac_out = 1.0
                moved_stop = pos["stop"]

                # time stop
                if time_stop_min is not None and ny_min_of(j) >= time_stop_min:
                    exit_price = float(row["close"])
                    reason = "tstop"
                if exit_price is None:
                    # verif SL (stop courant, apres eventuel BE)
                    if pos["side"] == 1 and low <= moved_stop:
                        exit_price, reason = moved_stop, "stop"
                    elif pos["side"] == -1 and high >= moved_stop:
                        exit_price, reason = moved_stop, "stop"
                    elif pos["side"] == 1 and high >= pos["target"]:
                        exit_price, reason = pos["target"], "target"
                    elif pos["side"] == -1 and low <= pos["target"]:
                        exit_price, reason = pos["target"], "target"

                # TP partiel : atteinte du niveau partial_r -> on ferme une fraction
                if exit_price is None and not pos.get("partial_done") and partial_r is not None:
                    p_level = pos["entry"] + pos["side"] * partial_r * pos["stop_dist"]
                    if (pos["side"] == 1 and high >= p_level) or \
                       (pos["side"] == -1 and low <= p_level):
                        exit_price, reason = p_level, "partial"

                if exit_price is None:
                    # mise a jour breakeven intra-barre (fin de barre)
                    if be_r is not None:
                        be_level = pos["entry"] + pos["side"] * be_r * pos["stop_dist"]
                        if pos["side"] == 1 and high >= be_level:
                            pos["stop"] = max(pos["stop"], pos["entry"])
                        elif pos["side"] == -1 and low <= be_level:
                            pos["stop"] = min(pos["stop"], pos["entry"])
                    j += 1
                    continue

                entry = pos["entry"]
                stop_dist = pos["stop_dist"]
                gross = pos["side"] * (exit_price - entry)
                # ajustement si BE : le stop est deja au BE -> PnL stop ~ 0 - cost
                net = gross - cost
                r_mult = net / stop_dist if stop_dist > 0 else 0.0
                if reason == "partial":
                    frac_out = partial_frac
                else:
                    frac_out = 1.0
                risk_money = balance * risk
                lots = normalize_lots(risk_money / (stop_dist * TICK_VALUE))
                pnl = net * lots * frac_out * TICK_VALUE
                balance += pnl
                peak = max(peak, balance)
                max_dd = max(max_dd, 1.0 - balance / peak)

                if reason == "partial":
                    # reste de la position : stop a BE, cible finale
                    pos["stop"] = pos["entry"]
                    pos["r_multiple_base"] = 0.0
                    pos["partial_done"] = True
                    pos["pnl_partial"] = pnl
                    pos["entry_j"] = j
                    j += 1
                    continue

                rows.append({
                    "date": ny_date, "entry_time": day.iloc[pos["entry_j"]]["time"],
                    "exit_time": day.iloc[j]["time"],
                    "side": "long" if pos["side"] == 1 else "short",
                    "entry": entry, "exit": exit_price, "reason": reason,
                    "net_points": net, "r_multiple": r_mult, "lots": lots,
                    "pnl": pnl + (pos.get("pnl_partial", 0.0) if reason != "partial" else 0.0)
                           if reason != "partial" else pnl,
                    "balance": balance, "trade_no": trades_today,
                })
                trades_today += 1
                pos = None
                cooldown = 1
                last_high = high
                last_low = low
                j += 1
                continue

            # gestion du cooldown pour re-entree
            if cooldown > 0:
                cooldown -= 1
                last_high = high
                last_low = low
                j += 1
                continue

            if trades_today < max_trades:
                prev_high = last_high
                prev_low = last_low
                broke_up = np.isfinite(mom6) and mom6 >= mod.LONG_MOM_MIN and high >= or_high and (
                    prev_high is None or prev_high < or_high)
                broke_down = np.isfinite(mom6) and mom6 <= mod.SHORT_MOM_MAX and low <= or_low and (
                    prev_low is None or prev_low > or_low)
                if long_setup and broke_up:
                    if require_break_close:
                        # confirmation = bougie de breakout haussiere ; l'entree
                        # reelle se fait a sa CLOTURE (pas d'ouverture -> sans lookahead)
                        if float(row["close"]) < float(row["open"]):
                            last_high = high
                            last_low = low
                            j += 1
                            continue
                        entry = float(row["close"])
                    else:
                        if req_or_dir:
                            ob = day.iloc[0]
                            if float(ob["close"]) < float(ob["open"]):
                                last_high = high
                                last_low = low
                                j += 1
                                continue
                        if req_prev_dir:
                            pb = day.iloc[j - 1]
                            if float(pb["close"]) < float(pb["open"]):
                                last_high = high
                                last_low = low
                                j += 1
                                continue
                        entry = max(float(row["open"]), or_high)
                    pos = {"side": 1, "entry": entry, "stop": long_stop_level,
                           "stop_dist": entry - long_stop_level,
                           "target": entry + target_r * (entry - long_stop_level),
                           "entry_j": j}
                elif short_setup and broke_down:
                    if require_break_close:
                        if float(row["close"]) > float(row["open"]):
                            last_high = high
                            last_low = low
                            j += 1
                            continue
                        entry = float(row["close"])
                    else:
                        if req_or_dir:
                            ob = day.iloc[0]
                            if float(ob["close"]) > float(ob["open"]):
                                last_high = high
                                last_low = low
                                j += 1
                                continue
                        if req_prev_dir:
                            pb = day.iloc[j - 1]
                            if float(pb["close"]) > float(pb["open"]):
                                last_high = high
                                last_low = low
                                j += 1
                                continue
                        entry = min(float(row["open"]), or_low)
                    pos = {"side": -1, "entry": entry, "stop": short_stop_level,
                           "stop_dist": short_stop_level - entry,
                           "target": entry - target_r * (short_stop_level - entry),
                           "entry_j": j}

            last_high = high
            last_low = low
            j += 1

        # position encore ouverte a la cloture -> EOD
        if pos is not None:
            idx = max(pos["entry_j"], len(day) - 1 - eod_bars_back)
            exit_price = float(day.iloc[idx]["close"])
            entry = pos["entry"]
            stop_dist = pos["stop_dist"]
            gross = pos["side"] * (exit_price - entry)
            net = gross - cost
            r_mult = net / stop_dist if stop_dist > 0 else 0.0
            risk_money = balance * risk
            lots = normalize_lots(risk_money / (stop_dist * TICK_VALUE))
            pnl = net * lots * TICK_VALUE + pos.get("pnl_partial", 0.0)
            balance += pnl
            peak = max(peak, balance)
            max_dd = max(max_dd, 1.0 - balance / peak)
            rows.append({
                "date": ny_date, "entry_time": day.iloc[pos["entry_j"]]["time"],
                "exit_time": day.iloc[idx]["time"],
                "side": "long" if pos["side"] == 1 else "short",
                "entry": entry, "exit": exit_price, "reason": "eod",
                "net_points": net, "r_multiple": r_mult, "lots": lots,
                "pnl": pnl, "balance": balance, "trade_no": trades_today,
            })
    return pd.DataFrame(rows), max_dd


def metrics(trades, risk, start, end):
    d = trades[(trades["date"] >= start) & (trades["date"] <= end)]
    if d.empty:
        return None
    r = d["r_multiple"].to_numpy(float)
    bal, peak, dd = ACCOUNT, ACCOUNT, 0.0
    for v in r:
        bal *= 1.0 + risk * v
        peak = max(peak, bal)
        dd = max(dd, 1.0 - bal / peak)
    wins = r[r > 0]
    losses = r[r <= 0]
    pf = wins.sum() / abs(losses.sum()) if len(losses) and losses.sum() != 0 else float("inf")
    return {
        "trades": len(d), "winrate": (r > 0).mean() * 100,
        "avg_r": r.mean(), "pf": pf,
        "return_pct": (bal / ACCOUNT - 1) * 100, "max_dd_pct": dd * 100,
        "per_day_usd": (bal - ACCOUNT) / max((end - start).days, 1),
    }


bars = mod.load_bars([
    "data_live/nas100_m15_kaggle_utc.parquet",
    "data_live/nas100_m15.parquet",
])

RISK, COST = 0.005, 1.7
OOS = mod.PERIODS[1]      # 2022-01-01 -> 2025-09-20
RECENT = mod.PERIODS[2]   # 2025-09-21 -> 2026-09-15
FULL = mod.PERIODS[-1]

VARIANTS = {
    "baseline":   dict(target_r=2.0, max_trades=2),
    "be075":      dict(target_r=2.0, max_trades=2, be_r=0.75),
    "be100":      dict(target_r=2.0, max_trades=2, be_r=1.0),
    "partial1r":  dict(target_r=2.0, max_trades=2, partial_r=1.0),
    "tstop1300":  dict(target_r=2.0, max_trades=2, time_stop_min=780),
    "tstop_be":   dict(target_r=2.0, max_trades=2, time_stop_min=780, be_r=0.75),
    "tstop1500_be": dict(target_r=2.0, max_trades=2, time_stop_min=900, be_r=0.75),
}

rows = []
trades_by_variant = {}
for name, kw in VARIANTS.items():
    tr, _ = simulate_manage(bars, RISK, COST, **kw)
    trades_by_variant[name] = tr
    m_oos = metrics(tr, RISK, OOS[1], OOS[2])
    m_rec = metrics(tr, RISK, RECENT[1], RECENT[2])
    m_full = metrics(tr, RISK, FULL[1], FULL[2])
    rows.append({
        "variante": name,
        "oos_ret": round(m_oos["return_pct"], 2), "oos_dd": round(m_oos["max_dd_pct"], 2),
        "oos_wr": round(m_oos["winrate"], 1), "oos_pf": round(m_oos["pf"], 2),
        "oos_usd_day": round(m_oos["per_day_usd"], 2),
        "recent_ret": round(m_rec["return_pct"], 2), "recent_dd": round(m_rec["max_dd_pct"], 2),
        "recent_wr": round(m_rec["winrate"], 1),
        "full_ret": round(m_full["return_pct"], 2), "full_dd": round(m_full["max_dd_pct"], 2),
    })
    tr.to_csv(OUT / f"trades_{name}.csv", index=False)

df = pd.DataFrame(rows).sort_values("oos_ret", ascending=False)
df.to_csv(OUT / "manage_summary.csv", index=False)
print(df.to_string(index=False))
