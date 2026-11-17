# Analyse marché USTECm — multi-timeframes < 1 an + order flow

Généré le 2026-11-15 par `tools/market_analysis_mtf.py`.
Fenêtre : **2025-11-09 → 2026-11-08** (12 mois, 23 520 barres M15).
Sorties détaillées : `out_market_analysis/` (structure par TF, flux horaire,
volume profile, stats d'ouverture).

## Limitation importante

**Pas d'order book ni de ticks bid/ask historiques** : MT5 n'archive pas la
profondeur de marché, et le dataset disponible est M15 OHLCV uniquement.
L'analyse utilise donc des **proxies d'order flow** dérivés des bougies
(delta, absorption, ratio achat/vente). Le vrai order book est capté en live
depuis lundi via l'EA `DOM_Recorder` (voir plus bas).

## 1. Structure par timeframe

| TF | Return 1 an | S1 (6 mois) | S2 (6 mois) | > EMA20 | ATR |
|---|---|---|---|---|---|
| M15 | +6,9 % | +15,2 % | **-7,2 %** | 54 % | 0,31 % |
| M30 | +7,1 % | +15,4 % | -7,2 % | 55 % | 0,52 % |
| H1 | +7,0 % | +15,3 % | -7,2 % | 56 % | 0,75 % |
| H4 | +7,0 % | +15,7 % | -7,6 % | 56 % | 1,67 % |
| D1 | +7,0 % | +15,6 % | -7,5 % | 67 % EMA20>EMA50 | 2,66 % |

- Tous les timeframes racontent la même chose : **montée forte S1
  (mai-nov 2025 → sommets ~31 405), correction baissière S2**.
- Le prix est à **49 % du range annuel** (22 801 – 31 405), à mi-chemin.
- Consensus de tendance nul (54 % au-dessus EMA20 partout) → **marché en
  transition / range**, pas de régime directionnel dominant.

## 2. Order flow (proxies M15)

- **Ratio buy/sell volume : 0,935** → flux légèrement vendeur sur l'année.
- **Corrélation delta cumulé vs prix : -0,18** → le delta proxy ne mène pas
  le prix ; le marché consomme le volume sans le suivre (absorption).
- **Bougies d'absorption** (vol ≥ p80, corps ≤ p30) : 3,4 % des barres ;
  seulement **27,6 % de reversal** après une absorption haussière → les gros
  volumes en petits corps ici continuent plus souvent qu'ils ne retournent.
- **Delta par heure NY** (session US) :

| Heure | Volume | Ratio B/S | Biais |
|---|---|---|---|
| 09:00-10:00 | 17,4 M | 1,00 | équilibré (range 09:30-09:45) |
| 10:00-11:00 | **21,2 M** | 0,95 | légèrement vendeur |
| 11:00-12:00 | 13,5 M | 1,03 | acheteur |
| 12:00-13:00 | 10,0 M | **0,81** | **vendeur fort** |
| 13:00-16:00 | 24,9 M | 0,86-0,89 | vendeur |

- **Volume horaire** : le range 09:30-09:45 concentre **12,6 % du volume
  journalier** (barre la plus liquide de la journée), puis décroissance
  continue jusqu'à 15h.

Lecture : le flux realité vendeur en après-midi (12h-15h NY) — les longs ORB
tenus tard dans la journée affrontent un flow contraire. Les cibles rapides
(1R-2R) sont mieux alignées avec ce régime que les longs holds 3R.

## 3. Volume profile (1 an, bins 10 pts)

- **POC : 29 445** — cluster de volume massif **29 400-29 550** (tous les
  top-8 HVN sont dans cette zone).
- **Value area 70 % : 24 645 – 31 035** (très large, année directionnelle).
- Prix actuel **27 024** : dans la value area mais **2 400 pts sous le POC**.
- **LVN notables** : 25 375 et la zone creuse **25 825-25 935**.

Lecture : le marché a quitté le plateau de volume 29 400-29 550 ; entre
26 000 et 29 400 le volume est plus mince → mouvements potentiellement plus
rapides (moins de murs de liquidité). La zone 25 825-25 935 est un trou :
traversée rapide probable si le prix y arrive.

## 4. Comportement d'ouverture 09:30 (257 jours)

- Cassure du high du range : **77 %** des jours ; du low : **73 %**.
- Range OR moyen : **143,8 pts** (médiane 133) — OR large cette année.
- **Corrélation taille OR ↔ amplitude du jour : 0,57** → un OR étroit
  prédit un jour plus calme ; un OR large un jour plus ample. Le filtre
  `RangeRankMax` (désactivé) a une base statistique réelle ici.

## 5. Journalier (D1)

- Jours haussiers : 53 % ; jours > +1 % : 58 ; jours < -1 % : 58 (symétrie).
- Pire jour : **-6,7 %** ; meilleur : +4,4 % ; **drawdown buy&hold : -15,2 %**.

## 6. Implications pour le bot ORB BOTH

1. **Régime actuel défavorable au 3R** : flux vendeur l'après-midi + marché
   range → cibles 1R-2R plus adaptées (conforme à la décision d'aller sur 1R).
2. **Entries 11h-15h contre le flow** : le filtre momentum reste critique ;
   un filtre "delta heure" (interdire les longs après 13h NY) est une piste
   testable avec ces données.
3. **OR rank** : réactiver `InpUseRangeRankFilter` est statistiquement
   justifié (corr 0,57 OR↔amplitude du jour).
4. **Zones clés live** : support de volume 25 825-25 935 (LVN), aimant POC
   29 445, cluster 29 400-29 550 = résistance majeure.

## 7. Order book en live — EA DOM_Recorder

`mql5/orb_portfolio/DOM_Recorder.mq5` (compilé, installé dans le terminal) :
- Capte la **profondeur de marché** (bids/asks × volumes, jusqu'à 10 niveaux)
  à chaque mise à jour du book (`OnBookEvent`) + chaque tick (bid/ask/last).
- Écrit `MQL5/Files/dom_records.csv` — **lecture seule, aucun ordre**.
- Après 1-2 semaines de capture, on pourra reconstruire le vrai order flow
  (delta bid/ask, imbalance du book, absorption au niveau) et calibrer
  l'agressivité du bot sur des données réelles de profondeur.

Attacher lundi : ouvrir un 2e graphique USTECm M1 dans le terminal démo et
y glisser `DOM_Recorder` (auto-trading activé, pas d'ordre envoyé).
