from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("out_orb_entry_scan")
OUT.mkdir(exist_ok=True)


def stat(x):
    x = pd.Series(x).dropna().to_numpy(float)
    if len(x) < 5:
        return len(x), np.nan, np.nan, np.nan
    m = x.mean()
    s = x.std(ddof=1)
    return len(x), float(m), float(m / (s / np.sqrt(len(x)))) if s > 0 else 0.0, float((x > 0).mean())


def periods(d):
    return {
        "is": d[d["date"] < pd.Timestamp("2022-01-01").date()],
        "oos": d[(d["date"] >= pd.Timestamp("2022-01-01").date()) & (d["date"] < pd.Timestamp("2025-10-01").date())],
        "rec": d[d["date"] >= pd.Timestamp("2025-09-01").date()],
    }


def main():
    d = pd.read_csv("out_orb_entry_features/nas100_entry_features.csv")
    d["date"] = pd.to_datetime(d["date"]).dt.date
    d = d[d["side"].eq("long") & (d["trend_daily"] < 0.00425)].copy()
    print("filtered", len(d), d["date"].min(), d["date"].max())
    features = [
        "delay_min", "range_atr", "range_pct", "range_pct_rank60", "spread_atr",
        "entry_vs_vwap_atr", "entry_vs_or_mid_atr", "dist_prev_high_atr",
        "dist_prev_low_atr", "dist_prev_close_atr", "range_vs_prev_range",
        "or_body_ratio", "or_close_pos", "or_upper_wick", "or_lower_wick", "or_vol_ratio",
        "prev_body_ratio", "prev_close_pos", "prev_upper_wick", "prev_lower_wick",
        "prev_range_atr", "prev_body_atr", "prev_vol_ratio", "prev_vol20_bar",
        "prev_atr", "prev_spread", "prev_rsi", "prev_trend_m15", "prev_above200",
        "prev_mom3", "prev_mom6", "prev_bar_ret", "trend_daily", "above200d",
        "gap_pct", "prev_day_ret", "prev_day_range_pct", "atr14_pct", "dow",
    ]
    rows = []
    for f in features:
        if f not in d:
            continue
        x = d[f].replace([np.inf, -np.inf], np.nan)
        if x.nunique() < 3:
            continue
        try:
            d["_bin"] = pd.qcut(x, 5, labels=False, duplicates="drop")
        except ValueError:
            continue
        for b, g in d.groupby("_bin"):
            for label, part in periods(g).items():
                n, avg, t, win = stat(part["r_multiple"])
                if n >= 8:
                    rows.append({"feature": f, "bin": int(b), "period": label,
                                 "n": n, "avgR": avg, "t": t, "win": win,
                                 "lo": float(g[f].min()), "hi": float(g[f].max())})
    q = pd.DataFrame(rows)
    q.to_csv(OUT / "quintiles.csv", index=False)
    piv = q.pivot_table(index=["feature", "bin"], columns="period", values="avgR")
    print(piv.round(3).to_string())

    print("\nCorrelations with r_multiple (all / is / oos / rec):")
    for f in features:
        if f not in d:
            continue
        vals = []
        for label, part in [("all", d), *periods(d).items()]:
            vals.append(part[f].corr(part["r_multiple"]))
        print(f"{f:24s} " + " ".join(f"{v:+.3f}" for v in vals))


if __name__ == "__main__":
    main()
