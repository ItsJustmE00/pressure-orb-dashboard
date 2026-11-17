import itertools
import random
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("out_orb_entry_scan")
OUT.mkdir(exist_ok=True)
RNG = random.Random(42)


def stats(part):
    x = pd.to_numeric(part["r_multiple"], errors="coerce").dropna().to_numpy(float)
    if len(x) < 4:
        return len(x), np.nan, np.nan, np.nan
    mean = float(x.mean())
    std = float(x.std(ddof=1))
    t = mean / (std / np.sqrt(len(x))) if std > 0 else 0.0
    return len(x), mean, float(t), float((x > 0).mean())


def equity(part, risk):
    bal = 57000.0
    peak = bal
    dd = 0.0
    for r in part.sort_values("date")["r_multiple"]:
        bal *= 1.0 + risk * float(r)
        peak = max(peak, bal)
        dd = max(dd, 1.0 - bal / peak)
    return bal, dd


def main():
    d = pd.read_csv("out_orb_entry_features/nas100_entry_features.csv")
    d["date"] = pd.to_datetime(d["date"])
    d = d[d["side"].eq("long")].copy()
    isd = d[d["date"] < "2022-01-01"]

    pool = {}
    for feat in [
        "or_close_pos", "or_upper_wick", "prev_close_pos", "prev_upper_wick",
        "prev_rsi", "prev_mom6", "prev_mom3", "range_pct_rank60",
        "range_atr", "gap_pct", "prev_day_ret", "atr14_pct",
        "dist_prev_high_atr", "dist_prev_low_atr", "spread_atr",
    ]:
        if feat not in d:
            continue
        for q in (0.4, 0.5, 0.6, 0.7, 0.8):
            th = float(isd[feat].quantile(q))
            pool[f"{feat}>{th:.6g}"] = d[feat] > th
            pool[f"{feat}<{th:.6g}"] = d[feat] < th
    for th in (0.002378, 0.00425, 0.006):
        pool[f"trend_daily<{th}"] = d["trend_daily"] < th
    for feat in ("above200d", "prev_above200"):
        if feat in d:
            pool[f"{feat}==1"] = d[feat].eq(1)
    pool["or_close_pos>0.8044"] = d["or_close_pos"] > 0.8044
    pool["prev_mom6>0.00123"] = d["prev_mom6"] > 0.00123
    pool["prev_upper_wick<0.07838"] = d["prev_upper_wick"] < 0.07838
    pool["prev_close_pos>0.9085"] = d["prev_close_pos"] > 0.9085

    names = list(pool)
    masks = np.column_stack([pool[n].to_numpy(bool) for n in names])
    feature_of = [n.split(">")[0].split("<")[0].split("==")[0] for n in names]

    periods = {
        "is": d["date"] < "2022-01-01",
        "oos": (d["date"] >= "2022-01-01") & (d["date"] < "2025-09-21"),
        "q4": (d["date"] >= "2025-09-21") & (d["date"] < "2026-01-01"),
        "y26": (d["date"] >= "2026-01-01") & (d["date"] <= "2026-09-15"),
        "m12": (d["date"] >= "2025-09-21") & (d["date"] <= "2026-09-15"),
    }
    pmasks = {k: v.to_numpy(bool) for k, v in periods.items()}

    rows = []
    seen = set()
    attempts = 0
    while len(rows) < 1000 and attempts < 50000:
        attempts += 1
        k = RNG.choice((2, 3, 4))
        idx = tuple(sorted(RNG.sample(range(len(names)), k)))
        if idx in seen:
            continue
        feats = [feature_of[i] for i in idx]
        if len(set(feats)) != len(feats):
            continue
        m = masks[:, idx].all(axis=1)
        if m.sum() < 40 or (m & pmasks["oos"]).sum() < 25 or (m & pmasks["y26"]).sum() < 12:
            continue
        seen.add(idx)
        out = {"rule": " & ".join(names[i] for i in idx)}
        for label, pm in pmasks.items():
            n, avg, t, win = stats(d[pm & m])
            out[f"{label}_n"] = n
            out[f"{label}_R"] = avg
            out[f"{label}_t"] = t
            out[f"{label}_win"] = win
        bal, dd = equity(d[pmasks["m12"] & m], 0.03)
        out["m12_bal30"] = bal
        out["m12_dd30"] = dd
        out["score"] = min(out["oos_R"], out["m12_R"])
        rows.append(out)

    df = pd.DataFrame(rows)
    df = df.sort_values("score", ascending=False)
    df.to_csv(OUT / "combos_1000.csv", index=False)
    cols = [
        "rule", "oos_n", "oos_R", "oos_t", "q4_n", "q4_R", "y26_n", "y26_R",
        "m12_n", "m12_R", "m12_bal30", "m12_dd30", "score",
    ]
    print("attempts", attempts, "combos", len(df))
    print(df[cols].head(30).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
