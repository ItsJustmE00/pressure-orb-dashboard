# Plan 57 000 USD — ORB NAS100 + US30

Objectif : viser **50 $/jour en moyenne**, pas 50 $/jour garanti. Compte simulé :
57 000 USD. Risque historique de référence : **0,5 % par trade et par
instrument** (285 USD) ; les tests filtrés récents utilisent 2,5–3,0 %.
Aucun ordre réel n'est autorisé.

## Règles

- Instruments : `USTECm` (NAS100) et `US30m` (Dow Jones 30).
- Session : 09:30-16:00 New York.
- Opening range : première barre M15 (09:30-09:45 NY), high/low.
- Entrée : cassure du high (long) ou du low (short).
- Stop : côté opposé de l'opening range.
- Target : 3R.
- Sortie : stop, target, ou fermeture de sécurité à **15:55 NY** (15:50 le
  vendredi) pour éviter la fermeture broker de 16:00 NY.
- Maximum : 1 trade par instrument et par jour ; pas de re-entrée, pas de
  martingale, pas d'ajout à une position perdante.
- Coûts de base : 1,7 point NAS100, 2,5 points US30. Coûts conservateurs :
  2,5 et 4,0 points.

## Résultats historiques (2016-10 → 2025-09)

| Scénario | Jours | Moyenne/jour | Total | Max DD | Jours gagnants |
|---|---:|---:|---:|---:|---:|
| Coûts de base | 2 276 | **49,74 $** | 113 197,77 $ | 14 163,96 $ (24,8 %) | 43,4 % |
| Coûts conservateurs | 2 276 | 36,14 $ | 82 255,05 $ | 17 715,79 $ (31,1 %) | 42,7 % |

- IS 2017-2021 (base) : 58,92 $/jour ; OOS 2022-2025 : 37,10 $/jour.
- OOS conservateur : 28,84 $/jour.
- Médiane quotidienne négative (base : −158,44 $) : l'edge dépend de quelques
  grosses journées ; la majorité des jours perdent.
- Capital nécessaire pour 50 $/jour : **57 298 $** avec les coûts de base,
  **78 860 $** avec les coûts conservateurs.
- Sur 24 592,71 $, le même plan ne produit que ~21,46 $/jour (base), avec un
  max DD de ~6 111 $ (24,8 %).

## Validation récente — ORB non filtré négatif

Sur 2025-09-21 → 2026-11-08 (M15 réels `USTECm`) :

- Variante 9 ans range=1/target=3R : **269 trades, −1 072,60 $**, soit
  −3,02 $/jour.
- Meilleur ORB NAS100 récent (range=2, target=4R) : +1,45 $/jour, p ajustée
  **0,62**.
- US30 récent : +4,07 $/jour, p ajustée 0,42.
- US500 récent : +7,74 $/jour, p ajustée 0,33.

L'edge ORB non filtré n'est pas présent sur les 14 derniers mois.

## Mise à jour 2026-11-12 — filtre tendance, test direct MT5

Configuration testée dans le Strategy Tester, compte simulé **57 000 USD**,
`USTECm` M15, ticks réels, **2026-01-01 → 2026-09-15**, aucun trade réel :

- Opening range 09:30-09:45 NY ; stop = côté opposé ; target 3R ; sortie 16:00 NY.
- **Long uniquement**.
- Filtre : `(EMA20 D1 − EMA50 D1) / close D1 < 0,00425` sur la dernière barre
  daily clôturée.
- Risque **2,5 % par trade**, un trade maximum par jour.
- Résultat : solde final **66 337,63 $**, soit **+9 337,63 $ (+16,38 %)**.
- 79 trades, 46,8 % de gagnants, **max DD 19,8 %**, R moyen +0,095.
- Même EA non filtré, 0,5 % de risque : solde final 49 816,68 $, **−12,6 %**.
- Variante 1,5 % : +10,48 %, max DD 12,3 %.
- Variante 3,0 % : +18,92 %, max DD 23,3 %.
- Variante agressive `InpTrendMax=0,002` à 2,5 % : +29,77 %, max DD 19,8 %,
  53 trades — moins robuste sur les données 2025-2026, à ne pas retenir comme
  base.

Conclusion : **première combinaison positive en test direct MT5**. Le seuil
2,5 % est agressif ; le drawdown historique OOS 2022-2025 du filtre
NAS100 peut approcher 40 %. Ce n'est pas une garantie et cela reste démo uniquement.

Configs : `out_orb_portfolio_57k/tester_ustecm_trend_25.ini` (base),
`tester_ustecm_trend_3.ini`, `tester_ustecm_filtered.ini`.

