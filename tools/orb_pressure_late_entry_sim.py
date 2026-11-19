"""Simulate the live ORB Pressure rules and test late-entry / re-entry filters.

The live EA works tick by tick:
  * range = 09:30-09:45 NY M15 bar high/low;
  * entries only while price is beyond a range boundary;
  * pressure = last 3 *closed* M15 bars, threshold 0.60;
  * one position at a time, max 10 entries/day, target 2R, stop = opposite
    range boundary, safety close 22:55 NY.

With M15 OHLC data a tick-by-tick replay is impossible, so the model uses
these documented approximations:
  * a break entry fills at max(open, high) for BUY / min(open, low) for SELL;
  * a signal that only becomes valid on a bar close fills at the next bar open
    (the EA sends a market order on the first tick of the new bar);
  * exits on the entry bar are only checked when the entry is the bar open
    (gap entry, or next-open close entry); for an intrabar boundary entry the
    bar path is unknown, so exits start on the following bar;
  * stop/target gaps fill at the bar open;
  * the 22:55 safety close is approximated by the 22:45 bar close.

No MT5 connection is used: this is a pure historical study.
"""

import argparse
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

NY = ZoneInfo("America/New_York")
OUT = Path("out_orb_pressure_review")
COST_POINTS = 1.7
TARGET_R = 2.0
PRESSURE_BARS = 3
PRESSURE_MIN = 0.6
RANGE_START_MIN = 9 * 60 + 30
RANGE_END_MIN = 9 * 60 + 45
CLOSE_MIN = 23 * 60
SAFETY_MIN = 22 * 60 + 55
LAST_BAR_MIN = 22 * 60 + 45
MAX_TRADES_PER_DAY = 10


def load_bars(paths):
    frames = []
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            raise SystemExit(f"Fichier absent: {path}")
        frame = pd.read_parquet(path)
        frames.append(frame[["time", "open", "high", "low", "close"]])
    bars = pd.concat(frames, ignore_index=True)
    bars["time"] = pd.to_datetime(bars["time"], utc=True)
    bars = (
        bars.drop_duplicates(subset="time", keep="last")
        .sort_values("time")
        .reset_index(drop=True)
    )
    bars["ny"] = bars["time"].dt.tz_convert(NY)
    bars["ny_date"] = bars["ny"].dt.date
    bars["minute"] = bars["ny"].dt.hour * 60 + bars["ny"].dt.minute

    open_ = bars["open"].to_numpy(float)
    high = bars["high"].to_numpy(float)
    low = bars["low"].to_numpy(float)
    close = bars["close"].to_numpy(float)
    rng = high - low
    body = np.abs(close - open_)
    valid = (rng > 0.0) & (body > 0.0)
    bull = valid & (close > open_)
    bear = valid & (close < open_)
    upper = high - np.maximum(open_, close)
    lower = np.minimum(open_, close) - low

    contribution = np.zeros(len(bars), dtype=float)
    contribution[bull] = (body[bull] / rng[bull]) * (
        1.0 - upper[bull] / rng[bull]
    )
    contribution[bear] = -(body[bear] / rng[bear]) * (
        1.0 - lower[bear] / rng[bear]
    )

    contribution = pd.Series(contribution)
    counted = pd.Series(valid.astype(float))
    sum3 = contribution.rolling(PRESSURE_BARS, min_periods=PRESSURE_BARS).sum()
    count3 = counted.rolling(PRESSURE_BARS, min_periods=PRESSURE_BARS).sum()

    def normalized(values, counts):
        values = np.asarray(values, dtype=float)
        counts = np.asarray(counts, dtype=float)
        result = np.full(len(values), 0.5)
        mask = counts > 0
        result[mask] = np.clip((values[mask] / counts[mask] + 1.0) / 2.0, 0.0, 1.0)
        return result

    # Pressure available while a bar is forming: previous 3 closed bars.
    bars["buy_prev"] = normalized(sum3.shift(1), count3.shift(1))
    # Pressure available on the first tick after the bar closes.
    bars["buy_now"] = normalized(sum3, count3)
    bars["sell_prev"] = 1.0 - bars["buy_prev"]
    bars["sell_now"] = 1.0 - bars["buy_now"]
    return bars


