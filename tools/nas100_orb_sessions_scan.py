import argparse
from pathlib import Path

import numpy as np
import pandas as pd

COST_POINTS = 1.7
TICK_VALUE = 1.0
ACCOUNT = 57000.0
RISK_PCT = 0.005
MIN_LOT = 0.05
MAX_LOT = 10.0


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--bars", default="data_live/nas100_m15.parquet")
    p.add_argument("--out", default="out_orb_sessions")
    p.add_argument("--starts", default="09:30,10:00,10:30,11:00")
    p.add_argument("--ranges", default="1,2")
    p.add_argument("--targets", default="3.0")
    p.add_argument("--cost-points", type=float, default=COST_POINTS)
    p.add_argument("--account", type=float, default=ACCOUNT)
    p.add_argument("--risk-pct", type=float, default=RISK_PCT)
    return p.parse_args()


def load_bars(path):
    df = pd.read_parquet(path)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df["ny"] = df["time"].dt.tz_convert("America/New_York")
    df["ny_date"] = df["ny"].dt.date
    df["ny_time"] = df["ny"].dt.time
    return df.sort_values("time").reset_index(drop=True)


def simulate_day(g, start, range_bars, target_r, cost_points):
    end = pd.Timestamp("16:00").time()
    day = g[(g["ny_time"] >= start) & (g["ny_time"] < end)].copy()
    if len(day) < range_bars + 2:
        return None
    day = day.reset_index(drop=True)
    range_part = day.iloc[:range_bars]
    hi = float(range_part["high"].max())
    lo = float(range_part["low"].min())
    if not np.isfinite(hi) or not np.isfinite(lo) or hi <= lo:
        return None
    for j in range(range_bars, len(day)):
        row = day.iloc[j]
        up = float(row["high"]) >= hi
        dn = float(row["low"]) <= lo
        if up and dn:
            return None
        if not up and not dn:
            continue
        side = 1 if up else -1
        entry = max(float(row["open"]), hi) if side == 1 else min(float(row["open"]), lo)
        stop = lo if side == 1 else hi
        target = entry + target_r * (entry - stop) if side == 1 else entry - target_r * (stop - entry)
        exit_price = None
        reason = "timeout"
        for k in range(j, len(day)):
            h = float(day["high"].iloc[k])
            l = float(day["low"].iloc[k])
            if side == 1:
                if l <= stop:
                    exit_price = stop
                    reason = "stop"
                    break
                if h >= target:
                    exit_price = target
                    reason = "target"
                    break
            else:
                if h >= stop:
                    exit_price = stop
                    reason = "stop"
                    break
                if l <= target:
                    exit_price = target
                    reason = "target"
                    break
        if exit_price is None:
            exit_price = float(day["close"].iloc[-1])
        gross = side * (exit_price - entry)
        net = gross - cost_points
        stop_dist = abs(entry - stop)
        if stop_dist <= 0:
            return None
        lots = min(MAX_LOT, max(MIN_LOT, RISK_PCT * ACCOUNT / (stop_dist * TICK_VALUE)))
        return {
            "date": row["ny_date"],
            "entry_time": row["time"],
            "side": "long" if side == 1 else "short",
            "entry": entry,
            "stop": stop,
            "target": target,
            "exit": exit_price,
            "reason": reason,
            "stop_points": stop_dist,
            "lots": lots,
            "pnl": net * lots * TICK_VALUE,
            "r_multiple": net / stop_dist,
        }
    return None


def main():
    args = parse_args()
    out = Path(args.out)
    out.mkdir(exist_ok=True)
    bars = load_bars(args.bars)
    days = [(d, g) for d, g in bars.groupby("ny_date", sort=True)]
    all_dates = [d for d, _ in days]
    starts = [pd.Timestamp(s).time() for s in args.starts.split(",")]
    ranges = [int(x) for x in args.ranges.split(",")]
    targets = [float(x) for x in args.targets.split(",")]
    rows = []
    for start in starts:
        for range_bars in ranges:
            for target_r in targets:
                trades = []
                for _, g in days:
                    tr = simulate_day(g, start, range_bars, target_r, args.cost_points)
                    if tr:
                        trades.append(tr)
                if not trades:
                    continue
                tr = pd.DataFrame(trades)
                daily = tr.groupby("date")["pnl"].sum().reindex(all_dates, fill_value=0.0)
                n = len(daily)
                mean = float(daily.mean())
                std = float(daily.std(ddof=1))
                t = mean / (std / np.sqrt(n)) if std > 0 else 0.0
                cum = daily.cumsum()
                dd = float((cum.cummax() - cum).max())
                rows.append({
                    "start": start.strftime("%H:%M"),
                    "range_bars": range_bars,
                    "target_r": target_r,
                    "trades": len(tr),
                    "days": n,
                    "win_rate": float((tr["r_multiple"] > 0).mean()),
                    "avg_r": float(tr["r_multiple"].mean()),
                    "mean_all_day": mean,
                    "mean_trade_day": float(daily[daily != 0].mean()),
                    "t_stat": t,
                    "max_dd": dd,
                })
    df = pd.DataFrame(rows).sort_values("mean_all_day", ascending=False)
    df.to_csv(out / "summary.csv", index=False)
    print(df.round(4).to_string(index=False))
    print("\n50$/day at 0.5% risk:", (df["mean_all_day"] >= 50).any())
    print("50$/day at 3.0% risk:", (df["mean_all_day"] * 6 >= 50).any())


if __name__ == "__main__":
    main()
