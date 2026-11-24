# Revue des trades ORB Pressure

Mise à jour : 19/11/2026, 11:20 NY.
Périmètre : les trois trades pris depuis la remise en service du bot, compte démo
`Trial16 / 473001893`, magic `20261117`, `USTECm M15`.

## 1. Méthode

Sources utilisées :

- `MQL5/Logs/2026MMDD.log` : range, pression, signaux, entrées, closes de sécurité.
- `logs/2026MMDD.log` du terminal : deals et prix d'exécution réels.
- API live `http://127.0.0.1:8050/api/live` : position ouverte, P/L, phase.
- Simulateur `tools/orb_pressure_late_entry_sim.py` : rejeu M15 de la stratégie.
- Test statistique `tools/orb_pressure_cutoff_test.py` : bootstrap par session.

Conventions :

- `extension` = distance entre le prix d'entrée et la bordure du range, divisée
  par la largeur du range. `0` = cassure nette ; `1` = entrée une largeur de
  range au-delà de la bordure.
- `stop_ratio` = distance au stop / largeur du range. `1` = stop à la bordure
  opposée ; `2` = stop à deux largeurs.
- `R` = P/L net / risque en dollars. Le risque cible est 0,5 % de l'equity.
- Les prix sont ceux du broker ; les heures sont NY.

## 2. Tableau de synthèse

| # | Date NY | Sens | Entrée NY | Range | Entrée | Extension | Stop | Risque | Volume | Pression | Sortie | P/L | R |
|---|---------|------|-----------|-------|---------|-----------|------|--------|--------|----------|--------|-----|---|
| 1 | 17/11 | SELL | 20:51 | 27149,40–27297,39 | 27146,16 | 3,24 pts (0,022×) | 151,23 pts (1,022×) | 124,01 $ (0,504 %) | 0,82 | 0,7161 | 27170,27 à 22:55 | −19,77 $ | −0,159 |
| 2 | 18/11 | BUY | 18:30 | 26955,63–27267,89 | 27364,01 | 96,12 pts (0,308×) | 408,38 pts (1,308×) | 122,51 $ (0,498 %) | 0,30 | 0,6773 | 27434,38 à 22:55 | +21,11 $ | +0,172 |
| 3 | 19/11 | SELL | 10:30 | 27581,65–27782,63 | 27295,39 | 286,26 pts (1,424×) | 487,24 pts (2,424×) | 121,81 $ (0,495 %) | 0,25 | 0,8012 | ouvert | +25,47 $ à 11:18 | +0,209 latent |

Chaîne d'equity vérifiée : 24 597,71 $ avant le trade 1, −19,77 $ → 24 577,94 $
avant le trade 2, +21,11 $ → 24 599,05 $ avant le trade 3. Les trois risques
sont dans la tolérance de 0,5 %.

## 3. Exécution : aucun défaut constaté

| Contrôle | Trade 1 | Trade 2 | Trade 3 |
|----------|---------|---------|---------|
| Ordre accepté | oui | oui | oui |
| Latence de fill | 982 ms | 1 626 ms | 1 214 ms |
| Slippage vs prix signal | −2,00 pts (favorable) | 0,00 | 0,00 |
| Spread | ~1,1 pt | ~1,1 pt | 1,12 pt |
| Plafond spread (500 pts) | respecté | respecté | respecté |
| Volume / risque | 0,82 / 0,504 % | 0,30 / 0,498 % | 0,25 / 0,495 % |
| SL et TP présents | oui | oui | oui |
| Une seule position | oui | oui | oui |
| Clôture de sécurité 22:55 | oui | oui | en attente |
| Rejet / doublon / erreur | aucun | aucun | aucun |

Conclusion : les trois trades sont **conformes aux règles du bot**. Il n'y a pas
de faute d'exécution à corriger (taille, spread, stop, heure de clôture, doublon).

## 4. Ce que les trades révèlent

### 4.1 Les deux trades tardifs viennent de redémarrages de l'EA

- Le 17/11, l'EA a été chargé à **16:18 NY** (log `range restored`), après le
  début de session. Il a repris le range du matin et pris le premier signal
  disponible à **20:51 NY**, soit 2 h 04 avant la clôture de sécurité.