## Mise à jour 2026-11-13 — entrées chirurgicales

Features construites sans look-ahead sur barres M15 clôturées : force de
l'opening range, position de clôture, volume relatif, momentum 3/6 barres, RSI,
distance aux niveaux de la veille, volatilité. Le scan par quintiles et les
règles testées sont dans `out_orb_entry_scan/`.

Règle retenue, en plus du filtre tendance long-only :

- `or_close_pos = (close_09:30 − low_09:30) / (high_09:30 − low_09:30)`.
- `prev_mom6 = close[1] / close[7] − 1` sur M15, barres 1 à 7 clôturées.
- Filtre : `or_close_pos > 0,8044` **et** `prev_mom6 > 0,00123`.
- Tout est connu à 09:45 NY ; aucun OHLC de la barre de déclenchement n'est
  utilisé.

Tests directs MT5, `USTECm` M15, 57 000 USD, 2026-01-01 → 2026-09-15 :

| Variante | Risque | Trades | Gagnants | R moyen | Max DD | Solde final | Résultat |
|---|---:|---:|---:|---:|---:|---:|---:|
| Tendance seule (référence) | 2,5 % | 79 | 46,8 % | +0,095 | 19,81 % | 66 337,63 $ | +16,38 % |
| OR close seul | 2,5 % | 33 | 51,5 % | +0,106 | 11,94 % | 61 376,81 $ | +7,67 % |
| OR close + momentum | 2,5 % | 31 | 58,1 % | +0,185 | 8,08 % | 64 964,59 $ | +13,97 % |
| OR close + momentum | 3,0 % | 31 | 58,1 % | +0,185 | 9,65 % | 66 493,63 $ | +16,65 % |
| OR close + momentum + prev close | 2,5 % | 29 | 58,6 % | +0,119 | 7,33 % | 61 537,77 $ | +7,96 % |

Conclusion sur la fenêtre 2026 : **OR close + momentum à 3,0 %** offre le même
rendement que la référence (+16,65 % contre +16,38 %) avec un drawdown direct
deux fois plus faible (9,65 % contre 19,81 %) et 31 trades au lieu de 79, soit
~52,7 $/jour de bourse. À 2,5 %, la version conservatrice donne ~44 $/jour et
8,1 % de DD.

### Validation élargie : Q4 2025 et 12 mois

Les mêmes règles, inputs explicitement forcés (le tester MT5 hérite sinon des
inputs du test précédent), donnent :

| Période / variante | Trades | Gagnants | R moyen | Max DD | Solde final | Résultat |
|---|---:|---:|---:|---:|---:|---:|
| Q4 2025, BE 3,0 % | 5 | 20,0 % | −0,762 | 10,97 % | 50 749,74 $ | −10,96 % |
| Q4 2025, tendance seule 3,0 % | 16 | 37,5 % | −0,228 | 11,43 % | 50 161,59 $ | −12,00 % |
| 12 mois, BE 3,0 % | 36 | 52,8 % | +0,053 | 10,97 % | 59 204,30 $ | +3,87 % |
| 12 mois, tendance seule 3,0 % | 95 | 45,3 % | +0,040 | 23,15 % | 59 659,52 $ | +4,67 % |
| 2026, E+F (momentum + mèche) 3,0 % | 67 | 46,3 % | −0,018 | 21,50 % | 53 314,20 $ | −6,47 % |

Lecture : BE réduit fortement le drawdown, mais **ne tient pas l'objectif
50 $/jour sur 12 mois** (+3,87 %, soit ~8,6 $/jour de bourse) et fait moins bien
que la tendance seule en rendement total. Le Q4 2025 est perdant avec seulement
5 trades, donc non concluant statistiquement. Le filtre E+F (`prev_mom6` +
`prev_upper_wick`), prometteur en Python, est **rejeté** en test direct : les
heures d'entrée diffèrent et l'échantillon réel devient mauvais. Le +16,65 %
2026 est une fenêtre favorable, pas une preuve de robustesse.

### Recherche de 1 000 combinaisons

`tools/orb_1000_combos.py` évalue 1 000 combinaisons de 2 à 4 filtres sur les
features, avec seuils calibrés avant 2022 et contrainte d'échantillon
(`oos_n >= 25`, `y26_n >= 12`). Résultat : `out_orb_entry_scan/combos_1000.csv`.
Les meilleures combinaisons Python sont :

