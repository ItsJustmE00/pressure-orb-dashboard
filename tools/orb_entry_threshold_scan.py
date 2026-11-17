import itertools
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("out_orb_entry_scan")
OUT.mkdir(exist_ok=True)


def stat(x):
    x = pd.Series(x).dropna().to_numpy(float)
    if len(x) < 4:
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
    isd = d[d["date"] < pd.Timestamp("2022-01-01").date()]

    specs = {
        "or_close_pos": ("high", [0.5, 0.6, 0.7, 0.8]),
        "or_upper_wick": ("low", [0.2, 0.3, 0.4, 0.5]),
        "prev_close_pos": ("high", [0.5, 0.6, 0.7, 0.8]),
        "prev_upper_wick": ("low", [0.2, 0.3, 0.4, 0.5]),
        "prev_rsi": ("high", [0.5, 0.6, 0.7, 0.8]),
        "dist_prev_high_atr": ("high", [0.4, 0.5, 0.6, 0.7, 0.8]),
        "dist_prev_low_atr": ("high", [0.4, 0.5, 0.6, 0.7, 0.8]),
        "prev_mom6": ("high", [0.4, 0.5, 0.6, 0.7]),
        "prev_mom3": ("high", [0.4, 0.5, 0.6, 0.7]),
        "range_pct": ("high", [0.4, 0.5, 0.6, 0.7, 0.8]),
        "range_pct_rank60": ("high", [0.4, 0.5, 0.6, 0.7, 0.8]),
        "range_atr": ("high", [0.4, 0.5, 0.6, 0.7, 0.8]),
        "prev_above200": ("eq1", []),
        "above200d": ("eq1", []),
        "dow": ("in", [(0, 1), (0, 1, 2), (0, 1, 2, 3)]),
        "delay_min": ("in", [(0, 15, 30), (0, 15, 30, 45), (0, 15, 30, 45, 60)]),
    }
    rows = []
    conds = {}
    for f, (direction, qs) in specs.items():
        if f not in d:
            continue
        if direction == "eq1":
            conds[f + "==1"] = d[f].eq(1)
            continue
        if direction == "in":
            for vals in qs:
                conds[f + "in" + str(vals)] = d[f].isin(vals)
            continue
        for q in qs:
            th = isd[f].quantile(q)
            if direction == "high":
                conds[f + ">" + f"{th:.4g}"] = d[f] > th
            else:
                conds[f + "<" + f"{th:.4g}"] = d[f] < th
    for name, cond in conds.items():
        sub = d[cond]
        out = {"rule": name, "n_all": len(sub)}
        for label, part in periods(sub).items():
            n, avg, t, win = stat(part["r_multiple"])
            out[f"{label}_n"] = n
            out[f"{label}_R"] = avg
            out[f"{label}_t"] = t
            out[f"{label}_win"] = win
        rows.append(out)
    df = pd.DataFrame(rows)
    df["score"] = df[["is_R", "oos_R", "rec_R"]].min(axis=1)
    df = df.sort_values("score", ascending=False)
    df.to_csv(OUT / "individual_rules.csv", index=False)
    print("=== individual rules (top by min-period avgR, n>=15/10) ===")
    cols = ["rule", "is_n", "is_R", "is_t", "oos_n", "oos_R", "oos_t", "rec_n", "rec_R", "rec_t"]
    print(df[(df.is_n >= 15) & (df.oos_n >= 10)][cols].head(30).round(3).to_string(index=False))

    # combinations of top individual rules, excluding redundant same-feature variants
    top = df[(df.is_n >= 25) & (df.oos_n >= 20) & (df.rec_n >= 8)].head(18)
    names = top["rule"].tolist()
    print("\n=== pair combinations ===")
    rows2 = []
    for a, b in itertools.combinations(names, 2):
        if a.split(">")[0].split("<")[0] == b.split(">")[0].split("<")[0]:
            continue
        sub = d[conds[a] & conds[b]]
        out = {"rule": a + " & " + b, "n_all": len(sub)}
        for label, part in periods(sub).items():
            n, avg, t, win = stat(part["r_multiple"])
            out[f"{label}_n"] = n
            out[f"{label}_R"] = avg
            out[f"{label}_t"] = t
        rows2.append(out)
    p = pd.DataFrame(rows2)
    p["score"] = p[["is_R", "oos_R", "rec_R"]].min(axis=1)
    p = p.sort_values("score", ascending=False)
    p.to_csv(OUT / "pair_rules.csv", index=False)
    cols2 = ["rule", "is_n", "is_R", "is_t", "oos_n", "oos_R", "oos_t", "rec_n", "rec_R", "rec_t"]
    print(p[(p.is_n >= 15) & (p.oos_n >= 10)][cols2].head(30).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
