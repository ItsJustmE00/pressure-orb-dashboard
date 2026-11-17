import pandas as pd


def m(x):
    x = pd.Series(x).dropna().to_numpy(float)
    if len(x) < 5:
        return len(x), float("nan"), float("nan")
    return len(x), float(x.mean()), float(x.mean() / (x.std(ddof=1) / len(x) ** 0.5))


def main():
    nas = pd.read_csv("out_orb_filter_scan/nas100_trades_features.csv")
    us30 = pd.read_csv("out_orb_filter_scan/us30_trades_features.csv")
    for df in (nas, us30):
        df["date"] = pd.to_datetime(df["date"]).dt.date
    qn = nas[nas["date"] < pd.Timestamp("2022-01-01").date()]["trend_daily"].quantile(0.2)
    qu = us30[us30["date"] < pd.Timestamp("2022-01-01").date()]["range_pct_rank60"].quantile(0.2)
    print("thresholds", qn, qu)
    a = nas[(nas["side"] == "long") & (nas["trend_daily"] < qn)]
    b = us30[us30["range_pct_rank60"] < qu]
    periods = [
        ("recent_1", pd.Timestamp("2025-09-01").date(), pd.Timestamp("2026-03-01").date()),
        ("recent_2", pd.Timestamp("2026-03-01").date(), pd.Timestamp("2026-12-31").date()),
        ("recent_all", pd.Timestamp("2025-09-01").date(), pd.Timestamp("2026-12-31").date()),
    ]
    for name, df in [("nas_long_trend", a), ("us30_range_low", b), ("portfolio", pd.concat([a, b]))]:
        print("\n", name)
        for label, start, end in periods:
            part = df[(df["date"] >= start) & (df["date"] < end)]
            n, avg, t = m(part["r_multiple"])
            print(f"  {label:10s} n={n:3d} avgR={avg:+.3f} t={t:+.2f}")
        for label, start, end in [("is", pd.Timestamp("2016-01-01").date(), pd.Timestamp("2022-01-01").date()),
                                  ("oos", pd.Timestamp("2022-01-01").date(), pd.Timestamp("2025-10-01").date())]:
            part = df[(df["date"] >= start) & (df["date"] < end)]
            n, avg, t = m(part["r_multiple"])
            print(f"  {label:10s} n={n:3d} avgR={avg:+.3f} t={t:+.2f}")


if __name__ == "__main__":
    main()
