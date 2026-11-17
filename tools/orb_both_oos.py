import argparse
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ACCOUNT = 57000.0
TICK_VALUE = 1.0
MIN_LOT = 0.05
LOT_STEP = 0.01
MAX_LOT = 100.0
LONG_TREND_MAX = 0.002378
LONG_OR_MIN = 0.8044
LONG_MOM_MIN = 0.00123
SHORT_TREND_MIN = -0.00425
SHORT_OR_MAX = 0.1956
SHORT_MOM_MAX = -0.00123
TARGET_R = 3.0

PERIODS = [
    ("is", date(2016, 11, 15), date(2021, 12, 31)),
    ("oos", date(2022, 1, 1), date(2025, 9, 20)),
    ("recent", date(2025, 9, 21), date(2026, 9, 15)),
    ("y26", date(2026, 1, 1), date(2026, 9, 15)),
    ("full", date(2016, 11, 15), date(2026, 9, 15)),
]


def load_bars(paths):
    frames = []
    for path in paths:
        d = pd.read_parquet(path)
        d["time"] = pd.to_datetime(d["time"], utc=True)
        frames.append(d[["time", "open", "high", "low", "close", "tick_volume", "spread"]])
    d = pd.concat(frames, ignore_index=True)
    d = d.sort_values("time").drop_duplicates("time", keep="last").reset_index(drop=True)
    d["ny"] = d["time"].dt.tz_convert("America/New_York")
    d["ny_date"] = d["ny"].dt.date
    d["utc_date"] = d["time"].dt.date
    d["ny_min"] = d["ny"].dt.hour * 60 + d["ny"].dt.minute
    d["prev_mom6"] = d["close"].shift(1) / d["close"].shift(7) - 1.0
    daily = d.groupby("utc_date")["close"].last().to_frame("d_close")
    daily["ema20"] = daily["d_close"].ewm(span=20, adjust=False).mean()
    daily["ema50"] = daily["d_close"].ewm(span=50, adjust=False).mean()
    daily["trend"] = (
        daily["ema20"].shift(1) - daily["ema50"].shift(1)
    ) / daily["d_close"].shift(1)
    d["trend_daily"] = d["ny_date"].map(daily["trend"].to_dict())
    return d


def normalize_lots(lots):
    lots = np.floor(lots / LOT_STEP) * LOT_STEP
    return float(max(MIN_LOT, min(MAX_LOT, round(lots, 2))))


def simulate(bars, risk, cost, eod_bars_back):
    balance = ACCOUNT
    peak = balance
    max_dd = 0.0
    rows = []
    for ny_date, g in bars.groupby("ny_date", sort=True):
        if ny_date < PERIODS[0][1] or ny_date > PERIODS[-1][2]:
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
        long_setup = np.isfinite(trend) and trend <= LONG_TREND_MAX and or_close_pos >= LONG_OR_MIN
        short_setup = np.isfinite(trend) and trend >= SHORT_TREND_MIN and or_close_pos <= SHORT_OR_MAX
        if not long_setup and not short_setup:
            continue
        trade = None
        for j in range(1, len(day)):
            row = day.iloc[j]
            mom6 = float(row["prev_mom6"])
            if long_setup and np.isfinite(mom6) and mom6 >= LONG_MOM_MIN:
                if float(row["high"]) >= or_high:
                    entry = max(float(row["open"]), or_high)
                    trade = ("long", entry, or_low, 1, j, trend, or_close_pos, mom6)
                    break
            elif short_setup and np.isfinite(mom6) and mom6 <= SHORT_MOM_MAX:
                if float(row["low"]) <= or_low:
                    entry = min(float(row["open"]), or_low)
                    trade = ("short", entry, or_high, -1, j, trend, or_close_pos, mom6)
                    break
        if trade is None:
            continue
        side_name, entry, stop, side, entry_j, trend, or_close_pos, mom6 = trade
        stop_dist = abs(entry - stop)
        if stop_dist <= 0.0:
            continue
        target = entry + TARGET_R * (entry - stop) if side == 1 else entry - TARGET_R * (stop - entry)
        exit_price = None
        reason = "timeout"
        for k in range(entry_j, len(day)):
            bar = day.iloc[k]
            high = float(bar["high"])
            low = float(bar["low"])
            if side == 1:
                if low <= stop:
                    exit_price = stop
                    reason = "stop"
                    break
                if high >= target:
                    exit_price = target
                    reason = "target"
                    break
            else:
                if high >= stop:
                    exit_price = stop
                    reason = "stop"
                    break
                if low <= target:
                    exit_price = target
                    reason = "target"
                    break
        if exit_price is None:
            idx = max(entry_j, len(day) - 1 - eod_bars_back)
            exit_price = float(day.iloc[idx]["close"])
        gross_points = side * (exit_price - entry)
        net_points = gross_points - cost
        r_multiple = net_points / stop_dist
        risk_money = balance * risk
        lots = normalize_lots(risk_money / (stop_dist * TICK_VALUE))
        pnl = net_points * lots * TICK_VALUE
        balance += pnl
        peak = max(peak, balance)
        max_dd = max(max_dd, 1.0 - balance / peak)
        rows.append({
            "date": ny_date,
            "entry_time": day.iloc[entry_j]["time"],
            "side": side_name,
            "entry": entry,
            "stop": stop,
            "target": target,
            "exit": exit_price,
            "reason": reason,
            "gross_points": gross_points,
            "net_points": net_points,
            "stop_points": stop_dist,
            "r_multiple": r_multiple,
            "lots": lots,
            "pnl": pnl,
            "balance": balance,
            "trend_daily": trend,
            "or_high": or_high,
            "or_low": or_low,
            "or_close_pos": or_close_pos,
            "prev_mom6": mom6,
        })
    trades = pd.DataFrame(rows)
    return trades, max_dd


