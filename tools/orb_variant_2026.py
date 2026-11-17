import pandas as pd


def m(x):
    x = pd.Series(x).dropna().to_numpy(float)
    if len(x) < 5:
        return len(x), float("nan"), float("nan")
    return len(x), float(x.mean()), float(x.mean() / (x.std(ddof=1) / len(x) ** 0.5))


def sim(trades, risk=0.015, start=57000.0):
    eq = start
    peak = start
    dd = 0.0
    for _, t in trades.sort_values(["date", "entry_time"]).iterrows():
        eq *= 1.0 + risk * float(t["r_multiple"])
        peak = max(peak, eq)
        dd = max(dd, 1.0 - eq / peak)
    return len(trades), (eq / start - 1) * 100, dd * 100, eq


nas = pd.read_csv("out_orb_filter_scan/nas100_trades_features.csv")
us30 = pd.read_csv("out_orb_filter_scan/us30_trades_features.csv")
for df in (nas, us30):
    df["date"] = pd.to_datetime(df["date"]).dt.date
qn = nas[nas["date"] < pd.Timestamp("2022-01-01").date()]["trend_daily"].quantile(0.2)
qr = nas[nas["date"] < pd.Timestamp("2022-01-01").date()]["rsi14"].quantile(0.6)
qu = us30[us30["date"] < pd.Timestamp("2022-01-01").date()]["range_pct_rank60"].quantile(0.2)
print("thresholds", qn, qr, qu)
variants = {
    "nas_trend": nas[(nas["side"] == "long") & (nas["trend_daily"] < qn)],
    "nas_trend_rsi": nas[(nas["side"] == "long") & (nas["trend_daily"] < qn) & (nas["rsi14"] > qr)],
    "us30_range": us30[us30["range_pct_rank60"] < qu],
    "us30_range_long": us30[(us30["side"] == "long") & (us30["range_pct_rank60"] < qu)],
    "us30_range_rsi": us30[(us30["range_pct_rank60"] < qu) & (us30["rsi14"] > qr)],
}
for name, t in variants.items():
    print("\n", name)
    for label, s, e in [
        ("2026_tester", pd.Timestamp("2026-01-01").date(), pd.Timestamp("2026-09-16").date()),
        ("recent_1", pd.Timestamp("2025-09-01").date(), pd.Timestamp("2026-03-01").date()),
        ("recent_2", pd.Timestamp("2026-03-01").date(), pd.Timestamp("2026-12-31").date()),
        ("recent_all", pd.Timestamp("2025-09-01").date(), pd.Timestamp("2026-12-31").date()),
        ("oos", pd.Timestamp("2022-01-01").date(), pd.Timestamp("2025-10-01").date()),
    ]:
        part = t[(t["date"] >= s) & (t["date"] < e)]
        n, avg, tv = m(part["r_multiple"])
        _, ret, dd, eq = sim(part, 0.015)
        print(f"  {label:12s} n={n:3d} avgR={avg:+.3f} t={tv:+.2f} ret1.5%={ret:+.1f}% dd={dd:.1f}%")

print("\nportfolios 2026 at 1.5%")
for combo in [
    ("nas_trend", "us30_range"),
    ("nas_trend_rsi", "us30_range"),
    ("nas_trend", "us30_range_long"),
    ("nas_trend_rsi", "us30_range_long"),
]:
    t = pd.concat([variants[c] for c in combo], ignore_index=True)
    part = t[(t["date"] >= pd.Timestamp("2026-01-01").date()) & (t["date"] < pd.Timestamp("2026-09-16").date())]
    n, avg, tv = m(part["r_multiple"])
    _, ret, dd, eq = sim(part, 0.015)
    print(f"{'+'.join(combo):35s} n={n:3d} avgR={avg:+.3f} ret={ret:+.1f}% dd={dd:.1f}% end={eq:,.0f}")
