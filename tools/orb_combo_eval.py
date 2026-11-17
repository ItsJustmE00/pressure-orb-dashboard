import argparse
import itertools
from pathlib import Path

import pandas as pd


def m(x):
    x = pd.Series(x).dropna().to_numpy(float)
    if len(x) < 5:
        return {"n": len(x), "avg": float("nan"), "t": float("nan"), "win": float("nan")}
    mean = float(x.mean())
    std = float(x.std(ddof=1))
    return {
        "n": int(len(x)),
        "avg": mean,
        "t": mean / (std / (len(x) ** 0.5)) if std > 0 else 0.0,
        "win": float((x > 0).mean()),
    }


def periods(df):
    return {
        "is": df[df["date"] < pd.Timestamp("2022-01-01").date()],
        "oos": df[(df["date"] >= pd.Timestamp("2022-01-01").date()) & (df["date"] < pd.Timestamp("2025-10-01").date())],
        "rec": df[df["date"] >= pd.Timestamp("2025-09-01").date()],
    }


def make_conditions(df, isdf):
    q = {}
    for f in ["vol20", "trend_daily", "range_pct_rank60", "range_atr", "atr14_pct", "rsi14"]:
        q[f] = isdf[f].quantile([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]).to_dict()
    conds = {
        "vol_mid": lambda d: (d["vol20"] >= q["vol20"][0.2]) & (d["vol20"] <= q["vol20"][0.8]),
        "vol_low": lambda d: d["vol20"] < q["vol20"][0.2],
        "vol_high": lambda d: d["vol20"] > q["vol20"][0.8],
        "trend_low": lambda d: d["trend_daily"] < q["trend_daily"][0.2],
        "trend_high": lambda d: d["trend_daily"] > q["trend_daily"][0.8],
        "range_rank_low": lambda d: d["range_pct_rank60"] < q["range_pct_rank60"][0.2],
        "range_rank_high": lambda d: d["range_pct_rank60"] > q["range_pct_rank60"][0.8],
        "range_atr_high": lambda d: d["range_atr"] > q["range_atr"][0.8],
        "range_atr_low": lambda d: d["range_atr"] < q["range_atr"][0.2],
        "atr_low_exclude": lambda d: d["atr14_pct"] > q["atr14_pct"][0.2],
        "rsi_high": lambda d: d["rsi14"] > q["rsi14"][0.6],
        "rsi_low": lambda d: d["rsi14"] < q["rsi14"][0.4],
    }
    return conds


def eval_combo(df, cond, label, rows):
    ps = periods(df[cond])
    out = {"combo": label}
    for name, part in ps.items():
        s = m(part["r_multiple"])
        out[f"{name}_n"] = s["n"]
        out[f"{name}_R"] = s["avg"]
        out[f"{name}_t"] = s["t"]
    if out["is_n"] >= 50 and out["oos_n"] >= 30 and out["rec_n"] >= 10:
        out["score"] = min(out["is_R"], out["oos_R"], out["rec_R"])
        rows.append(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="out_orb_filter_scan")
    ap.add_argument("--out", default="out_orb_combo_eval")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    all_rows = []
    for sym in ["nas100", "us30"]:
        df = pd.read_csv(Path(args.dir) / f"{sym}_trades_features.csv")
        df["date"] = pd.to_datetime(df["date"]).dt.date
        isdf = df[df["date"] < pd.Timestamp("2022-01-01").date()]
        conds = make_conditions(df, isdf)
        rows = []
        eval_combo(df, pd.Series(True, index=df.index), "baseline", rows)
        for side in ["all", "long", "short"]:
            base = pd.Series(True, index=df.index) if side == "all" else df["side"].eq(side)
            for name, fn in conds.items():
                eval_combo(df, base & fn(df), f"{side}+{name}", rows)
            for (n1, f1), (n2, f2) in itertools.combinations(conds.items(), 2):
                eval_combo(df, base & f1(df) & f2(df), f"{side}+{n1}+{n2}", rows)
        r = pd.DataFrame(rows)
        r.insert(0, "symbol", sym)
        all_rows.append(r)
        r = r.sort_values("score", ascending=False)
        r.to_csv(out / f"{sym}_combos.csv", index=False)
        print(f"\n=== {sym} top 20 by min-period avgR ===")
        cols = ["combo", "is_n", "is_R", "is_t", "oos_n", "oos_R", "oos_t", "rec_n", "rec_R", "rec_t"]
        print(r[cols].head(20).round(3).to_string(index=False))
    pd.concat(all_rows, ignore_index=True).to_csv(out / "all_combos.csv", index=False)


if __name__ == "__main__":
    main()
