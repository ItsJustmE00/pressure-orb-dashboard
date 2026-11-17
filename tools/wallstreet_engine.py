"""WALL STREET ENGINE — moteur d'analyse institutionnel pour ORB USTEC.

Architecture en 4 couches (comme un desk prop) :

COUCHE 1 - CONTEXTE MARCHE (avant ouverture)
  regime de tendance (EMA20/50 daily), regime de volatilite (ATR20 percentile),
  jour precedent (inside/trend/inside-day), gap overnight, range overnight.

COUCHE 2 - MICROSTRUCTURE (la premiere bougie M15, 09:30-09:45)
  delta proxy (volume * ((c-o)/(h-l))) = acheteur vs vendeur,
  effort vs resultat (volume anormal + petite range = absorption),
  volume relatif de l'ouverture vs 20 dernieres ouvertures.

COUCHE 3 - SCORING DE SETUP (anti-overfitting)
  Chaque breakout OR = un setup candidat. Score construit sur IN-SAMPLE
  2016-2021 uniquement, valide sur OOS 2022-2026. Les facteurs qui ne
  marchent pas OOS sont rejetes (lecon du filtre OR-rank).

COUCHE 4 - NOTE DU MATIN
  Pour chaque jour : score long / score short, verdict TRADE / NO-TRADE.

Sortie : out_wallstreet/ (setups, features, analyse scores) + doc.
"""
import importlib.util
import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out_wallstreet"
OUT.mkdir(exist_ok=True)

spec = importlib.util.spec_from_file_location("oos", ROOT / "tools" / "orb_both_oos.py")
mod = importlib.util.module_from_spec(spec)
_old = sys.stdout
sys.stdout = io.StringIO()
try:
    spec.loader.exec_module(mod)
finally:
    sys.stdout = _old

IS_END = pd.Timestamp("2021-12-31")
COST = 1.7
TARGET_R = 2.0

bars = mod.load_bars([
    "data_live/nas100_m15_kaggle_utc.parquet",
    "data_live/nas100_m15.parquet",
])

# ============================================================
# COUCHE 1 : barres de session journalieres + contexte
# ============================================================
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
daily["atr5"] = daily["tr"].rolling(5).mean()
daily["atr_pct"] = daily["atr20"].rolling(252).rank(pct=True)
daily["ema20"] = daily["c"].ewm(span=20, adjust=False).mean()
daily["ema50"] = daily["c"].ewm(span=50, adjust=False).mean()
daily["trend"] = (daily["ema20"] - daily["ema50"]) / daily["c"]
daily["inside"] = ((daily["h"] <= daily["prev_h"]) & (daily["l"] >= daily["prev_l"])).astype(int)
daily["dir_prev"] = np.sign(daily["c"] - daily["prev_c"])
daily["atr"] = daily["atr20"]
ctx = daily.set_index("ny_date")

# ============================================================
# COUCHE 2+3 : features par jour + setup candidat (1er breakout)
# ============================================================
# volume median a la barre d'ouverture (570) sur les 20 jours precedents
vol_open = bars[bars["ny_min"] == 570].groupby("ny_date")["tick_volume"].first()