| Combinaison | OOS n / R | 2026 n / R | 12 mois n / R | Statut |
|---|---:|---:|---:|---|
| `range_pct_rank60 > 0,504` & `trend < 0,002378` | 91 / +0,386 | 19 / +0,464 | 20 / +0,494 | non testable directement (rang EA ≠ rang Python) |
| `prev_upper_wick < 0,2068` & `trend < 0,002378` | 94 / +0,396 | 22 / +0,373 | 23 / +0,403 | testé, rejeté |
| `trend < 0,002378` & `prev_mom6 > 0,00123` | 98 / +0,413 | 20 / +0,360 | 21 / +0,393 | **testé, retenu** |

Le test direct de `prev_upper_wick < 0,2068` + `trend < 0,002378` donne
**61 189,13 $** sur 2026 (+7,35 %, 55 trades, DD 24,67 %) : rejeté.

Le test direct de **BE avec `InpTrendMax=0.002378`** donne :

| Période | Trades | Gagnants | R moyen | Max DD | Solde final | Résultat |
|---|---:|---:|---:|---:|---:|---:|
| 2026 | 23 | 60,9 % | +0,214 | 9,65 % | 65 188,36 $ | +14,37 % |
| Q4 2025 | 2 | 50,0 % | −0,405 | 3,00 % | 55 605,82 $ | −2,44 % |
| 12 mois | 25 | 60,0 % | +0,165 | 9,65 % | 63 598,30 $ | **+11,58 %** |

C'est le meilleur résultat direct long-only sur 12 mois : le seuil de tendance
plus strict évite l'essentiel des pertes Q4, au prix de 2 trades seulement sur
Q4. Il reste loin de 50 $/jour (~18 $/jour sur 12 mois) et l'échantillon est
petit (25 trades). Les 1 000 combinaisons sont un **crible**, pas une
validation : la plupart des tops sont sur-ajustés.

### Extension short et stratégie BOTH

Le miroir short `S_OR+MOM+TREND4` (`or_close_pos < 0,1956`,
`prev_mom6 < −0,00123`, `trend_daily > −0,00425`) est additif : test direct
short-only 12 mois à 3,0 % = **62 242,93 $** (+9,20 %, 47 trades, 48,9 %,
R moyen +0,079, DD 11,66 %). L'EA dispose maintenant des inputs
`InpShortOnly`, `InpUseShortOrFilter`, `InpShortOrCloseMax`,
`InpUseShortMomFilter`, `InpShortMomMax`, `InpUseShortTrendFilter`,
`InpShortTrendMin`, et les filtres long ne s'appliquent plus qu'au long.

La variante **BOTH** combine BE002 long et son miroir short, avec un seul trade
par jour (le premier côté qui casse). Tests directs `USTECm` M15, 57 000 USD :

| Période | Risque | Trades | Gagnants | R moyen | Max DD | Solde final | Résultat | $/jour |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 12 mois | 3,0 % | 62 | 58,1 % | +0,193 | 15,57 % | 79 052,62 $ | +38,69 % | 60,42 |
| 12 mois | 2,5 % | 62 | 58,1 % | +0,193 | 13,12 % | 75 186,01 $ | +31,91 % | **49,82** |
| 2026 (ticks réels) | 3,0 % | 45 | 55,6 % | +0,174 | 15,57 % | 70 311,73 $ | +23,35 % | 51,60 |
| Q4 2025 | 3,0 % | 16 | 62,5 % | +0,169 | 5,91 % | 61 388,05 $ | +7,70 % | 43,02 |

Lecture : à **2,5 %**, BOTH atteint ~**49,8 $/jour** sur 12 mois avec un DD de
13,12 % ; à 3,0 %, ~60,4 $/jour mais 15,57 % de DD. L'objectif de rendement est
donc atteint en test direct, mais **pas sous la règle de drawdown 10 %**. À
1,8-1,9 %, le DD retombe vers 10 % mais le rendement vers 36-38 $/jour
(extrapolation linéaire, non testée). Le
Q4 2025 est en ticks générés (les ticks réels MT5 commencent au 2026-01-01) ;
la ligne 2026 est la plus fiable. Le 12 mois mélange les deux et surestime donc
légèrement la qualité d'exécution du Q4.

### Correctif clôture broker et test à 0,5 %

Le premier test BOTH à 0,5 % ne comptait que **59 trades** et finissait à
**61 003,47 $** : quatre positions du vendredi étaient encore ouvertes à
20:55 serveur, la clôture à 21:00 était refusée (`Market closed`, retcode
10018), et la position bloquait le trade du lundi suivant. Le même problème
touchait les vendredis 2025-12-19, 2026-01-16, 2026-02-06 et 2026-02-20.