def check_exit(position, index, open_, high, low):
    """Return (exit_price, reason) or (None, None). Stop first, gaps at open."""
    side = position["side"]
    stop = position["stop"]
    target = position["target"]
    bar_open = float(open_[index])
    bar_high = float(high[index])
    bar_low = float(low[index])

    if side == "BUY":
        if bar_open <= stop:
            return bar_open, "stop"
        if bar_open >= target:
            return bar_open, "target"
        if bar_low <= stop:
            return stop, "stop"
        if bar_high >= target:
            return target, "target"
    else:
        if bar_open >= stop:
            return bar_open, "stop"
        if bar_open <= target:
            return bar_open, "target"
        if bar_high >= stop:
            return stop, "stop"
        if bar_low <= target:
            return target, "target"
    return None, None


def build_trade(position, exit_price, exit_time, reason):
    direction = 1.0 if position["side"] == "BUY" else -1.0
    gross = direction * (exit_price - position["entry"])
    net = gross - COST_POINTS
    trade = dict(position)
    trade.update(
        {
            "exit": float(exit_price),
            "exit_time": exit_time,
            "reason": reason,
            "gross_points": float(gross),
            "net_points": float(net),
            "r_multiple": float(net / position["stop_distance"]),
            "win": bool(net > 0.0),
        }
    )
    return trade


