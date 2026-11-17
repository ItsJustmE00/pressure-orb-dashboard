"""NOTE DU MATIN — style desk institutionnel (couche 4 du Wall Street Engine).

Genere pour une date donnee le briefing 3 temps, en n'utilisant QUE des
informations disponibles a chaque horodatage (aucun lookahead) :

  09:25 pre-ouverture : regime (trend EMA20/50), volatilite (ATR percentile),
                        veille (inside/trend), range overnight, gap.
  09:45 ouverture     : largeur du range d'ouverture (en ATR), delta de la
                        bougie d'ouverture (acheteurs vs vendeurs), volume relatif,
                        setups long/short valides selon les filtres ORB.
  verdict             : TRADE / NO-TRADE + raisons.

Usage :
  python tools/ws_morning_note.py --date 2025-04-09
  python tools/ws_morning_note.py --last
"""
import argparse
import importlib.util
import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location("oos", ROOT / "tools" / "orb_both_oos.py")
mod = importlib.util.module_from_spec(spec)
_old = sys.stdout
sys.stdout = io.StringIO()
try:
    spec.loader.exec_module(mod)
finally:
    sys.stdout = _old

# filtres ORB live (identiques au preset EA)
LONG_TREND_MAX, LONG_OR_MIN, LONG_MOM_MIN = 0.002378, 0.8044, 0.00123
SHORT_TREND_MIN, SHORT_OR_MAX, SHORT_MOM_MAX = -0.00425, 0.1956, -0.00123


