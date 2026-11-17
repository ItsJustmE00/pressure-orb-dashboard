from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("out_orb_entry_features")
OUT.mkdir(exist_ok=True)


def load_bars(paths):
    frames = []
    for p in paths:
        df = pd.read_parquet(p)
        df["time"] = pd.to_datetime(df["time"], utc=True)
        frames.append(df[["time", "open", "high", "low", "close", "tick_volume", "spread"]])
    d = pd.concat(frames, ignore_index=True).sort_values("time").drop_duplicates("time", keep="last")
    return d.reset_index(drop=True)


def load_trades():
    a = pd.read_csv("out_nas100_orb_9y_targets/trades_r1_t3.0.csv")
    b = pd.read_csv("out_nas100_orb_mt5_targets/trades_r1_t3.0.csv")
    t = pd.concat([a, b], ignore_index=True)
    t["date"] = pd.to_datetime(t["date"]).dt.date.astype(str)
    t = t.drop_duplicates("date", keep="last").sort_values("entry_time").reset_index(drop=True)
    t["entry_time"] = pd.to_datetime(t["entry_time"], utc=True)
    keep = ["date", "entry_time", "side", "entry", "stop", "target", "exit", "reason",
            "stop_points", "range_bars", "target_r", "r_multiple", "pnl"]
    return t[keep]