def period_metrics(trades, risk, start, end):
    if trades.empty:
        return None
    d = trades[(trades["date"] >= start) & (trades["date"] <= end)]
    if d.empty:
        return None
    r = d["r_multiple"].to_numpy(float)
    balance = ACCOUNT
    peak = balance
    max_dd = 0.0
    for value in r:
        balance *= 1.0 + risk * value
        peak = max(peak, balance)
        max_dd = max(max_dd, 1.0 - balance / peak)
    days = max(1, (end - start).days + 1)
    return {
        "trades": int(len(d)),
        "win_rate": float((r > 0).mean()),
        "avg_r": float(r.mean()),
        "total_r": float(r.sum()),
        "final": float(balance),
        "return_pct": float(balance / ACCOUNT - 1.0),
        "max_dd_pct": float(max_dd),
        "per_day": float((balance - ACCOUNT) / days),
        "long_n": int((d["side"] == "long").sum()),
        "short_n": int((d["side"] == "short").sum()),
        "long_avg_r": float(d.loc[d["side"] == "long", "r_multiple"].mean()) if (d["side"] == "long").any() else float("nan"),
        "short_avg_r": float(d.loc[d["side"] == "short", "r_multiple"].mean()) if (d["side"] == "short").any() else float("nan"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--risks", default="0.005,0.025")
    ap.add_argument("--costs", default="1.7,3.4,5.1")
    ap.add_argument("--eod-bars-back", default="0,1")
    ap.add_argument("--out", default="out_orb_both_oos")
    args = ap.parse_args()
    risks = [float(x) for x in args.risks.split(",")]
    costs = [float(x) for x in args.costs.split(",")]
    eod_modes = [int(x) for x in args.eod_bars_back.split(",")]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    bars = load_bars([
        "data_live/nas100_m15_kaggle_utc.parquet",
        "data_live/nas100_m15.parquet",
    ])
    summary_rows = []
    all_trades = {}
    for risk in risks:
        for cost in costs:
            for eod_back in eod_modes:
                trades, sim_dd = simulate(bars, risk, cost, eod_back)
                tag = f"r{risk:.3f}_c{cost:.1f}_e{eod_back}"
                all_trades[tag] = trades
                trades.to_csv(out / f"trades_{tag}.csv", index=False)
                for name, start, end in PERIODS:
                    m = period_metrics(trades, risk, start, end)
                    if m is None:
                        continue
                    summary_rows.append({
                        "risk_pct": risk * 100.0,
                        "cost_points": cost,
                        "eod_bars_back": eod_back,
                        "period": name,
                        **m,
                        "sim_max_dd_pct": sim_dd if name == "full" else float("nan"),
                    })
                full = period_metrics(trades, risk, PERIODS[-1][1], PERIODS[-1][2])
                print(
                    f"risk={risk*100:.1f}% cost={cost:.1f} eod_back={eod_back} "
                    f"trades={len(trades)} final={full['final']:.2f} "
                    f"ret={full['return_pct']*100:.2f}% dd={full['max_dd_pct']*100:.2f}%"
                )
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(out / "summary.csv", index=False)
    meta = {
        "account": ACCOUNT,
        "tick_value": TICK_VALUE,
        "min_lot": MIN_LOT,
        "max_lot": MAX_LOT,
        "target_r": TARGET_R,
        "filters": {
            "long": {
                "trend_max": LONG_TREND_MAX,
                "or_close_min": LONG_OR_MIN,
                "mom6_min": LONG_MOM_MIN,
            },
            "short": {
                "trend_min": SHORT_TREND_MIN,
                "or_close_max": SHORT_OR_MAX,
                "mom6_max": SHORT_MOM_MAX,
            },
        },
        "data": {
            "start": str(bars["time"].min()),
            "end": str(bars["time"].max()),
            "ny_dates": int(bars["ny_date"].nunique()),
        },
        "note": (
            "Bar-level BOTH simulation using only the side whose filters pass; "
            "no tick bid/ask order flow. EOD close at last M15 close (16:00 NY); "
            "eod_bars_back=1 uses 15:45 close as sensitivity. Calibration on the "
            "2025-09-21..2026-09-15 MT5 run shows ~0.08R/trade of bar-level optimism."
        ),
    }
    (out / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    cols = [
        "risk_pct", "cost_points", "eod_bars_back", "period", "trades",
        "win_rate", "avg_r", "total_r", "final", "return_pct",
        "max_dd_pct", "per_day", "long_n", "short_n", "long_avg_r", "short_avg_r",
    ]
    print("\n", summary[cols].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
