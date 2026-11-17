import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def load_bars(paths):
    frames = []
    for p in paths:
        df = pd.read_parquet(p)
        df["time"] = pd.to_datetime(df["time"], utc=True)
        frames.append(df[["time", "open", "high", "low", "close", "tick_volume", "spread"]])
    df = pd.concat(frames, ignore_index=True).sort_values("time").drop_duplicates("time", keep="last")
    return df.reset_index(drop=True)


def add_bar_features(bars):
    d = bars.copy()
    prev_close = d["close"].shift(1)
    tr = pd.concat([
        d["high"] - d["low"],
        (d["high"] - prev_close).abs(),
        (d["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    d["atr14"] = tr.rolling(14).mean().shift(1)
    d["ema20"] = d["close"].ewm(span=20, adjust=False).mean().shift(1)
    d["ema50"] = d["close"].ewm(span=50, adjust=False).mean().shift(1)
    d["ema200"] = d["close"].ewm(span=200, adjust=False).mean().shift(1)
    d["close_pre"] = d["close"].shift(1)
    delta = d["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    d["rsi14"] = (100 - 100 / (1 + rs)).shift(1)
    d["vol20"] = d["tick_volume"].rolling(20).mean().shift(1)
    d["bar_ret"] = d["close"].pct_change()
    return d


def add_daily_features(bars):
    d = bars.copy()
    d["ny"] = d["time"].dt.tz_convert("America/New_York")
    d["ny_date"] = d["ny"].dt.date
    d["ny_time"] = d["ny"].dt.time
    rows = []
    for day, g in d.groupby("ny_date", sort=True):
        rth = g[(g["ny_time"] >= pd.Timestamp("09:30").time()) & (g["ny_time"] < pd.Timestamp("16:00").time())]
        if len(rth) < 10:
            continue
        rows.append({
            "ny_date": day,
            "open": float(rth.iloc[0]["open"]),
            "close": float(rth.iloc[-1]["close"]),
            "high": float(rth["high"].max()),
            "low": float(rth["low"].min()),
        })
    x = pd.DataFrame(rows).sort_values("ny_date").reset_index(drop=True)
    x["day_ret"] = x["close"] / x["open"] - 1
    x["day_range_pct"] = (x["high"] - x["low"]) / x["open"]
    x["prev_close"] = x["close"].shift(1)
    x["prev_day_ret"] = x["day_ret"].shift(1)
    x["prev_day_range_pct"] = x["day_range_pct"].shift(1)
    x["atr14_pct"] = x["day_range_pct"].rolling(14).mean().shift(1)
    x["gap_pct"] = x["open"] / x["prev_close"] - 1
    x["ema20d"] = x["close"].ewm(span=20, adjust=False).mean().shift(1)
    x["ema50d"] = x["close"].ewm(span=50, adjust=False).mean().shift(1)
    x["ema200d"] = x["close"].ewm(span=200, adjust=False).mean().shift(1)
    x["trend_d"] = (x["ema20d"] - x["ema50d"]) / x["close"]
    return x


def enrich(trades, bars):
    b = add_bar_features(bars)
    b["ny"] = b["time"].dt.tz_convert("America/New_York")
    b["ny_date"] = b["ny"].dt.date
    daily = add_daily_features(bars)
    t = trades.copy()
    t["date"] = pd.to_datetime(t["date"]).dt.date
    t["ny_date"] = t["date"]
    t["entry_time"] = pd.to_datetime(t["entry_time"], utc=True)
    t = t.sort_values("entry_time").reset_index(drop=True)
    b = b.sort_values("time").reset_index(drop=True)
    cols = ["time", "atr14", "ema20", "ema50", "ema200", "close_pre", "rsi14", "vol20", "bar_ret"]
    t = pd.merge_asof(t, b[cols], left_on="entry_time", right_on="time", direction="backward")
    t = t.merge(daily, on="ny_date", how="left")
    t["range_width"] = t["stop_points"]
    t["range_atr"] = t["range_width"] / t["atr14"]
    t["range_pct"] = t["range_width"] / t["entry"]
    t["atr_pct"] = t["atr14"] / t["close_pre"]
    t["delay_min"] = (t["entry_time"].dt.tz_convert("America/New_York").dt.hour * 60
                      + t["entry_time"].dt.tz_convert("America/New_York").dt.minute
                      - (9 * 60 + 30 + 15 * t["range_bars"]))
    t["dow"] = pd.to_datetime(t["date"]).dt.dayofweek
    t["long"] = (t["side"] == "long").astype(int)
    t["range_rank"] = t.groupby("date")["range_width"].rank(pct=True)
    t["range_pct_rank60"] = t["range_width"].rolling(60, min_periods=20).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False)
    t["trend_m15"] = (t["ema20"] - t["ema50"]) / t["close_pre"]
    t["trend_daily"] = t["trend_d"]
    t["above200"] = (t["close_pre"] > t["ema200"]).astype(int)
    t["gap_abs"] = t["gap_pct"].abs()
    return t


def stat(x):
    x = pd.Series(x).dropna().to_numpy(float)
    if len(x) < 10:
        return {"n": len(x), "avg": np.nan, "t": np.nan, "win": np.nan}
    m = float(x.mean())
    s = float(x.std(ddof=1))
    return {"n": len(x), "avg": m, "t": m / (s / np.sqrt(len(x))) if s > 0 else 0.0, "win": float((x > 0).mean())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nas", default="data_live/nas100_m15_kaggle_utc.parquet,data_live/nas100_m15.parquet")
    ap.add_argument("--us30", default="data_live/us30_m15_kaggle_utc.parquet,data_live/us30_m15.parquet")
    ap.add_argument("--out", default="out_orb_filter_scan")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    configs = {
        "nas100": {
            "bars": args.nas.split(","),
            "trades": "out_nas100_orb_9y_targets/trades_r1_t3.0.csv",
            "recent": "out_nas100_orb_mt5_targets/trades_r1_t3.0.csv",
        },
        "us30": {
            "bars": args.us30.split(","),
            "trades": "out_us30_orb_9y/trades_r1_t3.0.csv",
            "recent": "out_us30_orb_recent/trades_r1_t3.0.csv",
        },
    }
    all_stats = []
    enriched = {}
    for name, cfg in configs.items():
        bars = load_bars(cfg["bars"])
        trades = pd.read_csv(cfg["trades"])
        if cfg.get("recent"):
            recent_path = Path(cfg["recent"])
            if recent_path.exists():
                recent = pd.read_csv(recent_path)
                trades = pd.concat([trades, recent], ignore_index=True)
                trades["date"] = pd.to_datetime(trades["date"]).dt.date.astype(str)
                trades = trades.drop_duplicates("date", keep="last")
        t = enrich(trades, bars)
        t.to_csv(out / f"{name}_trades_features.csv", index=False)
        enriched[name] = t
        print(f"\n{name}: {len(t)} trades {t['date'].min()} to {t['date'].max()}")
        for label, part in [
            ("is", t[t["date"] < pd.Timestamp("2022-01-01").date()]),
            ("oos", t[(t["date"] >= pd.Timestamp("2022-01-01").date()) & (t["date"] < pd.Timestamp("2025-10-01").date())]),
            ("recent", t[t["date"] >= pd.Timestamp("2025-09-01").date()]),
        ]:
            s = stat(part["r_multiple"])
            print(f"  {label:7s} n={s['n']:4d} avgR={s['avg']:+.3f} t={s['t']:+.2f} win={s['win']*100:.1f}%")
        features = ["range_atr", "range_pct", "atr_pct", "delay_min", "rsi14", "trend_m15",
                    "trend_daily", "above200", "gap_pct", "prev_day_ret", "prev_day_range_pct",
                    "atr14_pct", "range_pct_rank60", "vol20", "long", "dow"]
        for feature in features:
            t = enriched[name]
            try:
                t["bin"] = pd.qcut(t[feature], 5, labels=False, duplicates="drop")
            except ValueError:
                continue
            for b, g in t.groupby("bin"):
                for label, part in [
                    ("is", g[g["date"] < pd.Timestamp("2022-01-01").date()]),
                    ("oos", g[(g["date"] >= pd.Timestamp("2022-01-01").date()) & (g["date"] < pd.Timestamp("2025-10-01").date())]),
                    ("recent", g[g["date"] >= pd.Timestamp("2025-09-01").date()]),
                ]:
                    s = stat(part["r_multiple"])
                    if s["n"] >= 10:
                        all_stats.append({"symbol": name, "feature": feature, "bin": int(b), "period": label,
                                          **s, "feat_min": float(g[feature].min()), "feat_max": float(g[feature].max())})
    df = pd.DataFrame(all_stats)
    df.to_csv(out / "quintiles.csv", index=False)
    piv = df.pivot_table(index=["symbol", "feature", "bin"], columns="period", values="avg")
    print("\nQuintile avgR (is/oos/recent):")
    print(piv.round(3).to_string())
    (out / "quintiles.json").write_text(json.dumps(all_stats, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
