"""Test du filtre DELTA-CONFIRM sur le systeme LIVE (baseline 2R max2).

Wall Street rule : un breakout sans pression dans le sens du mouvement
(bougie de breakout qui cloture contre le sens) = absorption probable -> skip.
L'entree se fait alors a la cloture de la bougie de breakout confirmee.
"""
import importlib.util
import io
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out_wallstreet"
OUT.mkdir(exist_ok=True)

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
    ("delta_confirm", dict(require_break_close=True)),
    ("or_dir (delta bougie 09:30)", dict(req_or_dir=True)),
    ("prev_dir (bougie precedente)", dict(req_prev_dir=True)),
    ("or_dir+prev_dir", dict(req_or_dir=True, req_prev_dir=True)),
]
for name, kw in cases:
    tr, _ = m.simulate_manage(bars, 0.005, 1.7, 2.0, 2, **kw)
    a = m.metrics(tr, 0.005, OOS[1], OOS[2])
    b = m.metrics(tr, 0.005, RECENT[1], RECENT[2])
    f = m.metrics(tr, 0.005, m.mod.PERIODS[-1][1], m.mod.PERIODS[-1][2])
    rows.append({
        "variante": name,
        "oos_ret": round(a["return_pct"], 2), "oos_dd": round(a["max_dd_pct"], 2),
        "oos_wr": round(a["winrate"], 1), "oos_avg_r": round(a["avg_r"], 3),
        "oos_trades": a["trades"],
        "recent_ret": round(b["return_pct"], 2), "recent_wr": round(b["winrate"], 1),
        "recent_trades": b["trades"],
        "full_ret": round(f["return_pct"], 2), "full_dd": round(f["max_dd_pct"], 2),
    })
    tr.to_csv(OUT / f"trades_live_{name}.csv", index=False)

df = pd.DataFrame(rows)
df.to_csv(OUT / "delta_confirm_result.csv", index=False)
print(df.to_string(index=False))
