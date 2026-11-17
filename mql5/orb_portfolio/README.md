# ORB Portfolio — test MT5 Exness

Statut : **recherche / démo uniquement**. Aucun ordre réel. Le code compile
0 erreur / 0 warning (MetaEditor 5.0.0.6230).

## Fichiers

- `ORB_Portfolio.mq5` : EA source.
- `ORB_Portfolio.ex5` : binaire compilé.
- Copie déjà installée dans le terminal réellement utilisé (`473001893`) :
  `%APPDATA%\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\ORB_Portfolio.mq5`
  et `.ex5` (aussi dans le sous-dossier `ORB_Portfolio\`).
  Si le chemin diffère : terminal → `Fichier` → `Ouvrir le dossier de données`. 

## 1. Strategy Tester

1. Ouvrir le terminal **Exness MT5**, se connecter au compte **démo**.
2. Vérifier l'heure serveur : Market Watch → clic droit → Spécification, ou
   comparer l'horloge du terminal avec UTC. Chez Exness le serveur est
   généralement UTC ; sinon noter l'écart.
3. Activer **Algo Trading**.
4. `Ctrl+R` pour ouvrir le Strategy Tester.
5. Choisir :
   - Expert : `ORB_Portfolio`
   - Symbole : `USTECm` ou `US30m`
   - Période : `M15`
   - Dates disponibles : 2025-09-21 → 2026-11-08 (seule profondeur MT5)
   - Modèle : **Every tick based on real ticks** si disponible, sinon
     **1 minute OHLC**
   - Dépôt : **57 000 USD**
   - Levier : celui du compte démo
6. Paramètres :
   - `InpRiskPct = 0.5` pour un test conforme au DD ; `2.5`/`3.0` en mode
     agressif (DD OOS > 30 %, non conforme à la règle 10 %)
   - `InpTargetR = 3.0`
   - `InpServerGMTOffsetHours = 0` (mettre 2 ou 3 si le serveur n'est pas UTC)
   - `InpCloseBufferMinutes = 5` et `InpFridayCloseBufferMinutes = 10` :
     clôture de sécurité à **15:55 NY** (15:50 le vendredi), car le broker
     ferme à 16:00 NY. Ne pas remettre ces buffers à 0 en démo.
   - `InpMaxSpreadPoints = 500` (ou 0 pour désactiver)
   - `InpOneTradePerDay = true`
7. Filtres long + short validés en test direct (USTECm, 12 mois et 2026) :
   - `InpLongOnly = false`, `InpShortOnly = false` pour la version BOTH
     (un seul trade par jour, premier côté cassé).
   - Long : `InpUseTrendFilter = true`, `InpTrendMax = 0.002378`,
     `InpUseOrCloseFilter = true`, `InpOrCloseMin = 0.8044`,
     `InpUseMomFilter = true`, `InpMomMin = 0.00123`.
   - Short : `InpUseShortOrFilter = true`, `InpShortOrCloseMax = 0.1956`,
     `InpUseShortMomFilter = true`, `InpShortMomMax = -0.00123`,
     `InpUseShortTrendFilter = true`, `InpShortTrendMin = -0.00425`.
   - `InpUsePrevCloseFilter = false` (variante `true` moins rentable en direct)
   - `InpUsePrevWickFilter = false` (variante E+F rejetée en test direct)
   - `InpUseRsiFilter = false`
   - `InpUseRangeRankFilter = false`
   - `InpRiskPct = 0.5` pour un forward conforme à la règle de 10 % (OOS
     2022-2025 : DD 7,56 %, ~6,6 $/jour). `2.5` donne ~49,8 $/jour sur 12 mois
     mais **31 % de DD OOS** ; `3.0` est rejeté. La règle d'arrêt à 10 % reste
     une alerte, pas une garantie.
   - Configs propres : `tester_ustecm_BE_30_clean.ini` (2026),
     `tester_ustecm_BE_30_12m_clean.ini`,
     `tester_ustecm_trend_30_12m_clean.ini`, `tester_ustecm_BE002_30.ini`,
     `tester_ustecm_BE002_12m.ini`, `tester_ustecm_BE002_q4.ini`,
     `tester_ustecm_SHORT_12m.ini`, `tester_ustecm_SHORT_2026.ini`,
     `tester_ustecm_BOTH_12m.ini`, `tester_ustecm_BOTH_2026.ini`,
     `tester_ustecm_BOTH_q4.ini`, `tester_ustecm_BOTH_12m_25.ini`,
     `tester_ustecm_BOTH_12m_05.ini`.
   - **Important** : le tester MT5 hérite des inputs absents du `.ini`. Écrire
     explicitement `InpUseOrCloseFilter=false`, `InpUseMomFilter=false`,
     `InpUsePrevCloseFilter=false`, `InpUsePrevWickFilter=false`,
     `InpShortOnly=false`, tous les `InpUseShort*`, `InpDebugTrend=false`
     avant de relancer une variante.
8. Lancer le test. Refaire le même test sur l'autre symbole : chaque EA est
   indépendant, il faut additionner les deux courbes pour le portefeuille.

Attention : le Strategy Tester ne contient que **14 mois**. Il ne reproduit pas
le backtest 2016-2025 ; il sert à vérifier l'exécution, les stops, les lots et
le fuseau, pas à confirmer l'edge.

## 2. Démo forward

1. Créditer/réinitialiser le compte démo à **57 000 USD** (opération
   broker/terminal, impossible depuis le code du projet). Le compte démo actuel
   est à **24 597,71 $** : même à 2,5 % de risque il ne produira pas 50 $/jour,
   il servira seulement à valider l'exécution. Lancer
   `tools/launch_demo_both.py --risk 0.5` pour un test conforme au drawdown.
2. Ouvrir un graphique `USTECm` M15 (US30m/US500m ont été rejetés).
3. Glisser `ORB_Portfolio` sur le graphique, autoriser Algo Trading, charger
   `BOTH.set` (`tools/launch_demo_both.py`).
4. Vérifier le journal : `ORB range high=... low=...`, `ORB entry ...`,
   `40 inputs read`.
5. Laisser tourner **60 jours**. Arrêter si drawdown > 10 % ou si le résultat
   est négatif sur 30 jours ; noter que le DD historique de BOTH dépasse 10 %.
6. Noter chaque jour : trades, PnL, drawdown, spread à 09:30 NY.

## 3. Dashboard

Le dashboard est affiché en haut à gauche du graphique `USTECm` M15, sur fond
sombre. Il est mis à jour chaque seconde et à chaque tick.

Il affiche : mode du compte (DEMO/REAL), Algo Trading, solde, equity, P&L
flottant, marge libre, niveau de marge, P&L bot du jour, nombre de trades,
drawdown du jour, drawdown max de session, position ouverte (sens, volume,
entrée, SL, TP, P&L et R), range d'ouverture, OR close, tendance, momentum,
filtres LONG/SHORT, spread, heure serveur, heure New York et statut
(`WAITING FOR RANGE`, `ARMED - LONG`, `IN POSITION`, `CLOSED FOR TODAY`, etc.).

Inputs : `InpShowDashboard` (actif par défaut), `InpDashX`, `InpDashY`,
`InpDashFontSize`, `InpDashBg`, `InpDashText`, `InpDashAccent`, `InpDashGood`,
`InpDashBad`, `InpDashWarn`. Mettre `InpShowDashboard=false` pour le masquer.
Le dashboard est désactivé automatiquement en Strategy Tester non visuel.

## 4. Test manuel (sans EA)

Heure de New York : **09:30-09:45** pour l'opening range. Serveur UTC :
14:30-14:45 en hiver, 13:30-13:45 en été.

1. À 09:45 NY, relever le high et le low de la barre M15 09:30-09:45.
2. Placer un **buy stop** au high et un **sell stop** au low.
3. SL long = low ; SL short = high ; TP = entrée ± 3 × (high - low).
4. Risque 0,5 % de 57 000 = **285 $**.
   - USTECm : `lots = 285 / distance_stop_en_points_indice`
   - US30m : `lots = 285 / distance_stop_en_points_indice`
   - arrondir au pas de volume, respecter le lot minimum.
5. Quand un ordre se déclenche, annuler l'autre (OCO).
6. À **15:55 NY** (15:50 le vendredi), fermer et annuler le reste. Le broker
   ferme à 16:00 NY : une clôture à 16:00 peut être refusée. Un seul trade par
   instrument et par jour.

## 5. Limites

- L'edge ORB **non filtré** est absent des 14 derniers mois (NAS100 −3,02 $/jour).
- Le filtre tendance seul donne +16,38 % sur 2026-01-01 → 2026-09-15 à 2,5 %
  (max DD 19,8 %, 79 trades). Le filtre d'entrée `or_close_pos > 0,8044` +
  `prev_mom6 > 0,00123` donne +16,65 % à 3,0 % avec 31 trades et un max DD de
  9,65 %. Ce sont des résultats de recherche, pas des garanties.
- Sur **12 mois** (2025-09-21 → 2026-09-15), BE long-only 3,0 % avec
  `InpTrendMax=0.00425` ne rend que **+3,87 %** (36 trades, DD 10,97 %) contre
  +4,67 % pour la tendance seule (95 trades, DD 23,15 %). Avec
  `InpTrendMax=0.002378`, BE long-only rend **+11,58 %** (25 trades, 60 % de
  gagnants, DD 9,65 %) ; l'objectif ~50 $/jour n'est pas atteint (~18 $/jour).
- En ajoutant le short miroir (BOTH, un trade/jour) : **+31,91 % à 2,5 %**
  (62 trades, 58,1 % de gagnants, DD 13,12 %, **~49,8 $/jour**) et **+38,69 % à
  3,0 %** (DD 15,57 %, ~60,4 $/jour) sur 12 mois. Le Q4 2025 est en ticks
  générés (les ticks réels MT5 commencent au 2026-01-01) ; la fenêtre 2026 en
  ticks réels donne +23,35 % à 3,0 % (45 trades, DD 15,57 %, ~51,6 $/jour).
  L'objectif de rendement est atteint, mais **au-dessus de la règle de DD 10 %**.
- Le test BOTH à **0,5 %** corrigé donne **60 457,04 $** (+6,07 %, 62 trades,
  58,1 %, DD 2,74 %, ~9,47 $/jour), sans clôture refusée. L'ancien résultat
  (59 trades, 61 003,47 $) était faussé par des positions du vendredi bloquées
  au-delà de la fermeture broker.
- OOS **2022-2025** (`tools/orb_both_oos.py`, bar-level, clôture 15:45) à
  0,5 % : **194 trades, R moyen +0,155, +15,72 %, DD 7,56 %**, soit ~6,6 $/jour.
  À 5,1 points de coût : +10,78 %, DD 9,57 %. À 2,5 % : +114,54 % mais
  **DD 31,03 %** (~48 $/jour). Aucun réglage ne donne 50 $/jour sous 10 % de
  DD ; il faudrait ~8× plus de capital ou plus d'instruments.
- La simulation OOS surestime le 12 mois d'environ **0,08R/trade** : +8,47 %
  simulé contre +6,07 % en MT5 à 0,5 %. Après haircut, l'OOS 0,5 % reste
  positif (~+7-8 %) mais loin de 50 $/jour. L'IS 2016-2021 à 5,1 points est
  négatif (−3,82 %, DD 14,33 %) : l'edge n'est pas stable avant 2022.
- **Warmup D1** : le terminal n'a que 360 barres D1 depuis 2025-09-21. Le test
  12 mois démarre avec EMA20/50 non amorcées ; le 2025-12-02, le trend MT5 vaut
  −0,000138 contre +0,004969 en long historique, ce qui explique 62 trades MT5
  contre 60 en Python (3 longs de warmup, −1,817R). La fenêtre 2026 est la plus
  fiable ; le 12 mois ne valide pas proprement le filtre D1.
- Le filtre E+F (`prev_mom6` + `prev_upper_wick`) est rejeté en direct 2026 :
  −6,47 %, 67 trades, DD 21,50 % ; les heures d'entrée réelles diffèrent du
  backtest Python. Le filtre `prev_upper_wick < 0,2068` + `trend < 0,002378`
  est aussi rejeté (+7,35 %, 55 trades, DD 24,67 %).
- `tools/orb_1000_combos.py` a criblé 1 000 combinaisons de filtres ; les tops
  Python sont largement sur-ajustés. Seule la combinaison BE002 a été confirmée
  en direct sur 12 mois.
- À 2,5 % de risque, le drawdown OOS 2022-2025 de BOTH est **31,03 %** ; la
  règle d'arrêt à 10 % couperait la stratégie bien avant. Le réglage conforme
  est 0,5 %, avec un rendement OOS modeste (~6,6 $/jour sur 57 k$).
- Les coûts, le spread d'ouverture et le slippage peuvent annuler l'edge.
- Ne pas utiliser de martingale, ne pas élargir un stop, ne pas trader le
  compte réel.