def simulate(
    bars,
    max_extension=None,
    max_stop_ratio=None,
    max_trades=MAX_TRADES_PER_DAY,
    last_entry_min=SAFETY_MIN,
):
    open_ = bars["open"].to_numpy(float)
    high = bars["high"].to_numpy(float)
    low = bars["low"].to_numpy(float)
    close = bars["close"].to_numpy(float)
    minute = bars["minute"].to_numpy(int)
    times = bars["ny"].to_numpy()
    dates = bars["ny_date"].to_numpy()
    buy_prev = bars["buy_prev"].to_numpy(float)
    sell_prev = bars["sell_prev"].to_numpy(float)
    buy_now = bars["buy_now"].to_numpy(float)
    sell_now = bars["sell_now"].to_numpy(float)

    groups = {}
    for index, date in enumerate(dates):
        groups.setdefault(date, []).append(index)

    trades = []

    def filter_ok(entry, boundary, stop, width):
        extension = abs(entry - boundary)
        extension_ratio = extension / width if width > 0 else np.inf
        stop_distance = abs(entry - stop)
        stop_ratio = stop_distance / width if width > 0 else np.inf
        if stop_distance <= 0.0:
            return None
        if max_extension is not None and extension_ratio > max_extension:
            return None
        if max_stop_ratio is not None and stop_ratio > max_stop_ratio:
            return None
        return extension, extension_ratio, stop_distance, stop_ratio

    for date, indices in groups.items():
        indices = np.asarray(indices, dtype=int)
        day_minute = minute[indices]
        range_positions = np.flatnonzero(day_minute == RANGE_START_MIN)
        if len(range_positions) == 0:
            continue
        range_index = int(indices[int(range_positions[0])])
        hi = float(high[range_index])
        lo = float(low[range_index])
        width = hi - lo
        if not np.isfinite(width) or width < 5.0:
            continue

        position = None
        pending = None
        entries = 0
        day_trades = []

        for pos in range(int(range_positions[0]) + 1, len(indices)):
            index = int(indices[pos])
            current_min = int(minute[index])
            if current_min >= CLOSE_MIN:
                break

            # --- pending close-signal entry fills at this bar open ---
            if pending is not None:
                side = pending["side"]
                boundary = pending["boundary"]
                still_beyond = (side == "BUY" and open_[index] > boundary) or (
                    side == "SELL" and open_[index] < boundary
                )
                if still_beyond and entries < max_trades:
                    entry = float(open_[index])
                    stop = pending["stop"]
                    checked = filter_ok(entry, boundary, stop, width)
                    if checked is not None:
                        extension, extension_ratio, stop_distance, stop_ratio = checked
                        direction = 1.0 if side == "BUY" else -1.0
                        position = {
                            "date": date,
                            "side": side,
                            "entry": entry,
                            "stop": stop,
                            "target": entry + direction * TARGET_R * stop_distance,
                            "entry_pos": pos,
                            "entry_time": times[index],
                            "entry_source": "close",
                            "range_high": hi,
                            "range_low": lo,
                            "range_width": width,
                            "extension": extension,
                            "extension_ratio": extension_ratio,
                            "stop_distance": stop_distance,
                            "stop_ratio": stop_ratio,
                            "pressure": pending["pressure"],
                            "rank": entries + 1,
                            "check_same_bar": True,
                        }
                        entries += 1
                pending = None

            # --- manage an open position ---
            closed_this_bar = False
            if position is not None:
                check_now = position.get("check_same_bar", False) or (
                    position["entry_pos"] != pos
                )
                exit_price = None
                reason = None
                if check_now:
                    exit_price, reason = check_exit(position, index, open_, high, low)
                if exit_price is None and current_min == LAST_BAR_MIN:
                    exit_price = float(close[index])
                    reason = "eod"
                if exit_price is not None:
                    exit_time = pd.Timestamp(times[index]) + pd.Timedelta(minutes=15)
                    day_trades.append(
                        build_trade(position, exit_price, exit_time, reason)
                    )
                    position = None
                    closed_this_bar = True

            # --- new signal on this bar ---
            if position is not None or closed_this_bar or entries >= max_trades:
                continue
            if current_min >= last_entry_min:
                continue

            side = None
            entry = None
            boundary = None
            source = None
            pressure = None
            at_open = False

            buy_break = (high[index] >= hi) or (open_[index] > hi)
            sell_break = (low[index] <= lo) or (open_[index] < lo)
            if buy_break and sell_break:
                if close[index] >= hi:
                    side = "BUY"
                elif close[index] <= lo:
                    side = "SELL"
            elif buy_break:
                side = "BUY"
            elif sell_break:
                side = "SELL"

            if side == "BUY":
                boundary = hi
                pressure = buy_prev[index]
                if pressure >= PRESSURE_MIN:
                    entry = max(float(open_[index]), hi)
                    source = "break"
                    at_open = float(open_[index]) > hi
            elif side == "SELL":
                boundary = lo
                pressure = sell_prev[index]
                if pressure >= PRESSURE_MIN:
                    entry = min(float(open_[index]), lo)
                    source = "break"
                    at_open = float(open_[index]) < lo

            # Pressure only became valid on this bar close: enter next open.
            if entry is None and current_min + 15 < last_entry_min:
                if close[index] >= hi and buy_now[index] >= PRESSURE_MIN:
                    pending = {
                        "side": "BUY",
                        "boundary": hi,
                        "stop": lo,
                        "pressure": buy_now[index],
                    }
                elif close[index] <= lo and sell_now[index] >= PRESSURE_MIN:
                    pending = {
                        "side": "SELL",
                        "boundary": lo,
                        "stop": hi,
                        "pressure": sell_now[index],
                    }

            if entry is None:
                continue

            stop = lo if side == "BUY" else hi
            checked = filter_ok(entry, boundary, stop, width)
            if checked is None:
                continue
            extension, extension_ratio, stop_distance, stop_ratio = checked
            direction = 1.0 if side == "BUY" else -1.0
            position = {
                "date": date,
                "side": side,
                "entry": entry,
                "stop": stop,
                "target": entry + direction * TARGET_R * stop_distance,
                "entry_pos": pos,
                "entry_time": times[index],
                "entry_source": source,
                "range_high": hi,
                "range_low": lo,
                "range_width": width,
                "extension": extension,
                "extension_ratio": extension_ratio,
                "stop_distance": stop_distance,
                "stop_ratio": stop_ratio,
                "pressure": pressure,
                "rank": entries + 1,
                "check_same_bar": at_open,
            }
            entries += 1

        # Safety fallback: close anything still open at the last known bar.
        if position is not None:
            index = int(indices[-1])
            exit_time = pd.Timestamp(times[index]) + pd.Timedelta(minutes=15)
            day_trades.append(
                build_trade(position, float(close[index]), exit_time, "eod")
            )
        trades.extend(day_trades)

    frame = pd.DataFrame(trades)
    if not frame.empty:
        frame["entry_time"] = pd.to_datetime(frame["entry_time"], utc=True)
        frame["exit_time"] = pd.to_datetime(frame["exit_time"], utc=True)
        frame = frame.sort_values(["date", "entry_time"]).reset_index(drop=True)
    return frame


def max_drawdown(r_values):
    values = np.asarray(r_values, dtype=float)
    if len(values) == 0:
        return 0.0
    curve = np.cumsum(values)
    return float(np.max(np.maximum.accumulate(curve) - curve))


