# Dashboard ORB Control

Dashboard web local connecté au terminal MT5, aux résultats du bot et aux
logs. Il est **lecture seule** : aucun ordre n'est envoyé, aucun paramètre n'est
modifié depuis le site.

## Stack

- Python 3.14
- Flask (serveur + API JSON)
- MetaTrader5 (lecture du compte et du terminal)
- psutil (détection du terminal `terminal64.exe`)
- mistune (rendu du rapport Markdown)
- CSS + SVG natif, sans dépendance front-end externe

## Fichiers

```
web/
├── app.py                routes Flask et API
├── mt5_service.py        connexion MT5, état live, logs, preset
├── results_service.py    parsing des CSV/JSON de résultats
├── templates/index.html  dashboard
├── templates/report.html rendu du rapport complet
├── static/app.js         UI, charts SVG, polling
├── static/style.css      thème
└── data/direct_runs.json résultats MT5 consolidés
```

## Lancement

```powershell
C:\Python314\python.exe web\app.py --port 8050
```

ou à la racine du projet :

```powershell
.\start_web.ps1 -Open
```

Le serveur écoute sur `http://127.0.0.1:8050`.

## API

| Route | Usage |
|---|---|
| `GET /api/health` | état du serveur, terminal MT5 et connexion |
| `GET /api/live` | compte, tick, positions, ordres, deals, logs, preset |
| `GET /api/results` | tests MT5, OOS, frontière de risque, courbes, calibration |
| `GET /api/config` | inputs actifs de `BOTH.set` |
| `GET /api/report` | rapport complet au format HTML |
| `GET /report` | page rapport |

## Sources de données

- `out_orb_portfolio_57k/report.md` : rapport, tests direct MT5.
- `out_orb_portfolio_57k/summary.json` : résumé des runs tester.
- `out_orb_portfolio_57k/trades_BOTH_12m_25.csv` : courbe 12 mois 2,5 %.
- `out_orb_both_oos/summary.csv` et `out_orb_both_oos/trades_r0.005_c1.7_e1.csv` :
  OOS 2022-2025 et courbe 0,5 %.
- `out_orb_both_oos_risk/summary.csv` : frontière de risque.
- `MQL5/Logs/*.log` et `Logs/*.log` du terminal MT5 : journal live.
- `MQL5/Presets/BOTH.set` : configuration EA chargée.

## Sécurité

- Le serveur ne se lie qu'à `127.0.0.1`.
- Aucun endpoint d'écriture ou de placement d'ordre.
- Le token Telegram dans `tools/telegram.env` n'est jamais lu par le dashboard.
- Les logs MT5 peuvent contenir des informations de compte : le site reste
  local et privé.
