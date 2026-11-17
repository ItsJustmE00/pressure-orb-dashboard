"""Simulation agressive ORB : cible 1R + re-entrees multiples par jour.

Re-entree : apres un stop-out (ou un target), on re-entre quand le prix
recroise le niveau du range avec le filtre momentum, cooldown 1 barre,
max N trades/jour. EOD close 16:00 NY, eod_bars_back=1.
"""
import importlib.util
import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
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
    step = 0.01
    lots = max(MIN_LOT, min(MAX_LOT, round(lots / step) * step))
    return round(lots, 2)


def simulate_multi(bars, risk, cost, target_r, max_trades, eod_bars_back=1):
    balance = ACCOUNT
    peak = balance
    max_dd = 0.0
    rows = []
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
        if not long_setup and not short_setup:
            continue

        trades_today = 0
        pos = None  # dict(side, entry, stop, target, entry_j)
        cooldown = 0
        last_high = None
        last_low = None
        for j in range(1, len(day)):
            row = day.iloc[j]
            high = float(row["high"])
            low = float(row["low"])
            mom6 = float(row["prev_mom6"])

            # gestion de la position ouverte
            if pos is not None:
                exit_price = None
                reason = None
                if pos["side"] == 1:
                    if low <= pos["stop"]:
                        exit_price, reason = pos["stop"], "stop"
                    elif high >= pos["target"]:
                        exit_price, reason = pos["target"], "target"
                else:
                    if high >= pos["stop"]:
                        exit_price, reason = pos["stop"], "stop"
                    elif low <= pos["target"]:
                        exit_price, reason = pos["target"], "target"
                if exit_price is not None:
                    entry = pos["entry"]
                    stop_dist = abs(entry - pos["stop"])
                    gross = pos["side"] * (exit_price - entry)
                    net = gross - cost
                    r_mult = net / stop_dist if stop_dist > 0 else 0.0
                    risk_money = balance * risk
                    lots = normalize_lots(risk_money / (stop_dist * TICK_VALUE))
                    pnl = net * lots * TICK_VALUE
                    balance += pnl
                    peak = max(peak, balance)
                    max_dd = max(max_dd, 1.0 - balance / peak)
                    rows.append({
                        "date": ny_date, "entry_time": day.iloc[pos["entry_j"]]["time"],
                        "side": "long" if pos["side"] == 1 else "short",
                        "entry": entry, "exit": exit_price, "reason": reason,
                        "net_points": net, "r_multiple": r_mult, "lots": lots,
                        "pnl": pnl, "balance": balance,
                        "trade_no": trades_today,
                    })
                    trades_today += 1
                    pos = None
                    cooldown = 1
                    last_high = high
                    last_low = low
                    continue

            # detection de nouvelle entree (premiere ou re-entree apres cooldown)
            if pos is None and cooldown > 0:
                cooldown -= 1
            if pos is None and cooldown == 0 and trades_today < max_trades:
                prev_high = last_high if last_high is not None else None
                prev_low = last_low if last_low is not None else None
                # long : le prix etait sous or_high (ou jamais casse) et recasse
                broke_up = np.isfinite(mom6) and mom6 >= mod.LONG_MOM_MIN and high >= or_high and (
                    prev_high is None or prev_high < or_high
                )
                broke_down = np.isfinite(mom6) and mom6 <= mod.SHORT_MOM_MAX and low <= or_low and (
                    prev_low is None or prev_low > or_low
                )
                if long_setup and broke_up:
                    entry = max(float(row["open"]), or_high)
                    pos = {"side": 1, "entry": entry, "stop": or_low,
                           "target": entry + target_r * (entry - or_low), "entry_j": j}
                elif short_setup and broke_down:
                    entry = min(float(row["open"]), or_low)
                    pos = {"side": -1, "entry": entry, "stop": or_high,
                           "target": entry - target_r * (or_high - entry), "entry_j": j}
            last_high = high
            last_low = low

        # position encore ouverte a la cloture -> EOD
        if pos is not None:
            entry = pos["entry"]
            stop_dist = abs(entry - pos["stop"])
            idx = max(pos["entry_j"], len(day) - 1 - eod_bars_back)
            exit_price = float(day.iloc[idx]["close"])
            gross = pos["side"] * (exit_price - entry)
            net = gross - cost
            r_mult = net / stop_dist if stop_dist > 0 else 0.0
            risk_money = balance * risk
            lots = normalize_lots(risk_money / (stop_dist * TICK_VALUE))
            pnl = net * lots * TICK_VALUE
            balance += pnl
            peak = max(peak, balance)
            max_dd = max(max_dd, 1.0 - balance / peak)
            rows.append({
                "date": ny_date, "entry_time": day.iloc[pos["entry_j"]]["time"],
                "side": "long" if pos["side"] == 1 else "short",
                "entry": entry, "exit": exit_price, "reason": "timeout",
                "net_points": net, "r_multiple": r_mult, "lots": lots,
                "pnl": pnl, "balance": balance,
                "trade_no": trades_today,
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
    days = (end - start).days
    return {
        "trades": len(d), "winrate": (r > 0).mean() * 100,
        "avg_r": r.mean(), "pf": pf,
        "return_pct": (bal / ACCOUNT - 1) * 100, "max_dd_pct": dd * 100,
        "per_day_usd": (bal - ACCOUNT) / max(days, 1),
    }


bars = mod.load_bars([
    "data_live/nas100_m15_kaggle_utc.parquet",
    "data_live/nas100_m15.parquet",
])

RISK, COST, EOD = 0.005, 1.7, 1
OOS = mod.PERIODS[1]
FULL = mod.PERIODS[-1]

rows = []
for target_r in (1.0, 1.25, 1.5, 2.0):
    for max_trades in (1, 2, 3, 5):
        trades, _ = simulate_multi(bars, RISK, COST, target_r, max_trades, EOD)
        m_oos = metrics(trades, RISK, OOS[1], OOS[2])
        m_full = metrics(trades, RISK, FULL[1], FULL[2])
        if m_oos is None:
            continue
        rows.append({
            "target_r": target_r, "max_trades": max_trades,
            "oos_trades": m_oos["trades"], "oos_winrate": round(m_oos["winrate"], 1),
            "oos_avg_r": round(m_oos["avg_r"], 3), "oos_pf": round(m_oos["pf"], 2),
            "oos_ret": round(m_oos["return_pct"], 2), "oos_dd": round(m_oos["max_dd_pct"], 2),
            "oos_usd_day": round(m_oos["per_day_usd"], 2),
            "full_ret": round(m_full["return_pct"], 2) if m_full else None,
            "full_dd": round(m_full["max_dd_pct"], 2) if m_full else None,
        })
        tag = f"t{target_r}_m{max_trades}"
        trades.to_csv(f"out_orb_target_sweep/aggr_{tag}.csv", index=False)

out = Path("out_orb_target_sweep")
df = pd.DataFrame(rows)
df.to_csv(out / "aggressive_summary.csv", index=False)
print(df.sort_values("oos_ret", ascending=False).to_string(index=False))