def equity_drawdown(r_values, risk=0.005):
    balance = 1.0
    peak = 1.0
    worst = 0.0
    for value in r_values:
        balance *= 1.0 + risk * float(value)
        peak = max(peak, balance)
        worst = max(worst, 1.0 - balance / peak)
    return float(worst)


def period_slice(frame, start=None, end=None):
    if frame.empty:
        return frame
    dates = pd.to_datetime(frame["date"])
    mask = pd.Series(True, index=frame.index)
    if start is not None:
        mask &= dates >= pd.Timestamp(start)
    if end is not None:
        mask &= dates < pd.Timestamp(end)
    return frame[mask]


def summarize(trades, label):
    rows = []
    periods = {
        "all": (None, None),
        "is": (None, "2022-01-01"),
        "oos": ("2022-01-01", "2025-09-01"),
        "recent": ("2025-09-01", None),
    }
    for period, (start, end) in periods.items():
        part = period_slice(trades, start, end)
        if part.empty:
            rows.append(
                {
                    "variant": label,
                    "period": period,
                    "trades": 0,
                    "win_rate": np.nan,
                    "avg_r": np.nan,
                    "total_r": 0.0,
                    "profit_factor": np.nan,
                    "max_dd_r": 0.0,
                    "max_dd_pct_05": 0.0,
                    "avg_extension_ratio": np.nan,
                    "late_rate": np.nan,
                    "avg_stop_ratio": np.nan,
                    "target_rate": np.nan,
                    "stop_rate": np.nan,
                    "eod_rate": np.nan,
                }
            )
            continue
        r_values = part["r_multiple"].to_numpy(float)
        gains = r_values[r_values > 0].sum()
        losses = -r_values[r_values < 0].sum()
        rows.append(
            {
                "variant": label,
                "period": period,
                "trades": int(len(part)),
                "win_rate": float((r_values > 0).mean()),
                "avg_r": float(r_values.mean()),
                "total_r": float(r_values.sum()),
                "profit_factor": float(gains / losses) if losses > 0 else np.inf,
                "max_dd_r": max_drawdown(r_values),
                "max_dd_pct_05": equity_drawdown(r_values, 0.005),
                "avg_extension_ratio": float(part["extension_ratio"].mean()),
                "late_rate": float((part["extension_ratio"] > 0.05).mean()),
                "avg_stop_ratio": float(part["stop_ratio"].mean()),
                "target_rate": float((part["reason"] == "target").mean()),
                "stop_rate": float((part["reason"] == "stop").mean()),
                "eod_rate": float((part["reason"] == "eod").mean()),
            }
        )
    return rows


def add_rank(trades):
    if trades.empty:
        return trades
    part = trades.copy()
    part["date"] = pd.to_datetime(part["date"])
    part = part.sort_values(["date", "entry_time"]).reset_index(drop=True)
    part["rank"] = part.groupby("date").cumcount() + 1
    return part


def rank_breakdown(trades):
    if trades.empty:
        return pd.DataFrame()
    part = add_rank(trades)
    part["rank_group"] = np.where(
        part["rank"] == 1, "1", np.where(part["rank"] <= 3, "2-3", "4+")
    )
    rows = []
    for label, group in part.groupby("rank_group", sort=False):
        r_values = group["r_multiple"].to_numpy(float)
        rows.append(
            {
                "rank_group": label,
                "trades": int(len(group)),
                "win_rate": float((r_values > 0).mean()),
                "avg_r": float(r_values.mean()),
                "total_r": float(r_values.sum()),
                "avg_extension_ratio": float(group["extension_ratio"].mean()),
                "avg_stop_ratio": float(group["stop_ratio"].mean()),
                "target_rate": float((group["reason"] == "target").mean()),
            }
        )
    return pd.DataFrame(rows)