- Le 18/11, après l'incident terminal, l'EA a été rechargé à **18:11 NY** et a
  pris le premier signal à **18:30 NY**, soit 4 h 25 avant la clôture.

Ces deux trades sont donc des **entrées de fin de session consécutives à un
redémarrage**, pas le comportement normal du matin. Ils respectent les règles,
mais ils ont très peu de temps pour atteindre une cible à 2R. Le taux de
réalisation de la cible chute de 20,4 % (entrées 09:45–11:00) à 4,1 % après
19:00. Les deux sorts se font logiquement à la clôture de sécurité.

Sur ces deux trades précis, un coupe-circuit à 15:00 aurait évité −19,77 $ et
+21,11 $, soit +1,34 $ net : c'est du bruit. La décision ne doit pas se prendre
sur ces deux observations, mais sur l'ensemble de l'échantillon.

### 4.2 Le trade du 19/11 est une entrée tardive conforme

La bougie 10:15 a cassé le bas du range alors que la pression n'était que de
**0,5737** (< 0,60) : le bot a refusé. À l'ouverture 10:30, la pression est
passée à **0,8012** (3 bougies baissières) et le prix était déjà **286 points
sous le range** : le bot est entré au marché, comme prévu par la règle.

C'est donc une entrée tardive **conforme**, avec un stop à 2,42× la largeur du
range. Le risque en dollars reste plafonné à 0,5 %, mais la cible à 2R est très
éloignée. Le trade est actuellement en profit latent ; il reste à surveiller
jusqu'à 22:55.

### 4.3 Le filtre de distance n'est pas robuste

Le simulateur M15 (2016–2026, coût 1,7 pt, cible 2R, clôture 22:55) donne :

| Variante | Trades | R moyen | R total | DD max à 0,5 % |
|----------|-------:|--------:|--------:|---------------:|
| Baseline | 4 993 | 0,0275 | 137,3 | 19,3 % |
| Extension ≤ 0,25 | 3 057 | 0,0343 | 104,8 | 19,6 % |
| Extension ≤ 0,50 | 3 581 | 0,0369 | 132,1 | 20,6 % |
| **Coupe-circuit 15:00 NY** | **4 052** | **0,0509** | **206,2** | **15,0 %** |

Le filtre d'extension améliore le R moyen mais **dégrade l'OOS** (0,0193 pour
0,25× et 0,0211 pour 0,50×, contre 0,0204 en baseline) et les buckets ne sont pas
monotones : la tranche 0,5–1,0× est négative, les tranches > 1,0× redeviennent
positives. Ce n'est pas une règle robuste : **ne pas l'ajouter**.

### 4.4 Le coupe-circuit 15:00 NY est robuste

Le même simulateur, avec interdiction de toute nouvelle entrée après 15:00 NY
mais clôture de sécurité maintenue à 22:55 :

| Période | Baseline R moyen | Cut15 R moyen | Baseline R total | Cut15 R total | Baseline DD | Cut15 DD |
|---------|-----------------:|--------------:|-----------------:|--------------:|------------:|---------:|
| IS (2016–2021) | 0,0288 | 0,0583 | 73,8 | 118,4 | 18,1 % | 14,2 % |
| OOS (2022–09/2025) | 0,0204 | 0,0374 | 38,8 | 59,8 | 19,3 % | 15,0 % |
| Récent (09/2025–11/2026) | 0,0467 | 0,0663 | 24,8 | 28,0 | 14,8 % | 12,4 % |
| **Total** | **0,0275** | **0,0509** | **137,3** | **206,2** | **19,3 %** | **15,0 %** |

Bootstrap apparié par session NY (5 000 tirages) : **+68,6 R total, IC 95 %
[+27,6 ; +109,9], p < 0,001** ; **+0,0234 R moyen, IC 95 % [+0,0131 ; +0,0336]**.
Le résultat est positif sur les trois périodes et ne dépend pas de quelques
journées extrêmes.

Le plafond à 2 trades/jour combiné au cut15 est moins bon (+178,1 R, DD 18,7 %)
et son IC total inclut zéro : **ne pas l'ajouter**.

