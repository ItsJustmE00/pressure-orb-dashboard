"""Evaluation sans bruit de la strategie ORB 2R max2 (164+ trades reels).

Methodes :
1. Walk-forward annuel : coherence du rendement par annee
2. Significativite statistique : l'edge est-il du bruit ? (t-stat, bootstrap)
3. Monte-Carlo bootstrap jour-par-jour : distribution des futurs possibles
   pour plusieurs niveaux de risque, DD max, risk-of-ruin
4. Kelly reel : f* = mu / sigma^2 sur la distribution des R reels
5. Chemins de montee : 24 600 $ -> 1M $ attendu vs medians

Entree : out_orb_manage/trades_baseline.csv (R multiples nets de cout).
"""
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out_orb_manage"
RNG = np.random.default_rng(7)
ACC = 57_000.0

tr = pd.read_csv(OUT / "trades_baseline.csv", parse_dates=["date"])
tr = tr[tr["date"] >= "2022-01-01"]  # OOS + recent seulement
r_all = tr["r_multiple"].to_numpy(float)

print(f"trades 2022-2026 : {len(r_all)}  avgR={r_all.mean():.3f}  "
      f"std={r_all.std():.3f}  wr={(r_all>0).mean():.1%}")
print()

# ---------- 1. walk-forward annuel ----------
print("=== 1. WALK-FORWARD PAR ANNEE ===")
for y in range(2022, 2027):
    ry = tr[tr["date"].dt.year == y]["r_multiple"].to_numpy(float)
    if len(ry) == 0:
        continue
    eq = np.prod(1 + 0.005 * ry)
    print(f"{y} : {len(ry):>3} trades  avgR={ry.mean():+.3f}  "
          f"return={100*(eq-1):+6.2f}%  wr={(ry>0).mean():5.1%}  "
          f"{'OK' if ry.mean() > 0 else 'NEGATIF'}")
print()

# ---------- 2. l'edge est-il du bruit ? ----------
print("=== 2. SIGNIFICATIVITE (edge vs chance) ===")
mu = r_all.mean()
se = r_all.std() / np.sqrt(len(r_all))
t = mu / se
print(f"t-stat = {t:.2f} (seuil usuel > 2.0)")
# bootstrap du avgR : distribution si le hasard rejouait les memes trades
boot = [RNG.choice(r_all, size=len(r_all), replace=True).mean() for _ in range(10_000)]
boot = np.array(boot)
print(f"bootstrap avgR : p5={np.percentile(boot,5):+.3f}  "
      f"p50={np.median(boot):+.3f}  p95={np.percentile(boot,95):+.3f}")
print(f"P(avgR<=0 sous bootstrap) = {(boot<=0).mean()*100:.2f}%  "
      f"(faible = l'edge n'est pas un artefact)")
# max DD de la sequence reelle vs sequences melangees
def seq_dd(r, risk=0.005):
    eq = np.cumprod(1 + risk * r)
    peak = np.maximum.accumulate(np.concatenate([[1.0], eq]))
    dd = 1 - np.concatenate([[1.0], eq]) / peak
    return dd.max()
real_dd = seq_dd(r_all)
shuffled_dd = np.array([seq_dd(RNG.permutation(r_all)) for _ in range(5_000)])
print(f"max DD reel (ordre chronologique) : {real_dd*100:.2f}%  |  "
      f"DD des sequences melangees : p50={np.median(shuffled_dd)*100:.1f}%  "
      f"p95={np.percentile(shuffled_dd,95)*100:.1f}%")
print()

# ---------- 3. Kelly reel ----------
print("=== 3. KELLY REEL (distribution des R reelle) ===")
var = r_all.var(ddof=1)
f_kelly = mu / var
print(f"mu={mu:.4f}  sigma2={var:.4f}  -> f* = mu/sigma2 = {f_kelly:.3f} "
      f"({f_kelly*100:.0f}% du solde par trade)")
print(f"half-Kelly conseille : {f_kelly*50:.1f}%")
print()

# ---------- 4. Monte-Carlo bootstrap : futurs possibles ----------
print("=== 4. MONTE-CARLO BOOTSTRAP (250 jours de bourse = ~1 an, ~2 trades/j) ===")
print("resampling jour-par-jour des vrais trades (conserve le clustering)")
day_groups = [g["r_multiple"].to_numpy(float) for _, g in tr.groupby("date")]
n_days_year = 250

def mc_year(risk, n_sim=10_000, days=n_days_year):
    finals = np.empty(n_sim)
    maxdds = np.empty(n_sim)
    for s in range(n_sim):
        bal = ACC
        peak = bal
        dd = 0.0
        for _ in range(days):
            g = day_groups[RNG.integers(len(day_groups))]
            for v in g:
                bal *= 1 + risk * v
            peak = max(peak, bal)
            dd = max(dd, 1 - bal / peak)
        finals[s] = bal
        maxdds[s] = dd
    return finals, maxdds

for risk in (0.005, 0.01, 0.02, 0.04):
    finals, mdds = mc_year(risk)
    print(f"risque {risk*100:.1f}% : median {np.median(finals):>9,.0f}$  "
          f"p5 {np.percentile(finals,5):>9,.0f}$  p95 {np.percentile(finals,95):>9,.0f}$  "
          f"DD median {np.median(mdds)*100:5.1f}%  DD p95 {np.percentile(mdds,95)*100:5.1f}%  "
          f"P(x2)={(finals>=2*ACC).mean()*100:.0f}%  P(perdu)={(finals<ACC).mean()*100:.0f}%")
print()

# ---------- 5. chemins de montee vers 1M ----------
print("=== 5. CHEMINS 24 600 $ -> 1M (monte-carlo, ~500 trades/an) ===")
BAL0 = 24_597.71
def mc_to_target(risk, target=1_000_000, years=15, n_sim=10_000):
    hits, ruins, years_to = [], [], []
    day_cap = int(years * n_days_year)
    for s in range(n_sim):
        bal = BAL0
        peak = bal
        dd = 0.0
        hit_day = None
        ruin = False
        for d in range(day_cap):
            g = day_groups[RNG.integers(len(day_groups))]
            for v in g:
                bal *= 1 + risk * v
            if bal <= 500:
                ruin = True
                break
            peak = max(peak, bal)
            dd = max(dd, 1 - bal / peak)
            if hit_day is None and bal >= target:
                hit_day = d
                break
        if hit_day is not None:
            hits.append(1); years_to.append(hit_day / n_days_year)
        else:
            hits.append(0)
        ruins.append(1 if ruin else 0)
    return np.mean(hits), np.mean(ruins), years_to

for risk, label in ((0.005, "0,5 % (actuel)"), (0.01, "1 %"), (0.02, "2 %"),
                    (0.04, "4 %"), (0.08, "8 % (au-dessus half-Kelly)")):
    p_hit, p_ruin, yrs = mc_to_target(risk)
    med = np.median(yrs) if yrs else float("nan")
    print(f"risque {label:>28} : P(1M en <=15 ans) = {p_hit*100:5.1f}%  "
          f"ruine avant = {p_ruin*100:4.1f}%  annees medianes = {med:.1f}")
