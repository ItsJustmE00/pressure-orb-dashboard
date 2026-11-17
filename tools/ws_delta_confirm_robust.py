"""Robustesse du filtre delta-confirm : sensibilite au cout, au cible, au EOD.

Si l'amelioration survit a toutes les variantes de parametres -> edge reel.
"""
import importlib.util
import io
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out_wallstreet"

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
FULL = m.mod.PERIODS[-1]

rows = []
for cost in (1.7, 2.5, 3.4):
    for target in (2.0, 2.5, 1.5):
        for eod in (0, 1):
            res = {}
            for name, kw in (("base", dict()), ("dc", dict(require_break_close=True))):
                tr, _ = m.simulate_manage(bars, 0.005, cost, target, 2, eod_bars_back=eod, **kw)
                a = m.metrics(tr, 0.005, OOS[1], OOS[2])
                res[name] = a
            rows.append({
                "cost": cost, "target": target, "eod": eod,
                "base_ret": round(res["base"]["return_pct"], 1),
                "dc_ret": round(res["dc"]["return_pct"], 1),
                "base_dd": round(res["base"]["max_dd_pct"], 1),
                "dc_dd": round(res["dc"]["max_dd_pct"], 1),
                "base_wr": round(res["base"]["winrate"], 1),
                "dc_wr": round(res["dc"]["winrate"], 1),
                "dc_trades": res["dc"]["trades"],
                "dc_bat": "OK" if res["dc"]["return_pct"] > res["base"]["return_pct"] else "PERDU",
            })

df = pd.DataFrame(rows)
df.to_csv(OUT / "delta_confirm_robustness.csv", index=False)
print(df.to_string(index=False))
n_ok = (df["dc_bat"] == "OK").sum()
print(f"\ndelta-confirm gagne dans {n_ok}/{len(df)} combinaisons de parametres")
