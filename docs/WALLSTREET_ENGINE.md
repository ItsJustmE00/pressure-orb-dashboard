# Wall Street Engine — moteur d'analyse institutionnel ORB

> Objectif : analyser le marché comme un desk institutionnel — chaque setup,
> chaque bougie, chaque tick — plutôt que chercher un filtre magique.
> Outils : `tools/wallstreet_engine.py`, `tools/ws_morning_note.py`,
> `tools/ws_delta_confirm_test.py`, `mql5/orb_portfolio/DOM_Recorder.mq5`.

## Architecture en 4 couches

```
COUCHE 1 : CONTEXTE MARCHE (09:25 NY, avant ouverture)
  regime de tendance     EMA20 vs EMA50 (daily)
  regime de volatilite   ATR20 + percentile 1 an
  veille                 inside day / jour de tendance
  overnight              range nocturne (ATR), gap d'ouverture (ATR)

COUCHE 2 : MICROSTRUCTURE (09:45 NY)
  delta bougie d'ouverture  vol * (close-open)/(high-low)  -> acheteurs vs vendeurs
  volume relatif            volume 09:30 vs mediane des 20 dernieres ouvertures
  largeur du range          OR range en unités ATR

COUCHE 3 : SCORING DE SETUP (anti-overfitting)
  2 500 setups candidats (tous les breakouts OR 2016-2026, sans filtre)
  score = somme(rho_IS * z(facteur)) ajuste du sens du trade
  facteurs valides : atr_pct, or_atr, stop_atr, delta0, vol_rel
  validation : IS 2016-2021 (fit) -> OOS 2022-2026 (verdict)

COUCHE 4 : NOTE DU MATIN (`ws_morning_note.py --date YYYY-MM-DD` ou --last)
  briefing 3 temps 09:25 / 09:45 / verdict, aucun lookahead,
  section REVIEW a remplir apres session (journal de trading).
```

## Resultats honnetes (la partie la plus importante)

### 1. Ce qui NE marche PAS (prouve OOS, pas d'opinion)

| Piste testee | Verdict OOS | Lecon |
|---|---|---|
| Score multi-facteurs (5 facteurs honnetes) | quintiles NON monotones OOS, gate >= 40 : avgR -0.008 vs -0.008 sans gate | le score IS ne generalise pas |
| Gate score >= 40 sur le live | avgR 0.221 vs 0.260 sans gate | degrade le systeme live |
| Entree confirmee a la cloture de la bougie de breakout | +14.5% vs +22.3% baseline | l'entree tardive coute plus que le filtre n'apporte |
| delta de la bougie de BREAKOUT comme filtre | BIAISE (lookahead) : le delta n'est connu qu'a la cloture | piège detecte et corrige |
| Filtre OR-rank (sweep precedent) | tue l'edge (+0.75% vs +22.34%) | l'edge vient des ranges normaux/larges |
| delta bougie 09:30 (or_dir), bougie precedente (prev_dir) | ~baseline (22.1-23.0%, DD 4.4-4.9%) | pas de gain materiel |

### 2. Le piége du lookahead (a retenir)
Deux fois ce jour, un filtre "microstructure" a semble doubler la performance
(+35% OOS, avgR 0.515). Dans les deux cas l'info (delta de la bougie) n'etait
connue qu'a sa cloture alors que l'entree simulée se faisait a l'ouverture.
**Regle du moteur : un facteur n'est valide que s'il est connu AVANT l'entree.**

### 3. Ce qui reste vrai
- Baseline **2R / max 2 / risque 0.5% / hold EOD** : +22.3% OOS, DD 5.4%, t-stat 3.15.
- A la resolution M15 (OHLC + tick_volume), aucune couche supplementaire
  honnete n'ameliore le systeme. Les proxies microstructure manquent de
  resolution : il faut le vrai flux d'ordres.

### 4. La suite logique : donnees REELLES de ticks
`DOM_Recorder.mq5` (installe, a attacher lundi sur USTECr M1) enregistre :
`time, bid, ask, bid_vol, ask_vol` -> `MQL5/Files/dom_records.csv`.
Apres 1-2 semaines de capture, le moteur passera aux vrais calculs :
- delta reel par tick (acheteur actif vs vendeur actif), pas un proxy OHLC
- imbalance du carnet d'ordres aux niveaux du range OR
- absorption reelle : gros volume qui ne fait pas bouger le prix
- footprint par bougie M15 (delta par niveau de prix)

## Note du matin — exemple reel (09/04/2025, pause des tarifs)

```
09:25  regime BAISSIER (-4.49%) | volatilite haute (ATR 676 pts, p100)
       veille haussiere | overnight 687 pts (1.0 ATR) | gap -0.02 ATR
09:45  OR 347 pts (0.51 ATR) | delta +0.43 ACHETEURS | volume x1.02
verdict NO-TRADE (trend filtre encore baissier)
→ la plus grosse bougie de l'histoire (+2093 pts) a ete manquee :
  le filtre trend EMA20/50 est en retard sur les retournements violents.
```

## Fichiers de sortie (`out_wallstreet/`)

| Fichier | Contenu |
|---|---|
| `setups_scored.csv` | 2 500 setups + features + score + R realise |
| `factors.csv` | rho Spearman IS par facteur, retenu oui/non |
| `score_quintiles_oos.csv` | validation OOS du score |
| `baseline_with_score.csv` | trades live 2R max2 + score |
| `trades_live_*.csv` | baseline vs variantes de confirmation |
| `delta_confirm_result.csv` | test live honest (baseline gagne) |
