import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

COST_POINTS = 1.7
TICK_VALUE = 1.0
ACCOUNT = 24592.71
RISK_PCT = 0.005
MIN_LOT = 0.05
MAX_LOT = 10.0


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--bars", default="data_live/nas100_m15.parquet")
    p.add_argument("--out", default="out_nas100_orb")
    p.add_argument("--bootstrap", type=int, default=2000)
    p.add_argument("--seed", type=int, default=20261109)
    p.add_argument("--ranges", default="1,2,4")
    p.add_argument("--targets", default="1.0,1.5,2.0")
    p.add_argument("--cost-points", type=float, default=COST_POINTS)
    p.add_argument("--tick-value", type=float, default=TICK_VALUE)
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


def simulate_day(g, range_bars, target_r):
    start = pd.Timestamp("09:30").time()
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
        if side == 1:
            target = entry + target_r * (entry - stop)
        else:
            target = entry - target_r * (stop - entry)
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
        net = gross - COST_POINTS
        stop_dist = abs(entry - stop)
        if stop_dist <= 0:
            return None
        lots = min(MAX_LOT, max(MIN_LOT, RISK_PCT * ACCOUNT / (stop_dist * TICK_VALUE)))
        pnl = net * lots * TICK_VALUE
        r_multiple = net / stop_dist
        return {
            "date": row["ny_date"],
            "entry_time": row["time"],
            "side": "long" if side == 1 else "short",
            "entry": entry,
            "stop": stop,
            "target": target,
            "exit": exit_price,
            "reason": reason,
            "gross_points": gross,
            "net_points": net,
            "stop_points": stop_dist,
            "lots": lots,
            "pnl": pnl,
            "r_multiple": r_multiple,
        }
    return None


def main():
    global COST_POINTS, TICK_VALUE, ACCOUNT, RISK_PCT
    args = parse_args()
    COST_POINTS = args.cost_points
    TICK_VALUE = args.tick_value
    ACCOUNT = args.account
    RISK_PCT = args.risk_pct
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    bars = load_bars(args.bars)
    days = [g for _, g in bars.groupby("ny_date", sort=True)]
    ranges = [int(value) for value in args.ranges.split(",")]
    targets = [float(value) for value in args.targets.split(",")]
    combos = [(rb, tr) for rb in ranges for tr in targets]
    all_trades = []
    summary_rows = []
    daily_by_combo = {}
    for range_bars, target_r in combos:
        trades = []
        for g in days:
            trade = simulate_day(g, range_bars, target_r)
            if trade is not None:
                trade.update({"range_bars": range_bars, "target_r": target_r})
                trades.append(trade)
        tr = pd.DataFrame(trades)
        if tr.empty:
            continue
        tr.to_csv(out / f"trades_r{range_bars}_t{target_r}.csv", index=False)
        all_trades.append(tr)
        daily = tr.groupby("date")["pnl"].sum()
        daily_by_combo[f"r{range_bars}_t{target_r}"] = daily
        n_days = len(days)
        n_trade_days = len(daily)
        mean_all = float(daily.reindex([g["ny_date"].iloc[0] for g in days], fill_value=0.0).mean())
        mean_trade = float(daily.mean())
        std_trade = float(daily.std(ddof=1)) if n_trade_days > 1 else np.nan
        t_trade = mean_trade / (std_trade / np.sqrt(n_trade_days)) if std_trade and std_trade > 0 else 0.0
        total = float(tr["pnl"].sum())
        win = float((tr["pnl"] > 0).mean())
        summary_rows.append({
            "range_bars": range_bars,
            "target_r": target_r,
            "trades": int(len(tr)),
            "trade_days": int(n_trade_days),
            "all_days": int(n_days),
            "win_rate": win,
            "avg_r": float(tr["r_multiple"].mean()),
            "total_pnl": total,
            "mean_per_all_day": mean_all,
            "mean_per_trade_day": mean_trade,
            "median_per_trade_day": float(daily.median()),
            "t_trade_day": t_trade,
            "max_dd": float((daily.cumsum().cummax() - daily.cumsum()).max()),
        })
    summary = pd.DataFrame(summary_rows).sort_values("mean_per_all_day", ascending=False).reset_index(drop=True)
    summary.to_csv(out / "summary.csv", index=False)
    if summary.empty:
        raise SystemExit("no trades")
    best = summary.iloc[0].to_dict()

    daily_matrix = pd.DataFrame(daily_by_combo).fillna(0.0)
    y = daily_matrix.to_numpy(float)
    n = y.shape[0]
    means = y.mean(axis=0)
    stds = y.std(axis=0, ddof=1)
    t_obs = means / (stds / np.sqrt(n))
    max_pos = float(np.max(t_obs))
    y0 = y - means
    rng = np.random.default_rng(args.seed)
    boot = np.empty(args.bootstrap)
    for b in range(args.bootstrap):
        idx = rng.integers(0, n, n)
        s = y0[idx]
        m = s.mean(axis=0)
        sd = s.std(axis=0, ddof=1)
        tt = np.divide(m, sd / np.sqrt(n), out=np.zeros_like(m), where=sd > 0)
        boot[b] = np.max(tt)
    p_adj = float((1 + np.sum(boot >= max_pos)) / (args.bootstrap + 1))
    target_ok = best["mean_per_all_day"] >= 50.0
    result = {
        "bars": args.bars,
        "days": len(days),
        "first": str(bars["time"].min()),
        "last": str(bars["time"].max()),
        "risk_pct": RISK_PCT,
        "account": ACCOUNT,
        "cost_points": COST_POINTS,
        "best": best,
        "max_positive_t": max_pos,
        "p_adjusted": p_adj,
        "target_50_per_day": target_ok,
        "required_risk_note": "mean_per_all_day is at 0.5% risk per trade; scaling risk scales PnL and drawdown",
    }
    (out / "summary.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    lines = [
        "# NAS100 opening-range breakout scan",
        "",
        f"- Data: {bars['time'].min()} to {bars['time'].max()}, {len(days)} NY dates",
        f"- Risk: {RISK_PCT*100:.1f}% per trade (${RISK_PCT*ACCOUNT:.2f}); cost {COST_POINTS} index points",
        f"- Best: range={best['range_bars']} bars, target={best['target_r']}R, trades={best['trades']}, win={best['win_rate']*100:.1f}%, avg R={best['avg_r']:.3f}",
        f"- Mean PnL/all day: ${best['mean_per_all_day']:.2f}; per trade day: ${best['mean_per_trade_day']:.2f}; max DD: ${best['max_dd']:.2f}",
        f"- Max positive t: {max_pos:.2f}; p adjusted: {p_adj:.4f}; target $50/day: {target_ok}",
        "",
        "## All combinations",
        "",
        summary.to_markdown(index=False),
    ]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "days": len(days),
        "best": f"range={best['range_bars']} target={best['target_r']}",
        "trades": int(best["trades"]),
        "avg_r": round(float(best["avg_r"]), 3),
        "mean_all_day": round(float(best["mean_per_all_day"]), 2),
        "mean_trade_day": round(float(best["mean_per_trade_day"]), 2),
        "max_dd": round(float(best["max_dd"]), 2),
        "max_positive_t": round(max_pos, 2),
        "p_adj": round(p_adj, 4),
        "target_50": bool(target_ok),
    }, indent=2))


if __name__ == "__main__":
    main()