def extension_buckets(trades, rank1_only=False):
    if trades.empty:
        return pd.DataFrame()
    part = add_rank(trades)
    if rank1_only:
        part = part[part["rank"] == 1]
    bins = [-0.0001, 0.05, 0.25, 0.5, 1.0, 2.0, np.inf]
    labels = ["0-0.05", "0.05-0.25", "0.25-0.5", "0.5-1.0", "1.0-2.0", ">2.0"]
    part = part.copy()
    part["bucket"] = pd.cut(part["extension_ratio"], bins=bins, labels=labels)
    rows = []
    for label, group in part.groupby("bucket", observed=False):
        if group.empty:
            rows.append(
                {
                    "bucket": str(label),
                    "trades": 0,
                    "win_rate": np.nan,
                    "avg_r": np.nan,
                    "total_r": 0.0,
                }
            )
            continue
        r_values = group["r_multiple"].to_numpy(float)
        rows.append(
            {
                "bucket": str(label),
                "trades": int(len(group)),
                "win_rate": float((r_values > 0).mean()),
                "avg_r": float(r_values.mean()),
                "total_r": float(r_values.sum()),
                "avg_stop_ratio": float(group["stop_ratio"].mean()),
                "target_rate": float((group["reason"] == "target").mean()),
            }
        )
    return pd.DataFrame(rows)


def side_period_table(trades):
    if trades.empty:
        return pd.DataFrame()
    part = trades.copy()
    part["date"] = pd.to_datetime(part["date"])
    part["period"] = np.select(
        [
            part["date"] < pd.Timestamp("2022-01-01"),
            (part["date"] >= pd.Timestamp("2022-01-01"))
            & (part["date"] < pd.Timestamp("2025-09-01")),
            part["date"] >= pd.Timestamp("2025-09-01"),
        ],
        ["IS", "OOS", "RECENT"],
        "?",
    )
    rows = []
    for (period, side), group in part.groupby(["period", "side"]):
        r_values = group["r_multiple"].to_numpy(float)
        rows.append(
            {
                "period": period,
                "side": side,
                "trades": int(len(group)),
                "avg_r": float(r_values.mean()),
                "total_r": float(r_values.sum()),
            }
        )
    return pd.DataFrame(rows)


