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
        "oos": d[(d["date"] >= pd.Timestamp("2022-01-01").date()) & (d["date"] < pd.Timestamp("2025-09-21").date())],
        "q4": d[(d["date"] >= pd.Timestamp("2025-09-21").date()) & (d["date"] < pd.Timestamp("2026-01-01").date())],
        "y26": d[(d["date"] >= pd.Timestamp("2026-01-01").date()) & (d["date"] <= pd.Timestamp("2026-09-15").date())],
        "m12": d[(d["date"] >= pd.Timestamp("2025-09-21").date()) & (d["date"] <= pd.Timestamp("2026-09-15").date())],
    }


def main():
    d = pd.read_csv("out_orb_entry_features/nas100_entry_features.csv")
    d["date"] = pd.to_datetime(d["date"]).dt.date
    d = d[d["side"].eq("short")].copy()
    c = {
        "S_OR": d["or_close_pos"] < 0.1956,
        "S_MOM": d["prev_mom6"] < -0.00123,
        "S_TREND2": d["trend_daily"] > -0.002378,
        "S_TREND4": d["trend_daily"] > -0.00425,
        "S_PREVCLOSE": d["prev_close_pos"] < 0.0915,
        "S_WICK": d["prev_lower_wick"] < 0.07838,
        "S_ABOVE200": d["prev_above200"] == 0,
    }
    rules = {
        "short_base": pd.Series(True, index=d.index),
        "S_OR": c["S_OR"],
        "S_MOM": c["S_MOM"],
        "S_TREND2": c["S_TREND2"],
        "S_TREND4": c["S_TREND4"],
        "S_OR+MOM": c["S_OR"] & c["S_MOM"],
        "S_OR+MOM+TREND2": c["S_OR"] & c["S_MOM"] & c["S_TREND2"],
        "S_OR+MOM+TREND4": c["S_OR"] & c["S_MOM"] & c["S_TREND4"],
        "S_OR+MOM+PREVCLOSE": c["S_OR"] & c["S_MOM"] & c["S_PREVCLOSE"],
        "S_OR+MOM+WICK": c["S_OR"] & c["S_MOM"] & c["S_WICK"],
        "S_OR+MOM+ABOVE200": c["S_OR"] & c["S_MOM"] & c["S_ABOVE200"],
        "S_MOM+TREND2": c["S_MOM"] & c["S_TREND2"],
        "S_OR+TREND2": c["S_OR"] & c["S_TREND2"],
    }
    rows = []
    for name, cond in rules.items():
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
    df["score"] = df[["oos_R", "y26_R"]].min(axis=1)
    df = df.sort_values("score", ascending=False)
    df.to_csv(OUT / "short_rules.csv", index=False)
    cols = ["rule", "n_all", "oos_n", "oos_R", "q4_n", "q4_R", "y26_n", "y26_R", "y26_win", "m12_n", "m12_R"]
    print(df[cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
