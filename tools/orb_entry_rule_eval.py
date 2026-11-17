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


def equity(part, risk):
    bal = 57000.0
    peak = bal
    dd = 0.0
    for r in part.sort_values("date")["r_multiple"]:
        bal *= 1.0 + risk * r
        peak = max(peak, bal)
        dd = max(dd, 1.0 - bal / peak)
    return bal, dd


def periods(d):
    return {
        "is": d[d["date"] < pd.Timestamp("2022-01-01").date()],
        "oos": d[(d["date"] >= pd.Timestamp("2022-01-01").date()) & (d["date"] < pd.Timestamp("2025-10-01").date())],
        "rec": d[d["date"] >= pd.Timestamp("2025-09-01").date()],
        "y26": d[d["date"] >= pd.Timestamp("2026-01-01").date()],
    }


def main():
    d = pd.read_csv("out_orb_entry_features/nas100_entry_features.csv")
    d["date"] = pd.to_datetime(d["date"]).dt.date
    d = d[d["side"].eq("long") & (d["trend_daily"] < 0.002378)].copy()

    c = {
        "B": d["or_close_pos"] > 0.8044,
        "C": d["prev_rsi"] > 59.81,
        "D": d["dist_prev_high_atr"] > 2.08,
        "E": d["prev_mom6"] > 0.00123,
        "F": d["prev_upper_wick"] < 0.07838,
        "G": d["prev_close_pos"] > 0.9085,
        "H": d["prev_above200"] == 1,
        "I": d["or_upper_wick"] < 0.1923,
        "J": d["dist_prev_low_atr"] > 9.38,
        "K": d["range_atr"] > 1.837,
    }
    rules = {
        "base": pd.Series(True, index=d.index),
        "B": c["B"], "C": c["C"], "D": c["D"], "E": c["E"], "F": c["F"],
        "G": c["G"], "H": c["H"], "I": c["I"], "J": c["J"], "K": c["K"],
        "B+E": c["B"] & c["E"], "B+E+H": c["B"] & c["E"] & c["H"],
        "B+E+C": c["B"] & c["E"] & c["C"], "B+E+D": c["B"] & c["E"] & c["D"],
        "B+E+F": c["B"] & c["E"] & c["F"], "B+E+G": c["B"] & c["E"] & c["G"],
        "E+F": c["E"] & c["F"], "E+F+H": c["E"] & c["F"] & c["H"],
        "E+G": c["E"] & c["G"], "E+G+H": c["E"] & c["G"] & c["H"],
        "D+C": c["D"] & c["C"], "D+C+H": c["D"] & c["C"] & c["H"],
        "D+E": c["D"] & c["E"], "D+E+H": c["D"] & c["E"] & c["H"],
        "B+G": c["B"] & c["G"], "B+G+H": c["B"] & c["G"] & c["H"],
        "I+E": c["I"] & c["E"], "I+E+H": c["I"] & c["E"] & c["H"],
        "F+H": c["F"] & c["H"], "G+H": c["G"] & c["H"],
        "B+H": c["B"] & c["H"], "E+H": c["E"] & c["H"],
        "C+H": c["C"] & c["H"], "D+H": c["D"] & c["H"],
        "B+E+D+?": c["B"] & c["E"] & c["D"],
        "B+E+C+H": c["B"] & c["E"] & c["C"] & c["H"],
        "B+E+D+H": c["B"] & c["E"] & c["D"] & c["H"],
        "E+F+G": c["E"] & c["F"] & c["G"],
        "E+F+C": c["E"] & c["F"] & c["C"],
        "B+E+I": c["B"] & c["E"] & c["I"],
        "B+E+J": c["B"] & c["E"] & c["J"],
        "B+E+K": c["B"] & c["E"] & c["K"],
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
            bal, dd = equity(part, 0.025)
            out[f"{label}_bal25"] = bal
            out[f"{label}_dd25"] = dd
        rows.append(out)
    df = pd.DataFrame(rows)
    df["score"] = df[["is_R", "oos_R", "rec_R"]].min(axis=1)
    df = df.sort_values("score", ascending=False)
    df.to_csv(OUT / "rule_eval.csv", index=False)
    cols = ["rule", "n_all", "is_n", "is_R", "is_t", "oos_n", "oos_R", "oos_t",
            "rec_n", "rec_R", "rec_t", "y26_n", "y26_R", "y26_bal25", "y26_dd25", "score"]
    print(df[cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