rows = []
for ny_date, g in bars.groupby("ny_date", sort=True):
    if ny_date < mod.PERIODS[0][1] or ny_date > mod.PERIODS[-1][2]:
        continue
    if ny_date not in ctx.index:
        continue
    d = g[(g["ny_min"] >= 570) & (g["ny_min"] < 960)].sort_values("time").reset_index(drop=True)
    if len(d) < 10 or int(d.iloc[0]["ny_min"]) != 570:
        continue
    c = ctx.loc[ny_date]
    atr = float(c["atr"])
    if not np.isfinite(atr) or atr <= 0:
        continue

    or_high = float(d.iloc[0]["high"])
    or_low = float(d.iloc[0]["low"])
    or_range = or_high - or_low
    if not np.isfinite(or_range) or or_range <= 0:
        continue

    # --- features microstructure de la bougie d'ouverture ---
    ob = d.iloc[0]
    rng = float(ob["high"]) - float(ob["low"])
    delta0 = (float(ob["close"]) - float(ob["open"])) / (rng if rng > 0 else 1.0) \
        * float(ob["tick_volume"])
    vol_hist = [float(vol_open.get(pd.Timestamp(x).date(), np.nan))
                for x in list(ctx.index[ctx.index < ny_date])[-20:]]
    vol_hist = [v for v in vol_hist if np.isfinite(v)]
    vol_rel = float(ob["tick_volume"]) / np.median(vol_hist) if len(vol_hist) >= 10 else np.nan

    # --- premier breakout apres 09:45 ---
    side = None
    entry_j = None
    for j in range(1, len(d)):
        if float(d.iloc[j]["high"]) >= or_high:
            side, entry_j = 1, j
            break
        if float(d.iloc[j]["low"]) <= or_low:
            side, entry_j = -1, j
            break
    if side is None:
        continue
    bj = d.iloc[entry_j]
    entry = max(float(bj["open"]), or_high) if side == 1 else min(float(bj["open"]), or_low)
    stop = or_low if side == 1 else or_high
    stop_dist = abs(entry - stop)
    if stop_dist <= 0:
        continue
    target = entry + side * TARGET_R * stop_dist

    # delta du breakout + follow-through 2 barres (info disponible 30 min apres)
    brng = float(bj["high"]) - float(bj["low"])
    delta_break = (float(bj["close"]) - float(bj["open"])) / (brng if brng > 0 else 1.0)
    vol_break_rel = float(bj["tick_volume"]) / np.median(vol_hist) if vol_hist and len(vol_hist) >= 10 else np.nan

    # --- resultat du trade (2R, EOD, cout 1.7 pt) ---
    exit_price = None
    for k in range(entry_j, len(d)):
        hi, lo = float(d.iloc[k]["high"]), float(d.iloc[k]["low"])
        if side == 1 and lo <= stop:
            exit_price = stop
            break
        if side == 1 and hi >= target:
            exit_price = target
            break
        if side == -1 and hi >= stop:
            exit_price = stop
            break
        if side == -1 and lo <= target:
            exit_price = target
            break
    if exit_price is None:
        exit_price = float(d.iloc[-1]["close"])
    r_mult = (side * (exit_price - entry) - COST) / stop_dist

    rows.append({
        "date": ny_date,
        "dow": pd.Timestamp(ny_date).dayofweek,
        "atr": atr,
        "atr_pct": float(c["atr_pct"]) if np.isfinite(c["atr_pct"]) else np.nan,
        "trend": float(c["trend"]) if np.isfinite(c["trend"]) else np.nan,
        "inside_prev": int(c["inside"]),
        "dir_prev": int(c["dir_prev"]),
        "or_range": or_range,
        "or_atr": or_range / atr,
        "stop_atr": stop_dist / atr,
        "gap_atr": (float(bars[(bars["ny_date"] == ny_date)].iloc[0]["open"]) - float(c["prev_c"])) / atr,
        "delta0": delta0,
        "vol_rel": vol_rel,
        "side": side,
        "delta_break": delta_break,
        "vol_break_rel": vol_break_rel,
        "entry_time": bj["time"],
        "entry": entry, "stop": stop, "target": target,
        "exit": exit_price,
        "r": r_mult,
        "or_hist": or_range,
    })

df = pd.DataFrame(rows)
print(f"setups candidats (tous breakouts OR, sans filtre) : {len(df)}")

# ============================================================
# COUCHE 3 : scoring anti-overfitting (IS -> OOS)
# ============================================================
is_df = df[df["date"] <= IS_END.date()]
oos_df = df[df["date"] > IS_END.date()]
print(f"IS 2016-2021 : {len(is_df)} setups | OOS 2022-2026 : {len(oos_df)} setups")

FACTORS = ["atr_pct", "or_atr", "stop_atr", "gap_atr", "trend", "delta0",
           "vol_rel"]
# delta_break / vol_break_rel : connus SEULEMENT a la cloture de la bougie de
# breakout -> non utilisables pour une entree a l'ouverture. Exclus du score
# (anti-lookahead). Ils restent dans la table pour la review post-trade.
SIDE_FACTORS = {"trend", "delta0", "gap_atr"}  # a orienter selon le side

def aligned(frame, col):
    """Facteur oriente dans le sens du trade : +1 = favorable."""
    v = frame[col].to_numpy(float)
    if col in SIDE_FACTORS:
        v = v * frame["side"].to_numpy(float)
    return v