Le biais BUY/SELL n'est pas stable : les SELL sont négatifs en IS/OOS mais
positifs en récent. C'est un effet de régime, pas une règle robuste : **ne pas
filtrer par sens**.

## 5. Décision proposée

1. **Adopter le coupe-circuit 15:00 NY** : plus aucune nouvelle entrée après
   15:00, la clôture de sécurité à 22:55 reste inchangée. C'est la seule
   modification soutenue par un test robuste.
2. **Ne pas ajouter** le filtre d'extension, le plafond max 2, ni un filtre
   BUY/SELL.
3. **Appliquer la modification après la clôture du trade ouvert** et après
   accord explicite : ajout de `InpLastEntryHourNY=15` et
   `InpLastEntryMinuteNY=0`, recompilation 0 erreur / 0 warning, rechargement
   avec le preset, vérification du range et de la pression.
4. **Éviter les redémarrages inutiles de l'EA en session** ; le coupe-circuit
   neutralise le risque résiduel d'un rechargement tardif.
5. **Revue récurrente** : après chaque session, vérifier entrée, range,
   pression, spread, taille, extension, stop, R, sortie et P/L. Un trade perdant
   conforme n'est pas une faute ; une entrée hors règle ou un défaut de taille
   en est une.

> **Statut au 24/11** : le coupe-circuit 15:00 NY n'a pas été appliqué, faute
> d'accord. L'EA et le preset restent inchangés.

## 6. Ce que « sans faute » signifie

- Zéro faute d'exécution est un objectif atteignable et vérifiable : prix,
  taille, spread, stop, heure, doublon, clôture.
- Zéro trade perdant n'est pas un objectif mathématiquement garanti : une perte
  peut être parfaitement conforme.
- La priorité est de supprimer les classes de trades structurellement faibles
  (entrées de fin de session) et de ne changer une règle qu'après un test
  historique robuste, pas après un ou deux trades.

## 7. Reproduction

```powershell
C:\Python314\python.exe tools\orb_pressure_late_entry_sim.py
C:\Python314\python.exe tools\orb_pressure_cutoff_test.py
```

Sorties : `out_orb_pressure_review/report.md`,
`out_orb_pressure_review/summary.csv`,
`out_orb_pressure_review/rank_breakdown.csv`,
`out_orb_pressure_review/time_slots.csv`,
`out_orb_pressure_review/cutoff_test.md`.

## 8. Journal

| Date | Trade | Statut | Conclusion |
|------|-------|--------|------------|
| 17/11 | SELL 0,82 | clôturé −19,77 $ | conforme, entrée tardive après rechargement |
| 18/11 | BUY 0,30 | clôturé +21,11 $ | conforme, entrée tardive après rechargement |
| 19/11 | SELL 0,25 | clôturé +243,49 $ (TP 2R) | conforme, entrée tardive à 1,42× le range, TP atteint |

Le trade 3 a été clôturé au TP (2R). Le terminal était arrêté au moment de la
clôture ; le P/L est reconstruit depuis le solde : 24 599,05 $ avant l'entrée,
24 842,54 $ au redémarrage du 24/11, soit **+243,49 $** pour un risque de
121,81 $ (**R ≈ +2,00**). Aucun autre trade n'a été pris entre-temps.

## 9. Notification Telegram automatique

Chaque nouvelle entrée du bot est notifiée sur Telegram par
`tools/telegram_trade_notifier.py`, un processus en lecture seule :

- il interroge `http://127.0.0.1:8050/api/live` toutes les 5 s (cache 2 s) ;
- il reconstruit pression, spread, risque et signaux refusés depuis le log MQL5 ;
- il n'ouvre jamais MT5 et ne touche ni à l'EA ni aux positions ;
- l'état est conservé dans `logs/telegram_notifier_state.json` (id de position),
  ce qui évite les doublons ;
- les identifiants sont lus dans `tools/telegram.env` (ignoré par Git).

Tâche planifiée `ORB Telegram Notifier` : déclenchement au logon, redémarrage
automatique toutes les minutes en cas d'échec, instance unique.

Test manuel :

```powershell
C:\Python314\python.exe tools\telegram_trade_notifier.py --once --dry-run --send-existing
```
