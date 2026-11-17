import importlib.util
import io
import sys

spec = importlib.util.spec_from_file_location("aggr", "tools/orb_aggressive_sim.py")
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
OOS, FULL = m.mod.PERIODS[1], m.mod.PERIODS[-1]
for t, mt in [(3.0, 1), (3.0, 2), (2.5, 2)]:
    tr, _ = m.simulate_multi(bars, 0.005, 1.7, t, mt, 1)
    a = m.metrics(tr, 0.005, OOS[1], OOS[2])
    b = m.metrics(tr, 0.005, FULL[1], FULL[2])
    print(
        f"target={t} max={mt} trades={a['trades']} win={a['winrate']:.1f}% "
        f"avgR={a['avg_r']:.3f} ret={a['return_pct']:.2f}% dd={a['max_dd_pct']:.2f}% "
        f"usd_day={a['per_day_usd']:.2f} full_ret={b['return_pct']:.2f}% full_dd={b['max_dd_pct']:.2f}%"
    )
