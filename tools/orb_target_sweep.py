"""Sweep de la cible R pour ORB BOTH : 1R agressif vs 3R actuel.

Réutilise la simulation bar-level validée (out_orb_both_oos) en changeant
uniquement la cible. Coût 1.7 pts, eod_bars_back=1, risque 0.5 %.
"""
import importlib.util
import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("orb_oos", ROOT / "tools" / "orb_both_oos.py")
mod = importlib.util.module_from_spec(spec)
sys.stdout = io.StringIO()  # silence le main() éventuel
spec.loader.exec_module(mod)
sys.stdout = sys.__stdout__

bars = mod.load_bars([
    "data_live/nas100_m15_kaggle_utc.parquet",
    "data_live/nas100_m15.parquet",
])

TARGETS = [0.75, 1.0, 1.25, 1.5, 2.0, 3.0]
RISK = 0.005
COST = 1.7
EOD = 1

rows = []
trades_by_target = {}
for target in TARGETS:
    mod.TARGET_R = target
    trades, sim_dd = mod.simulate(bars, RISK, COST, EOD)
    trades_by_target[target] = trades
    for name, start, end in mod.PERIODS:
        m = mod.period_metrics(trades, RISK, start, end)
        if m is None:
            continue
        rows.append({
            "target_r": target,
            "period": name,
            "trades": m.get("trades"),
            "return_pct": round(m["return_pct"] * 100, 2),
            "max_dd_pct": round(m["max_dd_pct"] * 100, 2),
            "final": round(m["final"], 2),
        })

out = Path("out_orb_target_sweep")
out.mkdir(exist_ok=True)
summary = pd.DataFrame(rows)
summary.to_csv(out / "summary.csv", index=False)
print(summary.to_string(index=False))

print("\n--- Stats par cible (OOS 2022-2025) ---")
oos_start, oos_end = pd.Timestamp("2022-01-01").date(), pd.Timestamp("2025-09-20").date()
for target, tr in trades_by_target.items():
    d = tr[(tr["date"] >= oos_start) & (tr["date"] <= oos_end)]
    if d.empty:
        continue
    win = (d["r_multiple"] > 0).mean()
    by_reason = d["reason"].value_counts().to_dict()
    avg_r = d["r_multiple"].mean()
    avg_win_points = d.loc[d["r_multiple"] > 0, "net_points"].mean()
    avg_stop_points = d["stop_points"].mean()
    print(
        f"target={target} trades={len(d)} winrate={win*100:.1f}% avgR={avg_r:.3f} "
        f"reasons={by_reason} avgWinPts={avg_win_points:.1f} avgStopPts={avg_stop_points:.1f}"
    )

# repartition horaire d'entree (OOS, cible 1R)
tr = trades_by_target[1.0]
d = tr[(tr["date"] >= oos_start) & (tr["date"] <= oos_end)]
d["entry_min"] = pd.to_datetime(d["entry_time"], utc=True).dt.strftime("%H:%M").str.slice(0, 5)
print("\n--- Entrees par heure NY (cible 1R, OOS) ---")
print(d.groupby(d["entry_time"].str.slice(11, 13))["r_multiple"].agg(["count", "mean"]).round(3).to_string())