Correctif EA : `InpCloseBufferMinutes=5` (clôture 15:55 NY du lundi au jeudi)
et `InpFridayCloseBufferMinutes=10` (clôture 15:50 NY le vendredi, avant la
fermeture broker de 20:55 serveur). Une position ouverte un jour précédent est
aussi fermée au premier tick du jour suivant avant toute nouvelle entrée.

Test corrigé à **0,5 %**, 12 mois : **60 457,04 $**, **+6,07 %**, **62 trades**,
58,1 % de gagnants, R moyen +0,193, max DD 2,74 %, soit **9,47 $/jour**. Le
résultat colle à la simulation linéaire (~60 468 $) et ne présente plus aucune
clôture refusée. Le run 2,5 % corrigé donne 75 186,01 $ et le run 3,0 %
79 052,62 $.

### OOS 2022-2025 et calibration bar-level

`tools/orb_both_oos.py` rejoue BOTH sur les M15 2016-11-15 → 2026-11-08, avec
uniquement le côté dont les filtres passent (pas de cassure ambiguë), target 3R,
coûts 1,7/3,4/5,1 points, et clôture 15:45 NY (`eod_bars_back=1`, proche de la
clôture réelle 15:55). Résultats bruts :

| Période | Risque | Coûts | Trades | Gagnants | R moyen | Max DD | Solde final | Rendement | $/jour |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| IS 2016-2021 | 0,5 % | 1,7 | 227 | 41,9 % | +0,103 | 7,95 % | 63 702,55 $ | +11,76 % | 3,58 |
| OOS 2022-2025 | 0,5 % | 1,7 | 194 | 46,9 % | +0,155 | **7,56 %** | 65 959,73 $ | +15,72 % | 6,59 |
| OOS 2022-2025 | 0,5 % | 5,1 | 194 | 45,4 % | +0,110 | 9,57 % | 63 147,04 $ | +10,78 % | 4,52 |
| 2026 | 0,5 % | 1,7 | 44 | 56,8 % | +0,262 | 2,92 % | 60 327,27 $ | +5,84 % | 12,90 |
| 12 mois | 0,5 % | 1,7 | 60 | 58,3 % | +0,274 | 2,92 % | 61 825,81 $ | +8,47 % | 13,41 |
| Full 2016-2026 | 0,5 % | 1,7 | 481 | 46,0 % | +0,145 | 7,95 % | 79 956,88 $ | +40,28 % | 6,39 |
| OOS 2022-2025 | 2,5 % | 1,7 | 194 | 46,9 % | +0,155 | **31,03 %** | 122 288,36 $ | +114,54 % | 48,04 |
| Full 2016-2026 | 2,5 % | 1,7 | 481 | 46,0 % | +0,145 | **34,62 %** | 249 676,69 $ | +338,03 % | 53,64 |

À 0,5 %, l'OOS 2022-2025 est positif avec **7,56 % de DD** ; à 5,1 points de
coût, il reste positif (+10,78 %, DD 9,57 %) mais l'IS 2016-2021 devient négatif
(−3,82 %, DD 14,33 %) : l'edge n'est pas stable avant 2022. À 0,75 %, l'OOS
monte à +24,07 % mais le DD à 11,21 %, déjà au-dessus de la règle. À 2,5 %,
l'OOS atteint ~48 $/jour mais avec **31,03 % de DD** ; le full monte à 34,62 %.
Il n'existe donc **aucun réglage de risque qui donne 50 $/jour sous 10 % de DD**
avec ce seul instrument et cet échantillon.

La simulation bar-level reste optimiste : sur 12 mois à 0,5 %, elle donne
+8,47 % contre **+6,07 %** en MT5, soit ~**0,08R/trade** d'écart (entrées/sorties
tick, spread bid/ask, cible short). En appliquant ce haircut, l'OOS 0,5 %
retombe vers +7-8 % et 2026 vers +4 %, toujours positif mais loin de 50 $/jour.
Le coût 5,1 points reste le scénario de stress à surveiller.

### Limite du warmup D1 dans le test 12 mois

Le terminal MT5 ne contient que **360 barres D1**, du 2025-09-21 au 2026-11-13.
Or `DailyTrend()` utilise EMA20/EMA50 D1 avec `shift(1)` : le test 12 mois
démarre donc avec une EMA non amorcée. Exemple : le 2025-12-02, le trend MT5
vaut −0,000138 (warmup) alors que le trend long-historique Python vaut +0,004969 ;
le trade BUY passe le filtre `InpTrendMax=0.002378` dans MT5 mais serait rejeté
en live. Les trois longs 2025-12-02, 2025-12-19 et 2026-02-05 sont dans les
62 trades MT5 mais absents du backtest long-historique ; leur somme vaut
−1,817R. C'est l'explication principale de l'écart 62 vs 60 trades. La fenêtre
**2026**, post-warmup, est la plus fiable ; le 12 mois ne valide pas proprement
le filtre D1. Pour un test propre, il faudrait précharger l'historique D1 avant
le 2025-09-21, ce que la limite de 14 mois ne permet pas ici.

