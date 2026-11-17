import pandas as pd
from pathlib import Path


def m(x):
    x = pd.Series(x).dropna().to_numpy(float)
    if len(x) < 5:
        return len(x), float("nan"), float("nan"), float("nan")
    mean = float(x.mean())
    std = float(x.std(ddof=1))
    t = mean / (std / (len(x) ** 0.5)) if std > 0 else 0.0
    return len(x), mean, t, float((x > 0).mean())


def report(df, name, feature, bins=5):
    d = df.copy()
    d["bin"] = pd.qcut(d[feature], bins, labels=False, duplicates="drop")
    print(f"\n=== {name} {feature} by side ===")
    rows = []
    for (b, side), g in d.groupby(["bin", "side"]):
        for period, part in [
            ("is", g[g["date"] < pd.Timestamp("2022-01-01").date()]),
            ("oos", g[(g["date"] >= pd.Timestamp("2022-01-01").date()) & (g["date"] < pd.Timestamp("2025-10-01").date())]),
            ("recent", g[g["date"] >= pd.Timestamp("2025-09-01").date()]),
        ]:
            n, avg, t, win = m(part["r_multiple"])
            if n:
                rows.append((b, side, period, n, avg, t, win))
    for r in rows:
        print(f"bin={r[0]} {r[1]:5s} {r[2]:6s} n={r[3]:4d} avgR={r[4]:+.3f} t={r[5]:+.2f} win={r[6]*100:.1f}%")


def main():
    for name in ["nas100", "us30"]:
        df = pd.read_csv(Path("out_orb_filter_scan") / f"{name}_trades_features.csv")
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df["side"] = df["side"].astype(str)
        print(f"\n{name} n={len(df)}")
        for feature in ["trend_daily", "range_pct_rank60", "range_atr", "atr_pct", "rsi14", "vol20"]:
            report(df, name, feature)
        print("\nSimple conditions:")
        conds = {
            "trend_low": df["trend_daily"] < df["trend_daily"].quantile(0.2),
            "range_rank_low": df["range_pct_rank60"] < df["range_pct_rank60"].quantile(0.2),
            "range_atr_high": df["range_atr"] > df["range_atr"].quantile(0.8),
            "atr_high": df["atr14_pct"] > df["atr14_pct"].quantile(0.8),
            "rsi_high": df["rsi14"] > df["rsi14"].quantile(0.6),
            "vol_mid": (df["vol20"] > df["vol20"].quantile(0.2)) & (df["vol20"] < df["vol20"].quantile(0.8)),
        }
        for cname, cond in conds.items():
            for side in ["all", "long", "short"]:
                part = df[cond & ((df["side"] == side) if side != "all" else True)]
                out = []
                for period, q in [
                    ("is", part[part["date"] < pd.Timestamp("2022-01-01").date()]),
                    ("oos", part[(part["date"] >= pd.Timestamp("2022-01-01").date()) & (part["date"] < pd.Timestamp("2025-10-01").date())]),
                    ("rec", part[part["date"] >= pd.Timestamp("2025-09-01").date()]),
                ]:
                    n, avg, t, win = m(q["r_multiple"])
                    out.append(f"{period}:n{n}/R{avg:+.2f}/t{t:+.1f}")
                print(f"{cname:15s} {side:5s} " + " ".join(out))


if __name__ == "__main__":
    main()
