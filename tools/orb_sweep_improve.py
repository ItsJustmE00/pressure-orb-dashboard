"""Sweep d'amelioration ORB : filtre OR-rank + buffer de stop.

Bascule : baseline 2R max2 (22,34 % OOS / 5,40 % DD).
Chaque variante est testee sur OOS 2022-2025 + recent 2025-2026.
"""
import io
import sys

import pandas as pd
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out_orb_manage"

spec = importlib.util.spec_from_file_location("mg", ROOT / "tools" / "orb_manage_sim.py")
m = importlib.util.module_from_spec(spec)
_old = sys.stdout
sys.stdout = io.StringIO()
try:
    spec.loader.exec_module(m)
finally:
    sys.stdout = _old

bars = m.mod.load_bars([
    "data_live/nas100_m15_kaggle_utc.parquet",
    "data_live/nas100_m15.parquet",
])
OOS = m.mod.PERIODS[1]
RECENT = m.mod.PERIODS[2]

rows = []
cases = [
    ("baseline", dict()),
    ("rank0.1", dict(rank_max=0.1)),
    ("rank0.2", dict(rank_max=0.2)),
    ("rank0.3", dict(rank_max=0.3)),
    ("rank0.4", dict(rank_max=0.4)),
    ("buf0.05", dict(stop_buffer_frac=0.05)),
    ("buf0.10", dict(stop_buffer_frac=0.10)),
    ("buf0.20", dict(stop_buffer_frac=0.20)),
    ("rank0.2_buf0.05", dict(rank_max=0.2, stop_buffer_frac=0.05)),
    ("rank0.3_buf0.10", dict(rank_max=0.3, stop_buffer_frac=0.10)),
]
for name, kw in cases:
    tr, _ = m.simulate_manage(bars, 0.005, 1.7, 2.0, 2, **kw)
    a = m.metrics(tr, 0.005, OOS[1], OOS[2])
    b = m.metrics(tr, 0.005, RECENT[1], RECENT[2])
    rows.append({
        "variante": name,
        "oos_ret": round(a["return_pct"], 2), "oos_dd": round(a["max_dd_pct"], 2),
        "oos_wr": round(a["winrate"], 1), "oos_pf": round(a["pf"], 2),
        "oos_usd_day": round(a["per_day_usd"], 2),
        "recent_ret": round(b["return_pct"], 2), "recent_dd": round(b["max_dd_pct"], 2),
        "recent_wr": round(b["winrate"], 1), "recent_trades": b["trades"],
    })
    tr.to_csv(OUT / f"trades_sweep_{name}.csv", index=False)

df = pd.DataFrame(rows).sort_values("oos_ret", ascending=False)
df.to_csv(OUT / "improve_sweep.csv", index=False)
print(df.to_string(index=False))