def note(day, bars, sess_daily):
    d = bars[bars["ny_date"] == day].sort_values("time")
    d = d[(d["ny_min"] >= 570) & (d["ny_min"] < 960)].reset_index(drop=True)
    if len(d) < 10:
        print(f"pas de session complete pour {day}")
        return
    ctx = sess_daily.set_index("ny_date")
    if day not in ctx.index:
        return
    c = ctx.loc[day]
    atr = float(c["atr"])

    lines = []
    lines.append(f"╔══════════ NOTE DU MATIN — USTEC — {day} ══════════")
    lines.append("║")

    # ---------- 09:25 pre-ouverture ----------
    trend = float(c["trend"])
    atr_pct = float(c["atr_pct"])
    prev_dir = int(c["dir_prev"])
    inside = int(c["inside"])
    regime = "HAUSSIER" if trend > 0.001 else ("BAISSIER" if trend < -0.001 else "NEUTRE")
    vol_reg = ("haute" if atr_pct >= 0.8 else "normale" if atr_pct >= 0.3 else "basse")

    # overnight : bougies avant 09:30 NY du jour
    pre = bars[(bars["ny_date"] == day) & (bars["ny_min"] < 570)]
    on_range = (float(pre["high"].max()) - float(pre["low"].min())) if len(pre) else np.nan
    day_open = float(d.iloc[0]["open"])
    gap = (day_open - float(c["prev_c"])) / atr if np.isfinite(c["prev_c"]) and atr > 0 else np.nan

    lines.append("║ 09:25 — PRE-OUVERTURE (couche 1 : contexte marche)")
    lines.append(f"║   regime          : {regime}  (EMA20 vs EMA50 : {trend*100:+.2f}%)")
    lines.append(f"║   volatilite     : {vol_reg}  (ATR20 = {atr:.0f} pts, percentile 1 an = {atr_pct:.0%})")
    lines.append(f"║   veille         : {'INSIDE DAY' if inside else ('tendance ' + ('haussiere' if prev_dir > 0 else 'baissiere'))}")
    lines.append(f"║   range overnight: {on_range:.0f} pts ({on_range/atr:.1f} ATR)" if np.isfinite(on_range) else "║   range overnight: n/a")
    lines.append(f"║   gap d'ouverture: {gap:+.2f} ATR" if np.isfinite(gap) else "║   gap d'ouverture: n/a")

    # ---------- 09:45 ouverture ----------
    ob = d.iloc[0]
    or_high, or_low = float(ob["high"]), float(ob["low"])
    or_range = or_high - or_low
    rng = float(ob["high"]) - float(ob["low"])
    delta0 = (float(ob["close"]) - float(ob["open"])) / (rng if rng > 0 else 1.0)
    # volume relatif de l'ouverture
    vol_open_hist = []
    for x in list(ctx.index[ctx.index < day])[-20:]:
        v = bars[(bars["ny_date"] == x) & (bars["ny_min"] == 570)]["tick_volume"]
        if len(v):
            vol_open_hist.append(float(v.iloc[0]))
    vol_rel = float(ob["tick_volume"]) / np.median(vol_open_hist) if len(vol_open_hist) >= 10 else np.nan

    lines.append("║")
    lines.append("║ 09:45 — OUVERTURE (couche 2 : microstructure)")
    lines.append(f"║   range d'ouverture : {or_range:.0f} pts ({or_range/atr:.2f} ATR)  [{or_low:.0f} - {or_high:.0f}]")
    lines.append(f"║   delta bougie 09:30: {delta0:+.2f}  ({'ACHETEURS dominants' if delta0 > 0 else 'VENDEURS dominants' if delta0 < 0 else 'equilibre'})")
    lines.append(f"║   volume relatif    : x{vol_rel:.2f} vs mediane 20j" if np.isfinite(vol_rel) else "║   volume relatif    : n/a")
    if or_range / atr < 0.30:
        lines.append("║   ⚠ range tres etroit vs ATR -> breakout a risque de faux depart")

    # ---------- verdict ----------
    lines.append("║")
    lines.append("║ VERDICT (couche 3 : setups)")
    trend = float(c["trend"])
    pos_close = (float(ob["close"]) - or_low) / (or_range if or_range > 0 else 1)
    long_setup = trend <= LONG_TREND_MAX and pos_close >= LONG_OR_MIN
    short_setup = trend >= SHORT_TREND_MIN and pos_close <= SHORT_OR_MAX
    if long_setup:
        lines.append(f"║   ✅ LONG actif  : breakout de {or_high:.0f} -> stop {or_low:.0f} (~{or_range:.0f} pts), cible 2R")
    if short_setup:
        lines.append(f"║   ✅ SHORT actif : cassure de {or_low:.0f} -> stop {or_high:.0f} (~{or_range:.0f} pts), cible 2R")
    if not long_setup and not short_setup:
        lines.append("║   ❌ NO-TRADE : aucun setup ne passe les filtres (trend/position dans le range)")
    lines.append("║")
    lines.append("║ 16:00 — REVIEW (couche 4 : a remplir apres session)")
    lines.append("╚═══════════════════════════════════════════════════")
    print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    ap.add_argument("--last", action="store_true")
    args = ap.parse_args()

    bars = mod.load_bars([
        "data_live/nas100_m15_kaggle_utc.parquet",
        "data_live/nas100_m15.parquet",
    ])
    sess = bars[(bars["ny_min"] >= 570) & (bars["ny_min"] < 960)]
    daily = sess.groupby("ny_date").agg(
        o=("open", "first"), h=("high", "max"), l=("low", "min"),
        c=("close", "last"), vol=("tick_volume", "sum"), n=("close", "count"),
    ).reset_index().sort_values("ny_date").reset_index(drop=True)
    daily["prev_c"] = daily["c"].shift(1)
    daily["prev_h"] = daily["h"].shift(1)
    daily["prev_l"] = daily["l"].shift(1)
    daily["tr"] = np.maximum(daily["h"] - daily["l"],
                             np.maximum((daily["h"] - daily["prev_c"]).abs(),
                                        (daily["l"] - daily["prev_c"]).abs()))
    daily["atr20"] = daily["tr"].rolling(20).mean()
    daily["atr"] = daily["atr20"]
    daily["atr_pct"] = daily["atr20"].rolling(252).rank(pct=True)
    daily["ema20"] = daily["c"].ewm(span=20, adjust=False).mean()
    daily["ema50"] = daily["c"].ewm(span=50, adjust=False).mean()
    daily["trend"] = (daily["ema20"] - daily["ema50"]) / daily["c"]
    daily["inside"] = ((daily["h"] <= daily["prev_h"]) & (daily["l"] >= daily["prev_l"])).astype(int)
    daily["dir_prev"] = np.sign(daily["c"] - daily["prev_c"])

    if args.last:
        day = daily["ny_date"].iloc[-2]  # derniere journee complete
    else:
        day = pd.Timestamp(args.date).date()
    note(day, bars, daily)


if __name__ == "__main__":
    main()