def time_slot_table(trades):
    if trades.empty:
        return pd.DataFrame()
    part = add_rank(trades)
    ny = part["entry_time"].dt.tz_convert(NY)
    minutes = ny.dt.hour * 60 + ny.dt.minute
    bins = [RANGE_END_MIN, 11 * 60, 13 * 60, 15 * 60, 17 * 60, 19 * 60, CLOSE_MIN]
    labels = [
        "09:45-11:00",
        "11:00-13:00",
        "13:00-15:00",
        "15:00-17:00",
        "17:00-19:00",
        "19:00-22:45",
    ]
    part = part.copy()
    part["slot"] = pd.cut(minutes, bins=bins, labels=labels, right=False)
    rows = []
    for label, group in part.groupby("slot", observed=False):
        if group.empty:
            rows.append(
                {
                    "slot": str(label),
                    "trades": 0,
                    "win_rate": np.nan,
                    "avg_r": np.nan,
                    "total_r": 0.0,
                    "target_rate": np.nan,
                }
            )
            continue
        r_values = group["r_multiple"].to_numpy(float)
        rows.append(
            {
                "slot": str(label),
                "trades": int(len(group)),
                "win_rate": float((r_values > 0).mean()),
                "avg_r": float(r_values.mean()),
                "total_r": float(r_values.sum()),
                "target_rate": float((group["reason"] == "target").mean()),
            }
        )
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bars",
        nargs="+",
        default=[
            "data_live/nas100_m15_kaggle_utc.parquet",
            "data_live/nas100_m15.parquet",
        ],
    )
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    bars = load_bars(args.bars)
    print(
        f"Bars {len(bars):,} | {bars['time'].min()} -> {bars['time'].max()} | "
        f"{bars['ny_date'].nunique()} NY dates"
    )

    variants = {
        "baseline": {},
        "max1": {"max_trades": 1},
        "max2": {"max_trades": 2},
        "max3": {"max_trades": 3},
        "cut14": {"last_entry_min": 14 * 60},
        "cut15": {"last_entry_min": 15 * 60},
        "cut16": {"last_entry_min": 16 * 60},
        "max1_cut15": {"max_trades": 1, "last_entry_min": 15 * 60},
        "max2_cut15": {"max_trades": 2, "last_entry_min": 15 * 60},
        "extension_0.25": {"max_extension": 0.25},
        "extension_0.50": {"max_extension": 0.50},
        "extension_0.75": {"max_extension": 0.75},
        "extension_1.00": {"max_extension": 1.00},
        "max2_ext0.50": {"max_trades": 2, "max_extension": 0.50},
        "stop_ratio_1.50": {"max_stop_ratio": 1.50},
        "stop_ratio_2.00": {"max_stop_ratio": 2.00},
    }

    all_rows = []
    baseline = None
    for label, kwargs in variants.items():
        trades = simulate(bars, **kwargs)
        trades.to_csv(out / f"trades_{label}.csv", index=False)
        if label == "baseline":
            baseline = trades
        all_rows.extend(summarize(trades, label))
        print(f"{label}: {len(trades)} trades")

    summary = pd.DataFrame(all_rows)
    summary.to_csv(out / "summary.csv", index=False)
    buckets_all = extension_buckets(baseline)
    buckets_all.to_csv(out / "extension_buckets.csv", index=False)
    buckets_rank1 = extension_buckets(baseline, rank1_only=True)
    buckets_rank1.to_csv(out / "extension_buckets_rank1.csv", index=False)
    ranks = rank_breakdown(baseline)
    ranks.to_csv(out / "rank_breakdown.csv", index=False)
    sides = side_period_table(baseline)
    sides.to_csv(out / "side_period.csv", index=False)
    slots = time_slot_table(baseline)
    slots.to_csv(out / "time_slots.csv", index=False)

    baseline_stats = summary[
        (summary["variant"] == "baseline") & (summary["period"] == "all")
    ].iloc[0]
    cut15_stats = summary[
        (summary["variant"] == "cut15") & (summary["period"] == "all")
    ].iloc[0]

    coverage = (
        f"{bars['time'].min()} -> {bars['time'].max()}, "
        f"{bars['ny_date'].nunique()} dates NY"
    )
    lines = [
        "# ORB Pressure - revue des entrees tardives et des re-entrees",
        "",
        f"- Donnees : {coverage}.",
        f"- Strategie simulee : range 09:30 NY, pression {PRESSURE_BARS} bougies "
        f"cloturees, seuil {PRESSURE_MIN:.2f}, cible {TARGET_R:.1f}R, "
        f"cloture de securite 22:55 NY, cout {COST_POINTS:.1f} point.",
        f"- Baseline : {int(baseline_stats['trades'])} trades, "
        f"win {baseline_stats['win_rate'] * 100:.1f} %, "
        f"R moyen {baseline_stats['avg_r']:.3f}, "
        f"R total {baseline_stats['total_r']:.1f}, "
        f"DD max {baseline_stats['max_dd_pct_05'] * 100:.1f} % a 0,5 %/trade.",
        f"- Coupe-circuit 15:00 NY : {int(cut15_stats['trades'])} trades, "
        f"R moyen {cut15_stats['avg_r']:.3f}, "
        f"R total {cut15_stats['total_r']:.1f}, "
        f"DD max {cut15_stats['max_dd_pct_05'] * 100:.1f} %.",
        "- Test apparie par session dans `cutoff_test.md` : le gain du coupe-circuit "
        "15:00 est positif sur les trois periodes et significatif au bootstrap.",
        "",
        "## Effet des filtres",
        "",
        summary[
            [
                "variant",
                "period",
                "trades",
                "win_rate",
                "avg_r",
                "total_r",
                "profit_factor",
                "max_dd_pct_05",
                "avg_extension_ratio",
                "late_rate",
                "target_rate",
            ]
        ].to_markdown(index=False, floatfmt=".4f"),
        "",
        "## Effet du rang d'entree dans la journee (baseline)",
        "",
        ranks.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## Resultat par distance d'entree (baseline, tous rangs)",
        "",
        buckets_all.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## Resultat par distance d'entree (baseline, premier trade du jour)",
        "",
        buckets_rank1.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## BUY / SELL par periode (baseline)",
        "",
        sides.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## Resultat par heure d'entree (baseline)",
        "",
        slots.to_markdown(index=False, floatfmt=".4f"),
        "",
        "Lecture : `extension` est la distance entre le prix d'entree et la "
        "bordure du range, divisee par la largeur du range. `0-0.05` correspond "
        "a une cassure nette ; `>1.0` a une entree tres tardive. Les trades sont "
        "simules avec des bougies M15, sans tick ni carnet : les chiffres servent "
        "a comparer des regles, pas a promettre un resultat live.",
    ]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n" + "\n".join(lines[:12]))


if __name__ == "__main__":
    main()
