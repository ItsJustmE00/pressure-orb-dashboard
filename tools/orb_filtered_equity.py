import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def load(sym):
    df = pd.read_csv(Path("out_orb_filter_scan") / f"{sym}_trades_features.csv")
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def thresholds(df):
    isdf = df[df["date"] < pd.Timestamp("2022-01-01").date()]
    return {
        "trend_low": isdf["trend_daily"].quantile(0.2),
        "range_rank_low": isdf["range_pct_rank60"].quantile(0.2),
        "vol_lo": isdf["vol20"].quantile(0.2),
        "vol_hi": isdf["vol20"].quantile(0.8),
        "rsi_hi": isdf["rsi14"].quantile(0.6),
    }


def select(df, q, name):
    if name == "nas_trend_long":
        return df[(df["side"] == "long") & (df["trend_daily"] < q["trend_low"])]
    if name == "nas_trend_rsi_long":
        return df[(df["side"] == "long") & (df["trend_daily"] < q["trend_low"]) & (df["rsi14"] > q["rsi_hi"])]
    if name == "us30_range_low":
        return df[df["range_pct_rank60"] < q["range_rank_low"]]
    if name == "us30_range_low_long":
        return df[(df["side"] == "long") & (df["range_pct_rank60"] < q["range_rank_low"])]
    if name == "nas_vol_mid":
        return df[(df["vol20"] >= q["vol_lo"]) & (df["vol20"] <= q["vol_hi"])]
    if name == "us30_vol_mid":
        return df[(df["vol20"] >= q["vol_lo"]) & (df["vol20"] <= q["vol_hi"])]
    raise ValueError(name)


def simulate(trades, risk, start=57000.0):
    trades = trades.sort_values(["date", "entry_time"]).copy()
    eq = start
    peak = start
    dd = 0.0
    rows = []
    for d, g in trades.groupby("date", sort=True):
        day_start = eq
        for _, t in g.iterrows():
            r = float(t["r_multiple"])
            eq *= 1.0 + risk * r
            peak = max(peak, eq)
            dd = max(dd, 1.0 - eq / peak)
        rows.append({"date": d, "pnl": eq - day_start, "equity": eq})
    daily = pd.DataFrame(rows)
    out = {
        "n": len(trades),
        "start": start,
        "end": eq,
        "ret_pct": (eq / start - 1.0) * 100.0,
        "max_dd_pct": dd * 100.0,
        "days": len(daily),
        "avg_day": daily["pnl"].mean() if len(daily) else 0.0,
        "median_day": daily["pnl"].median() if len(daily) else 0.0,
    }
    return out, daily


def period_sim(trades, risk, period):
    if period == "is":
        t = trades[trades["date"] < pd.Timestamp("2022-01-01").date()]
    elif period == "oos":
        t = trades[(trades["date"] >= pd.Timestamp("2022-01-01").date()) & (trades["date"] < pd.Timestamp("2025-10-01").date())]
    elif period == "rec":
        t = trades[trades["date"] >= pd.Timestamp("2025-09-01").date()]
    else:
        t = trades
    return simulate(t, risk)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--risk", type=float, default=0.5)
    ap.add_argument("--out", default="out_orb_filtered_equity")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    data = {s: load(s) for s in ["nas100", "us30"]}
    qs = {s: thresholds(data[s]) for s in data}
    cands = {
        "nas_trend_long": ("nas100", "nas_trend_long"),
        "nas_trend_rsi_long": ("nas100", "nas_trend_rsi_long"),
        "nas_vol_mid": ("nas100", "nas_vol_mid"),
        "us30_range_low": ("us30", "us30_range_low"),
        "us30_range_low_long": ("us30", "us30_range_low_long"),
        "us30_vol_mid": ("us30", "us30_vol_mid"),
    }
    selected = {}
    for name, (sym, rule) in cands.items():
        selected[name] = select(data[sym], qs[sym], rule)
    rows = []
    for name, t in selected.items():
        for risk in [0.5, 1.0, 1.5, 2.0]:
            sim, daily = simulate(t, risk / 100.0)
            sim.update({"strategy": name, "risk_pct": risk, "period": "full"})
            rows.append(sim)
            daily.to_csv(out / f"{name}_risk{risk}.csv", index=False)
            for period in ["is", "oos", "rec"]:
                s2, d2 = period_sim(t, risk / 100.0, period)
                s2.update({"strategy": name, "risk_pct": risk, "period": period})
                rows.append(s2)
    df = pd.DataFrame(rows)
    cols = ["strategy", "risk_pct", "period", "n", "ret_pct", "max_dd_pct", "avg_day", "end"]
    print("\n=== individual ===")
    print(df[cols].round(2).to_string(index=False))
    df.to_csv(out / "individual.csv", index=False)

    print("\n=== portfolios at 0.5% risk per trade ===")
    port_rows = []
    for combo in [
        ("nas_trend_long", "us30_range_low"),
        ("nas_trend_rsi_long", "us30_range_low"),
        ("nas_vol_mid", "us30_vol_mid"),
        ("nas_trend_long", "us30_range_low_long"),
        ("nas_trend_rsi_long", "us30_range_low_long"),
    ]:
        trades = pd.concat([selected[c] for c in combo], ignore_index=True)
        for risk in [0.5, 1.0, 1.5]:
            sim, daily = simulate(trades, risk / 100.0)
            sim.update({"strategy": "+".join(combo), "risk_pct": risk, "period": "full"})
            port_rows.append(sim)
            daily.to_csv(out / f"port_{'_'.join(combo)}_risk{risk}.csv", index=False)
            for period in ["is", "oos", "rec"]:
                s2, d2 = period_sim(trades, risk / 100.0, period)
                s2.update({"strategy": "+".join(combo), "risk_pct": risk, "period": period})
                port_rows.append(s2)
    p = pd.DataFrame(port_rows)
    print(p[cols].round(2).to_string(index=False))
    p.to_csv(out / "portfolios.csv", index=False)


if __name__ == "__main__":
    main()
