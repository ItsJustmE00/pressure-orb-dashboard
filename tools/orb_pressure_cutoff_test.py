"""Block-bootstrap the 15:00 NY entry cutoff against the live baseline.

Trades on the same day are correlated, so the resampling unit is the NY
session, not the individual trade. The script reads the trade files produced
by ``orb_pressure_late_entry_sim.py`` and writes a short markdown summary.

No MT5 connection and no strategy change: this is a statistical check.
"""

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("out_orb_pressure_review")
BASELINE = OUT / "trades_baseline.csv"
VARIANTS = {
    "cut14": OUT / "trades_cut14.csv",
    "cut15": OUT / "trades_cut15.csv",
    "cut16": OUT / "trades_cut16.csv",
    "max2_cut15": OUT / "trades_max2_cut15.csv",
}
PERIODS = {
    "all": (None, None),
    "is": (None, "2022-01-01"),
    "oos": ("2022-01-01", "2025-09-01"),
    "recent": ("2025-09-01", None),
}
SEED = 20261119
BOOTSTRAP = 5000


def load(path):
    frame = pd.read_csv(path, parse_dates=["date", "entry_time", "exit_time"])
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    return frame


def daily(frame):
    return frame.groupby("date")["r_multiple"].agg(["sum", "size"])


def drawdown(r_values, risk=0.005):
    balance = 1.0
    peak = 1.0
    worst = 0.0
    for value in r_values:
        balance *= 1.0 + risk * float(value)
        peak = max(peak, balance)
        worst = max(worst, 1.0 - balance / peak)
    return worst


def period_stats(frame, start, end):
    dates = pd.to_datetime(frame["date"])
    mask = pd.Series(True, index=frame.index)
    if start is not None:
        mask &= dates >= pd.Timestamp(start)
    if end is not None:
        mask &= dates < pd.Timestamp(end)
    part = frame[mask]
    r_values = part["r_multiple"].to_numpy(float)
    return {
        "trades": int(len(part)),
        "avg_r": float(r_values.mean()) if len(part) else np.nan,
        "total_r": float(r_values.sum()),
        "dd_pct": drawdown(r_values) * 100.0,
        "max_day_r": float(part.groupby("date")["r_multiple"].sum().min())
        if len(part)
        else np.nan,
    }


def bootstrap(base, other, seed=SEED, draws=BOOTSTRAP):
    """Paired day-level bootstrap of total and average R."""
    base_daily = daily(base)
    other_daily = daily(other)
    dates = sorted(set(base_daily.index) | set(other_daily.index))
    base_sum = base_daily["sum"].reindex(dates, fill_value=0.0).to_numpy(float)
    base_n = base_daily["size"].reindex(dates, fill_value=0).to_numpy(float)
    other_sum = other_daily["sum"].reindex(dates, fill_value=0.0).to_numpy(float)
    other_n = other_daily["size"].reindex(dates, fill_value=0).to_numpy(float)

    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(dates), size=(draws, len(dates)))
    base_total = base_sum[idx].sum(axis=1)
    other_total = other_sum[idx].sum(axis=1)
    base_avg = base_total / np.maximum(base_n[idx].sum(axis=1), 1.0)
    other_avg = other_total / np.maximum(other_n[idx].sum(axis=1), 1.0)

    total_diff = other_total - base_total
    avg_diff = other_avg - base_avg
    return {
        "total_diff_mean": float(total_diff.mean()),
        "total_ci_low": float(np.percentile(total_diff, 2.5)),
        "total_ci_high": float(np.percentile(total_diff, 97.5)),
        "total_p_le_0": float((total_diff <= 0.0).mean()),
        "avg_diff_mean": float(avg_diff.mean()),
        "avg_ci_low": float(np.percentile(avg_diff, 2.5)),
        "avg_ci_high": float(np.percentile(avg_diff, 97.5)),
        "avg_p_le_0": float((avg_diff <= 0.0).mean()),
    }


def main():
    baseline = load(BASELINE)
    lines = [
        "# ORB Pressure - test statistique du coupe-circuit horaire",
        "",
        f"- Reechantillonnage par session NY, {BOOTSTRAP} tirages, graine {SEED}.",
        "- Comparaison appariee : memes dates pour la baseline et la variante.",
        "- `p<=0` = part des tirages ou la variante ne fait pas mieux que la baseline.",
        "",
        "## Statistiques par periode",
        "",
        "| variante | periode | trades | R moyen | R total | DD max % | pire journee R |",
        "|:---------|:--------|-------:|--------:|--------:|---------:|---------------:|",
    ]

    for label, path in [("baseline", BASELINE)] + list(VARIANTS.items()):
        frame = baseline if label == "baseline" else load(path)
        for period, (start, end) in PERIODS.items():
            stats = period_stats(frame, start, end)
            lines.append(
                f"| {label} | {period} | {stats['trades']} | "
                f"{stats['avg_r']:.4f} | {stats['total_r']:.1f} | "
                f"{stats['dd_pct']:.1f} | {stats['max_day_r']:.2f} |"
            )

    lines.extend(
        [
            "",
            "## Bootstrap apparie contre la baseline",
            "",
            "| variante | delta R total | IC 95 % | p<=0 | delta R moyen | IC 95 % | p<=0 |",
            "|:---------|--------------:|:--------|-----:|--------------:|:--------|-----:|",
        ]
    )
    for label, path in VARIANTS.items():
        other = load(path)
        result = bootstrap(baseline, other)
        lines.append(
            f"| {label} | {result['total_diff_mean']:+.1f} | "
            f"[{result['total_ci_low']:+.1f} ; {result['total_ci_high']:+.1f}] | "
            f"{result['total_p_le_0']:.3f} | "
            f"{result['avg_diff_mean']:+.4f} | "
            f"[{result['avg_ci_low']:+.4f} ; {result['avg_ci_high']:+.4f}] | "
            f"{result['avg_p_le_0']:.3f} |"
        )

    lines.extend(
        [
            "",
            "Lecture : un intervalle de confiance entièrement positif indique que "
            "la variante bat la baseline sur la majorité des tirages. Le test ne "
            "prouve pas un gain futur ; il vérifie que le gain historique n'est pas "
            "un simple effet de quelques journées.",
        ]
    )
    text = "\n".join(lines) + "\n"
    (OUT / "cutoff_test.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
