"""Sweep des seuils d'entree ORB : momentum, trend, or_close, cible.

Variation un-a-la-fois autour du baseline 2R max2.
"""
import importlib.util
import io
import sys
from pathlib import Path

import pandas as pd

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

BASE = dict(
    LONG_TREND_MAX=0.002378, LONG_OR_MIN=0.8044, LONG_MOM_MIN=0.00123,
    SHORT_TREND_MIN=-0.00425, SHORT_OR_MAX=0.1956, SHORT_MOM_MAX=-0.00123,
)

cases = [
    ("baseline", {}),
    ("mom0.0010", dict(LONG_MOM_MIN=0.0010, SHORT_MOM_MAX=-0.0010)),
    ("mom0.0015", dict(LONG_MOM_MIN=0.0015, SHORT_MOM_MAX=-0.0015)),
    ("mom0.0018", dict(LONG_MOM_MIN=0.0018, SHORT_MOM_MAX=-0.0018)),
    ("trend0.0020", dict(LONG_TREND_MAX=0.0020, SHORT_TREND_MIN=-0.0020)),
    ("trend0.0028", dict(LONG_TREND_MAX=0.0028, SHORT_TREND_MIN=-0.0028)),
    ("trend0.0035", dict(LONG_TREND_MAX=0.0035, SHORT_TREND_MIN=-0.0035)),
    ("orclose0.75", dict(LONG_OR_MIN=0.75, SHORT_OR_MAX=0.25)),
    ("orclose0.85", dict(LONG_OR_MIN=0.85, SHORT_OR_MAX=0.15)),
    ("target2.25", dict(target=2.25)),
    ("target2.50", dict(target=2.50)),
    ("target1.75", dict(target=1.75)),
]

rows = []
for name, overrides in cases:
    target = overrides.pop("target", 2.0)
    for k, v in BASE.items():
        setattr(m.mod, k, v)
    for k, v in overrides.items():
        setattr(m.mod, k, v)
    tr, _ = m.simulate_manage(bars, 0.005, 1.7, target, 2)
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
    tr.to_csv(OUT / f"trades_sweep2_{name}.csv", index=False)

df = pd.DataFrame(rows).sort_values("oos_ret", ascending=False)
df.to_csv(OUT / "entry_sweep.csv", index=False)
print(df.to_string(index=False))