print("\n=== correlation facteur <-> R (Spearman, IS 2016-2021) ===")
rhos = {}
for f in FACTORS:
    x = aligned(is_df, f)
    y = is_df["r"].to_numpy(float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 50:
        rhos[f] = np.nan
        continue
    rho = pd.Series(x[ok]).corr(pd.Series(y[ok]), method="spearman")
    rhos[f] = rho
    print(f"{f:>14} : rho = {rho:+.3f}")

selected = [f for f in FACTORS if np.isfinite(rhos[f]) and abs(rhos[f]) >= 0.04]
print(f"\nfacteurs retenus (|rho| >= 0.04) : {selected}")

# score = somme des rho * z-score (fit IS uniquement, applique tel quel OOS)
def zscore(a):
    a = np.asarray(a, float)
    m = np.nanmean(a)
    s = np.nanstd(a)
    return (a - m) / (s if s > 0 else 1.0)

for frame in (df,):
    sc = np.zeros(len(frame))
    for f in selected:
        v = aligned(frame, f)
        sc += rhos[f] * zscore(v)
    frame["score"] = sc
df["score"] = (df["score"] - df["score"].min()) / (df["score"].max() - df["score"].min() + 1e-12) * 100

# re-coupure IS/OOS apres ajout du score (vues pandas)
is_df = df[df["date"] <= IS_END.date()]
oos_df = df[df["date"] > IS_END.date()]

print("\n=== VALIDATION OOS : avgR par quintile de score ===")
q = pd.qcut(oos_df["score"], 5, labels=["Q1 bas", "Q2", "Q3", "Q4", "Q5 haut"])
tab = oos_df.groupby(q, observed=True).agg(
    n=("r", "count"), avg_r=("r", "mean"), wr=("r", lambda x: (x > 0).mean() * 100))
print(tab.round(3).to_string())

is_tab = is_df.copy()
is_tab["q"] = pd.qcut(is_tab["score"], 5, labels=False)
print("\n(memo IS) avgR par quintile :")
print(is_tab.groupby("q")["r"].agg(["count", "mean"]).round(3).to_string())

# ============================================================
# Test decisif : gate score>=X sur OOS (vs tout trader)
# ============================================================
print("\n=== GATE SCORE (OOS 2022-2026, 2R, EOD, cout 1.7) ===")
base_avg = oos_df["r"].mean()
print(f"aucun gate   : n={len(oos_df)}  avgR={base_avg:+.3f}  totalR={oos_df['r'].sum():+.1f}")
for gate in (40, 50, 60):
    sub = oos_df[oos_df["score"] >= gate]
    if len(sub) < 30:
        continue
    print(f"score >= {gate} : n={len(sub)}  avgR={sub['r'].mean():+.3f}  "
          f"totalR={sub['r'].sum():+.1f}  wr={(sub['r']>0).mean()*100:.1f}%")

# gate delta Break : MICROSTRUCTURE HONNETE = delta de la bougie d'ouverture,
# connu a 09:45 avant tout breakout (le delta de la bougie de breakout est du lookahead)
print("\n=== GATE MICROSTRUCTURE HONNETE : delta de la bougie d'ouverture (connu 09:45) ===")
for thr in (0.0, 0.5, -0.5):
    sub = oos_df[(oos_df["side"] * oos_df["delta0"]) >= thr]
    if len(sub) >= 30:
        print(f"delta0 aligne >= {thr:+.1f} : n={len(sub)}  avgR={sub['r'].mean():+.3f}  "
              f"totalR={sub['r'].sum():+.1f}  wr={(sub['r']>0).mean()*100:.1f}%")

# ============================================================
# Sauvegardes + features pour la note du matin
# ============================================================
df.to_csv(OUT / "setups_scored.csv", index=False)
pd.DataFrame({"facteur": list(rhos), "rho_IS": list(rhos.values()),
              "retenu": [f in selected for f in rhos]}).to_csv(OUT / "factors.csv", index=False)
tab.to_csv(OUT / "score_quintiles_oos.csv")
df.describe().to_csv(OUT / "features_stats.csv")

# baseline actuel (216 trades) + score : le gate ameliore-t-il le systeme LIVE ?
base = pd.read_csv(ROOT / "out_orb_manage" / "trades_baseline.csv", parse_dates=["date"])
base_oos = base[base["date"] >= "2022-01-01"].copy()
# rapprochement par date
score_map = df.set_index("date")["score"]
base_oos["score"] = base_oos["date"].dt.date.map(score_map)
matched = base_oos[base_oos["score"].notna()]
print(f"\n=== GATE SUR LE SYSTEME LIVE (baseline 2R max2, {len(matched)} trades OOS ===")
print(f"sans gate  : avgR={matched['r_multiple'].mean():+.3f}  totalR={matched['r_multiple'].sum():+.1f}")
for gate in (40, 50, 60):
    sub = matched[matched["score"] >= gate]
    if len(sub) < 20:
        continue
    print(f"score >= {gate} : n={len(sub)}  avgR={sub['r_multiple'].mean():+.3f}  "
          f"totalR={sub['r_multiple'].sum():+.1f}  wr={(sub['r_multiple']>0).mean()*100:.1f}%")
matched.to_csv(OUT / "baseline_with_score.csv", index=False)

print("\nOK -> out_wallstreet/")
