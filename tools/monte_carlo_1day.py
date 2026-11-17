"""Monte Carlo : 200 $ -> 1 000 000 $ en UNE SEULE journee, 1RR.

Contraintes reelles du compte :
- session USTEC ~23h -> max ~500 trades/jour viables (plafond spread)
- winrate p, risque r % du solde par trade (1RR), compound (lots augmentent)
- cout spread/commission : c R par trade (les deux cotes)
- CAP de capacite : max 500 lots = 500 $/pt -> risque max par trade
  = 500 lots * stop_pts * 1 $/pt (sinon impossible d'executer la taille)

Sortie : probabilite d'atteindre 1M avant la fin du jour, mediane, ruine.
"""
import numpy as np

RNG = np.random.default_rng(42)
START = 200.0
TARGET = 1_000_000.0
MAX_TRADES = 500          # plafond viable/jour (spread)
STOP_PTS = 20.0           # stop typique scalper
MAX_LOTS = 500.0          # volume max USTECr
COST_R = 0.10             # cout all-in en fraction de R (0.7pt / 7pt stop ~ 0.1)

def run(p, r, sessions=20_000, trades=MAX_TRADES, verbose=True):
    balance = np.full(sessions, START)
    hit = np.zeros(sessions, dtype=bool)
    ruin = np.zeros(sessions, dtype=bool)
    peak_dd = np.zeros(sessions)
    peak = balance.copy()
    for _ in range(trades):
        alive = ~hit & ~ruin
        if not alive.any():
            break
        bal = balance[alive]
        risk_money = bal * r
        # cap de capacite : lots = risk/(stop*1$) <= 500
        eff_risk = np.minimum(risk_money, MAX_LOTS * STOP_PTS)
        lots = eff_risk / STOP_PTS
        win = RNG.random(len(bal)) < p
        r_mult = np.where(win, 1.0 - COST_R, -(1.0 + COST_R))
        pnl = eff_risk * r_mult
        newbal = bal + pnl
        dead = newbal < STOP_PTS * 0.05 / 1.0  # plus assez pour trader min lot
        balance[alive] = newbal
        ruin[alive] = dead
        reached = (newbal >= TARGET) & ~dead
        hit[alive] = reached
        peak[alive] = np.maximum(peak[alive], newbal)
        peak_dd[alive] = np.maximum(peak_dd[alive],
                                    1.0 - newbal / np.maximum(peak[alive], 1e-9))
    n = (~hit & ~ruin).sum()
    pct = lambda x: x.sum() / sessions * 100
    if verbose:
        print(f"p={p:.0%} risque={r:.0%} trades={trades} -> "
              f"1M atteint : {pct(hit):.2f}%  |  ruine : {pct(ruin):.2f}%  |  "
              f"en cours : {pct(~hit & ~ruin):.2f}%  |  "
              f"mediane finale : {np.median(balance):,.0f} $  |  "
              f"DD median chemin : {np.median(peak_dd)*100:.1f}%")
    return hit, ruin, balance


print("=== 200 $ -> 1M $ EN UNE JOURNEE (500 trades max, stop 20 pts, cap 500 lots) ===")
print()
print("--- winrate 55 % (realiste ORB/cout inclus) ---")
for r in (0.10, 0.20, 0.35, 0.50):
    run(0.55, r)
print()
print("--- winrate 60 % (tres bon scalper) ---")
for r in (0.10, 0.20, 0.30):
    run(0.60, r)
print()
print("--- winrate 70 % (exceptionnel, irrealiste en continu) ---")
for r in (0.20, 0.35, 0.50):
    run(0.70, r)
print()
print("--- cas limite : 1000 trades/jour (au-dela du plafond spread, pour reference) ---")
run(0.60, 0.20, trades=1000)
run(0.70, 0.35, trades=1000)
