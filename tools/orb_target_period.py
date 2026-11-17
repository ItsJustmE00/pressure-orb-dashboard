import pandas as pd


def m(x):
    x = pd.Series(x).dropna().to_numpy(float)
    if len(x) < 5:
        return len(x), float("nan"), float("nan")
    return len(x), float(x.mean()), float(x.mean() / (x.std(ddof=1) / len(x) ** 0.5))


def sim(trades, risk, start=57000.0):
    eq = start
    peak = start
    dd = 0.0
    daily = []
    for d, g in trades.sort_values(["date", "entry_time"]).groupby("date", sort=True):
        d0 = eq
        for _, t in g.iterrows():
            eq *= 1.0 + risk * float(t["r_multiple"])
            peak = max(peak, eq)
            dd = max(dd, 1.0 - eq / peak)
        daily.append(eq - d0)
    return eq, dd, sum(daily) / len(daily) if daily else 0.0, len(daily)


nas = pd.read_csv("out_orb_filter_scan/nas100_trades_features.csv")
us30 = pd.read_csv("out_orb_filter_scan/us30_trades_features.csv")
for df in (nas, us30):
    df["date"] = pd.to_datetime(df["date"]).dt.date
qn = nas[nas["date"] < pd.Timestamp("2022-01-01").date()]["trend_daily"].quantile(0.2)
qu = us30[us30["date"] < pd.Timestamp("2022-01-01").date()]["range_pct_rank60"].quantile(0.2)
a = nas[(nas["side"] == "long") & (nas["trend_daily"] < qn)]
b = us30[us30["range_pct_rank60"] < qu]
p = pd.concat([a, b], ignore_index=True)
periods = {
    "2026_tester": (pd.Timestamp("2026-01-01").date(), pd.Timestamp("2026-09-16").date()),
    "recent_all": (pd.Timestamp("2025-09-01").date(), pd.Timestamp("2026-12-31").date()),
    "oos": (pd.Timestamp("2022-01-01").date(), pd.Timestamp("2025-10-01").date()),
    "is": (pd.Timestamp("2016-01-01").date(), pd.Timestamp("2022-01-01").date()),
}
for label, (s, e) in periods.items():
    part = p[(p["date"] >= s) & (p["date"] < e)]
    n, avg, t = m(part["r_multiple"])
    print(f"\n{label} n={n} avgR={avg:+.3f} t={t:+.2f}")
    for risk in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]:
        eq, dd, avg_day, days = sim(part, risk / 100.0)
        print(f"  risk={risk:.1f}% end={eq:,.0f} ret={100*(eq/57000-1):+.1f}% dd={dd*100:.1f}% avg_trade_day={avg_day:,.0f} days={days}")