def main():
    bars = load_bars([
        "data_live/nas100_m15_kaggle_utc.parquet",
        "data_live/nas100_m15.parquet",
    ])
    b = bars.copy()
    b["ny"] = b["time"].dt.tz_convert("America/New_York")
    b["ny_date"] = b["ny"].dt.date
    b["utc_date"] = b["time"].dt.date
    b["ny_min"] = b["ny"].dt.hour * 60 + b["ny"].dt.minute
    b["available"] = b["time"] + pd.Timedelta(minutes=15)
    b["bar_range"] = b["high"] - b["low"]
    b["body"] = (b["close"] - b["open"]).abs()
    b["body_ratio"] = b["body"] / b["bar_range"].replace(0, np.nan)
    b["close_pos"] = (b["close"] - b["low"]) / b["bar_range"].replace(0, np.nan)
    b["upper_wick"] = (b["high"] - b[["open", "close"]].max(axis=1)) / b["bar_range"].replace(0, np.nan)
    b["lower_wick"] = (b[["open", "close"]].min(axis=1) - b["low"]) / b["bar_range"].replace(0, np.nan)
    prev_close = b["close"].shift(1)
    tr = pd.concat([
        b["bar_range"],
        (b["high"] - prev_close).abs(),
        (b["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    b["atr14"] = tr.rolling(14).mean()
    b["vol20"] = b["tick_volume"].rolling(20).mean()
    b["vol_ratio"] = b["tick_volume"] / b["vol20"].replace(0, np.nan)
    b["range_atr_bar"] = b["bar_range"] / b["atr14"].replace(0, np.nan)
    b["body_atr"] = b["body"] / b["atr14"].replace(0, np.nan)
    b["ema20"] = b["close"].ewm(span=20, adjust=False).mean()
    b["ema50"] = b["close"].ewm(span=50, adjust=False).mean()
    b["ema200"] = b["close"].ewm(span=200, adjust=False).mean()
    b["trend_m15"] = (b["ema20"] - b["ema50"]) / b["close"]
    b["above200"] = (b["close"] > b["ema200"]).astype(int)
    delta = b["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    b["rsi14"] = 100 - 100 / (1 + rs)
    b["mom3"] = b["close"].pct_change(3)
    b["mom6"] = b["close"].pct_change(6)
    b["bar_ret"] = b["close"].pct_change()
    b["tp"] = (b["high"] + b["low"] + b["close"]) / 3.0
    b["pv"] = b["tp"] * b["tick_volume"]
    rth = (b["ny_min"] >= 570) & (b["ny_min"] < 960)
    b["rth"] = rth
    b["cum_pv"] = b["pv"].where(rth).groupby(b["ny_date"]).cumsum()
    b["cum_vol"] = b["tick_volume"].where(rth).groupby(b["ny_date"]).cumsum()
    b["vwap"] = b["cum_pv"] / b["cum_vol"].replace(0, np.nan)

    cols = [
        "available", "open", "high", "low", "close", "tick_volume", "spread",
        "bar_range", "body_ratio", "close_pos", "upper_wick", "lower_wick",
        "atr14", "vol20", "vol_ratio", "range_atr_bar", "body_atr",
        "ema20", "ema50", "ema200", "trend_m15", "above200", "rsi14",
        "mom3", "mom6", "bar_ret", "vwap",
    ]
    feat = b[cols].copy()
    feat = feat.rename(columns={
        "open": "prev_open", "high": "prev_high_bar", "low": "prev_low_bar", "close": "prev_close_bar",
        "tick_volume": "prev_volume", "spread": "prev_spread",
        "body_ratio": "prev_body_ratio", "close_pos": "prev_close_pos",
        "upper_wick": "prev_upper_wick", "lower_wick": "prev_lower_wick",
        "range_atr_bar": "prev_range_atr", "body_atr": "prev_body_atr",
        "vol_ratio": "prev_vol_ratio", "atr14": "prev_atr", "rsi14": "prev_rsi",
        "vol20": "prev_vol20_bar", "trend_m15": "prev_trend_m15",
        "above200": "prev_above200", "mom3": "prev_mom3", "mom6": "prev_mom6",
        "bar_ret": "prev_bar_ret",
    })

    t = load_trades()
    t = pd.merge_asof(t, feat, left_on="entry_time", right_on="available", direction="backward")

    ors = b[(b["ny_min"] == 570)].copy()
    ors = ors[[
        "ny_date", "open", "high", "low", "close", "tick_volume", "vol20", "atr14",
        "body_ratio", "close_pos", "upper_wick", "lower_wick", "vol_ratio",
    ]].rename(columns={
        "open": "or_open", "high": "or_high", "low": "or_low", "close": "or_close",
        "tick_volume": "or_volume", "vol20": "or_vol20", "atr14": "or_atr14",
        "body_ratio": "or_body_ratio", "close_pos": "or_close_pos",
        "upper_wick": "or_upper_wick", "lower_wick": "or_lower_wick",
        "vol_ratio": "or_vol_ratio",
    })
    t["ny_date_obj"] = pd.to_datetime(t["date"]).dt.date
    t = t.merge(ors, left_on="ny_date_obj", right_on="ny_date", how="left", suffixes=("", "_or"))

    daily = b.groupby("utc_date").agg(
        d_open=("open", "first"), d_high=("high", "max"),
        d_low=("low", "min"), d_close=("close", "last"),
    ).reset_index()
    daily["d_range"] = daily["d_high"] - daily["d_low"]
    daily["day_ret"] = daily["d_close"] / daily["d_open"] - 1.0
    daily["day_range_pct"] = daily["d_range"] / daily["d_open"]
    daily["prev_high"] = daily["d_high"].shift(1)
    daily["prev_low"] = daily["d_low"].shift(1)
    daily["prev_close"] = daily["d_close"].shift(1)
    daily["prev_range"] = daily["d_range"].shift(1)
    daily["prev_day_ret"] = daily["day_ret"].shift(1)
    daily["prev_day_range_pct"] = daily["day_range_pct"].shift(1)
    daily["atr14_pct"] = daily["day_range_pct"].rolling(14).mean().shift(1)
    daily["ema20d"] = daily["d_close"].ewm(span=20, adjust=False).mean().shift(1)
    daily["ema50d"] = daily["d_close"].ewm(span=50, adjust=False).mean().shift(1)
    daily["ema200d"] = daily["d_close"].ewm(span=200, adjust=False).mean().shift(1)
    daily["trend_daily"] = (daily["ema20d"] - daily["ema50d"]) / daily["d_close"].shift(1)
    daily["above200d"] = (daily["d_close"].shift(1) > daily["ema200d"]).astype(int)
    daily["gap_pct"] = daily["d_open"] / daily["prev_close"] - 1.0
    t = t.merge(daily, left_on="ny_date_obj", right_on="utc_date", how="left", suffixes=("", "_daily"))

    t["range_width"] = t["stop_points"]
    t["range_atr"] = t["range_width"] / t["or_atr14"]
    t["range_pct"] = t["range_width"] / t["entry"]
    t["breakout_strength"] = np.where(
        t["side"].eq("long"),
        (t["entry"] - t["or_high"]) / t["range_width"],
        (t["or_low"] - t["entry"]) / t["range_width"],
    )
    t["breakout_strength_atr"] = np.where(
        t["side"].eq("long"),
        (t["entry"] - t["or_high"]) / t["or_atr14"],
        (t["or_low"] - t["entry"]) / t["or_atr14"],
    )
    t["entry_vs_vwap_atr"] = (t["entry"] - t["vwap"]) / t["or_atr14"]
    t["entry_vs_or_mid_atr"] = (t["entry"] - (t["or_high"] + t["or_low"]) / 2.0) / t["or_atr14"]
    t["dist_prev_high_atr"] = (t["entry"] - t["prev_high"]) / t["or_atr14"]
    t["dist_prev_low_atr"] = (t["entry"] - t["prev_low"]) / t["or_atr14"]
    t["dist_prev_close_atr"] = (t["entry"] - t["prev_close"]) / t["or_atr14"]
    t["range_vs_prev_range"] = t["range_width"] / t["prev_range"]
    t["spread_atr"] = t["prev_spread"] * 0.01 / t["or_atr14"]
    t["delay_min"] = (t["entry_time"].dt.tz_convert("America/New_York").dt.hour * 60
                      + t["entry_time"].dt.tz_convert("America/New_York").dt.minute - 570)
    t["dow"] = pd.to_datetime(t["date"]).dt.dayofweek
    t["long"] = (t["side"] == "long").astype(int)
    t["range_pct_rank60"] = t["range_width"].rolling(60, min_periods=20).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False)
    t["win"] = (t["r_multiple"] > 0).astype(int)
    t["target_hit"] = (t["reason"] == "target").astype(int)

    keep = [
        "date", "entry_time", "side", "long", "entry", "stop", "target", "exit", "reason",
        "r_multiple", "win", "target_hit", "stop_points", "range_width", "delay_min", "dow",
        "breakout_strength", "breakout_strength_atr", "range_atr", "range_pct",
        "entry_vs_vwap_atr", "entry_vs_or_mid_atr", "dist_prev_high_atr", "dist_prev_low_atr",
        "dist_prev_close_atr", "range_vs_prev_range", "range_pct_rank60", "spread_atr",
        "or_body_ratio", "or_close_pos", "or_upper_wick", "or_lower_wick", "or_vol_ratio",
        "prev_body_ratio", "prev_close_pos", "prev_upper_wick", "prev_lower_wick",
        "prev_range_atr", "prev_body_atr", "prev_vol_ratio", "prev_vol20_bar",
        "prev_atr", "prev_spread", "prev_close_bar", "prev_high_bar", "prev_low_bar",
        "prev_rsi", "prev_trend_m15", "prev_above200", "prev_mom3", "prev_mom6", "prev_bar_ret",
        "trend_daily", "above200d", "gap_pct", "prev_day_ret", "prev_day_range_pct",
        "atr14_pct",
    ]
    keep = [c for c in keep if c in t.columns]
    t[keep].to_csv(OUT / "nas100_entry_features.csv", index=False)
    print("rows", len(t), "cols", len(keep))
    print(t[keep].head().to_string())


if __name__ == "__main__":
    main()
