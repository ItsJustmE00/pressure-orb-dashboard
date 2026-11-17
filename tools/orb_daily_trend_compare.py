import pandas as pd

frames = []
for path in ["data_live/nas100_m15_kaggle_utc.parquet", "data_live/nas100_m15.parquet"]:
    d = pd.read_parquet(path)
    d["time"] = pd.to_datetime(d["time"], utc=True)
    frames.append(d[["time", "close"]])
b = pd.concat(frames, ignore_index=True).sort_values("time").drop_duplicates("time")
b["date"] = b["time"].dt.date
g = b.groupby("date", sort=True).agg(c=("close", "last")).reset_index()
g["date"] = pd.to_datetime(g["date"])
g["e20"] = g["c"].ewm(span=20, adjust=False).mean().shift(1)
g["e50"] = g["c"].ewm(span=50, adjust=False).mean().shift(1)
g["trend"] = (g["e20"] - g["e50"]) / g["c"].shift(1)
isd = g[g["date"] < "2022-01-01"]["trend"].dropna()
print("n", len(isd))
print(isd.quantile([0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]).round(6).to_string())
dates = pd.to_datetime([
    "2025-11-19", "2025-12-02", "2025-12-19", "2025-12-23", "2025-12-26",
    "2026-09-03", "2026-09-11", "2026-09-14",
])
print(g[g["date"].isin(dates)][["date", "trend"]].to_string(index=False))
