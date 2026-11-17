"""L'idee : une seule bougie 4H avec re-leveraging continu peut-elle faire 200 -> 1M ?

Mecanique : a chaque barre M15, on re-deploie TOUTE l'equity comme marge :
  lots = u * levier * E / prix   (u = utilisation de marge, cap 500 lots)
  dE = lots * (close_{k+1} - close_k) * 1$/pt
Direction : celle de la bougie 4H (open -> close).
Si E <= 0 en cours de route -> ruine (un repli brutal dans la bougie).

Question 1 : les 20 plus grandes bougies 4H de 10 ans de donnees reelles.
Question 2 : pour chacune, combien 200 $ deviennent en rider toute la bougie.
Question 3 : sequences de 2-3 bougies 4H tendancielles consecutives (une "journee").
"""
import io
import sys
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location("oos", ROOT / "tools" / "orb_both_oos.py")
mod = importlib.util.module_from_spec(spec)
_old = sys.stdout; sys.stdout = io.StringIO()
spec.loader.exec_module(mod)
sys.stdout = sys.__stdout__

bars = mod.load_bars([
    "data_live/nas100_m15_kaggle_utc.parquet",
    "data_live/nas100_m15.parquet",
])
bars = bars.sort_values("time").reset_index(drop=True)
bars["h4"] = bars["time"].dt.floor("4h")

# ---------- aggregate 4H ----------
g = bars.groupby("h4").agg(
    open=("open", "first"), high=("high", "max"), low=("low", "min"),
    close=("close", "last"), n=("close", "count"),
).reset_index()
g["range_pts"] = g["high"] - g["low"]
g["dir"] = np.sign(g["close"] - g["open"])
print("=== TOP 15 PLUS GRANDES BOUGIES 4H (10 ans) ===")
top = g.sort_values("range_pts", ascending=False).head(15)
for _, row in top.iterrows():
    print(f"{row['h4']}  range={row['range_pts']:7.0f} pts ({row['range_pts']/row['close']*100:4.1f}%)  "
          f"dir={'HAUSSIERE' if row['dir']>0 else 'BAISSIERE'}  O={row['open']:.0f} C={row['close']:.0f}")
print()

# ---------- ride la bougie, barre M15 par barre ----------
def ride_candle(start_time, direction, e0=200.0, u=1.0, levier=2000.0,
                cap_lots=500.0, tick_per_pt=1.0):
    """Retourne (equity_finale, points_parcourus, ruine)."""
    m15 = bars[(bars["time"] >= start_time) &
               (bars["time"] < start_time + pd.Timedelta(hours=4))]
    if len(m15) < 2:
        return e0, 0.0, False
    E = e0
    for i in range(len(m15) - 1):
        price_now = float(m15.iloc[i]["close"])
        price_next = float(m15.iloc[i + 1]["close"])
        lots = min(u * levier * E / price_now, cap_lots)
        if lots <= 0:
            return 0.0, 0.0, True
        dP = direction * (price_next - price_now)
        E += lots * dP * tick_per_pt
        if E <= 0:
            return 0.0, 0.0, True
    return E, direction * (float(m15.iloc[-1]["close"]) - float(m15.iloc[0]["open"])), False

print("=== 200 $ RIDES LES 15 PLUS GRANDES BOUGIES (100% marge, levier 2000, cap 500 lots) ===")
print("(theorique maximum : aucune retracement tolere entre deux barres M15)")
print(f"{'bougie':>22} {'range':>8} {'dir':>10} {'E finale':>14} {'ruine':>6}")
for _, row in top.iterrows():
    E, pts, ruin = ride_candle(row["h4"], row["dir"])
    print(f"{str(row['h4'])[:16]:>22} {row['range_pts']:8.0f} "
          f"{'HAUSSE' if row['dir']>0 else 'BAISSE':>10} {E:>14,.0f} {'OUI' if ruin else 'non':>6}")
print()

print("=== meme chose avec 50% de marge (buffer de survie au bruit) ===")
for _, row in top.head(8).iterrows():
    E, pts, ruin = ride_candle(row["h4"], row["dir"], u=0.5)
    print(f"{str(row['h4'])[:16]:>22} range={row['range_pts']:7.0f}  E={E:>12,.0f}  ruine={'OUI' if ruin else 'non'}")
print()

# ---------- sequences de 2-3 bougies 4H tendancielles (journee extreme) ----------
print("=== JOURNEES EXTREMES : somme des ranges 4H par jour calendaire (UTC) ===")
g["date_utc"] = g["h4"].dt.date
day_range = g.groupby("date_utc").agg(total_range=("range_pts", "sum"),
                                      n_candles=("range_pts", "count"),
                                      net_move=("close", "last")).reset_index()
# net move reel du jour : prix de fin - prix de debut du jour
daily = bars.groupby(bars["time"].dt.date).agg(o=("open", "first"), c=("close", "last"))
day_range = day_range.merge(daily, left_on="date_utc", right_index=True)
day_range["net_pts"] = day_range["c"] - day_range["o"]
extreme = day_range.sort_values("total_range", ascending=False).head(10)
print(f"{'jour':>12} {'somme ranges 4H':>16} {'mouvement net':>14}")
for _, row in extreme.iterrows():
    print(f"{str(row['date_utc']):>12} {row['total_range']:16.0f} {row['net_pts']:+14.0f}")
print()

# meilleur jour : ride toutes les bougies 4H du jour dans le sens de chacune,
# mais strategie reelle = suivre le sens NET du jour du debut a la fin
print("=== RIDER LE JOUR NET (m15 par m15, sens du jour, 100% marge, cap 500 lots) ===")
for _, row in extreme.head(6).iterrows():
    day = bars[bars["time"].dt.date == row["date_utc"]].sort_values("time")
    direction = np.sign(row["net_pts"])
    E = 200.0
    ruin = False
    for i in range(len(day) - 1):
        price_now = float(day.iloc[i]["close"])
        price_next = float(day.iloc[i + 1]["close"])
        lots = min(2000.0 * E / price_now, 500.0)
        dP = direction * (price_next - price_now)
        E += lots * dP
        if E <= 0:
            ruin = True
            break
    print(f"{str(row['date_utc']):>12} net={row['net_pts']:+7.0f} pts  "
          f"E finale = {E:>14,.0f} $  ruine={'OUI' if ruin else 'non'}")