Configs propres : `tester_ustecm_BE_30_clean.ini` (2026),
`tester_ustecm_BE_30_12m_clean.ini`, `tester_ustecm_trend_30_12m_clean.ini`,
`tester_ustecm_BE002_30.ini`, `tester_ustecm_BE002_12m.ini`,
`tester_ustecm_BE002_q4.ini`, `tester_ustecm_SHORT_12m.ini`,
`tester_ustecm_SHORT_2026.ini`, `tester_ustecm_BOTH_12m.ini`,
`tester_ustecm_BOTH_2026.ini`, `tester_ustecm_BOTH_q4.ini`,
`tester_ustecm_BOTH_12m_25.ini`, `tester_ustecm_BOTH_12m_05.ini`.
`tools/make_entry_tester_configs.py` régénère désormais `BE_25`, `BE_30`, `B_25`
et `BEG_25` avec `InpUsePrevWickFilter=false` et `InpDebugTrend=false`
explicites. Si vous éditez un `.ini` à la main, ajoutez toujours ces lignes
`false` : le tester MT5 hérite sinon des valeurs du test précédent. Les inputs
short absents d'un ancien `.ini` doivent aussi être ajoutés explicitement.

Recommandation révisée : lancer le forward démo avec **BOTH à 0,5 %**, seul
réglage compatible avec la règle de 10 % (OOS DD 7,56 %, ~6,6 $/jour OOS,
~9,5 $/jour sur 12 mois). Le **2,5 %** n'est pas un forward test conforme :
il donne ~48-50 $/jour sur 12 mois mais **31 % de DD OOS** ; le 3,0 % est
rejeté. Pour viser 50 $/jour sous 10 % de DD, il faut environ **8× plus de
capital** (~450-500 k$), plus d'instruments ou un edge plus fréquent — pas plus
de risque. Ne pas augmenter le risque pour compenser un petit compte démo.

## Mise en œuvre

1. Créditer/réinitialiser le compte démo à 57 000 USD (action broker/terminal,
   pas réalisable depuis le code du projet). Le compte actuel est à
   24 597,71 $ : à 0,5 % il validera l'exécution et le risque, pas la cible
   50 $/jour.
2. Utiliser l'EA ORB BOTH avec les règles ci-dessus, risque **0,5 %** (DD OOS
   7,56 %, ~6,6 $/jour OOS) pour un test conforme ; 2,5 % uniquement si l'on
   accepte explicitement 31 % de DD OOS. Stop/target serveur, clôture 15:55 NY
   (15:50 vendredi).
3. Valider la conversion NY → serveur (UTC) et les spreads réels à 09:30.
4. Démo forward 60 jours minimum. Arrêt si drawdown > 10 % ou si le résultat
   reste négatif sur 30 jours.
5. Aucun passage en réel sans holdout positif, coûts réels et autorisation
   explicite.

## Preuves

- `data_live/nas100_m15_kaggle_utc.parquet`
- `data_live/us30_m15_kaggle_utc.parquet`
- `out_nas100_orb_9y_targets/trades_r1_t3.0.csv`
- `out_us30_orb_9y/trades_r1_t3.0.csv`
- `out_nas100_orb_mt5_targets/`
- `out_us30_orb_recent/`
- `out_us500_orb_recent/`
- `out_orb_entry_features/nas100_entry_features.csv`
- `out_orb_entry_scan/quintiles.csv`, `individual_rules.csv`, `pair_rules.csv`,
  `rule_eval.csv`, `combos_1000.csv`, `short_rules.csv`
- `tools/orb_1000_combos.py`, `tools/orb_short_eval.py`
- `out_orb_both_oos/summary.csv`, `out_orb_both_oos/metadata.json`,
  `out_orb_both_oos_risk/summary.csv`
- `tools/orb_both_oos.py` (OOS BOTH 2016-2026, bar-level)
- `out_orb_portfolio_57k/tester_ustecm_SHORT_12m.ini`,
  `tester_ustecm_BOTH_12m.ini`, `tester_ustecm_BOTH_2026.ini`,
  `tester_ustecm_BOTH_q4.ini`, `tester_ustecm_BOTH_12m_25.ini`
- `tools/launch_demo_both.py` (démo BOTH, `--risk` défaut 0,5 %)
