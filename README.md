# ORB NAS100 / USTECm — bot, recherche et dashboard

Projet de trading algorithmique **Opening Range Breakout (ORB)** sur `USTECm`
(NAS100). Le bot tourne en **compte démo Exness**, en **forward test BOTH à
0,5 % de risque par trade**, sans aucun ordre réel.

Le dépôt contient :

- l'EA MT5 `ORB_Portfolio` (source et binaire compilé) ;
- l'EA MT5 `ORB_Pressure` (variante avec filtre de pression des bougies) ;
- les outils de recherche, de calibration et de lancement du forward ;
- les résultats des tests direct MT5 et de la simulation OOS 2016-2026 ;
- un **dashboard web local** connecté à MT5 pour suivre le bot, les analyses,
  les résultats et les logs ;
- un **dashboard Vercel** déployé pour accès distant.

## Arborescence

```
.
├── mql5/orb_portfolio/          EA MT5 ORB_Portfolio (source + .ex5)
│   └── ORB_Pressure.mq5        EA MT5 ORB_Pressure (avec filtre pression)
├── tools/                       outils ORB (lancement démo, OOS, configs, parsing)
├── out_orb_portfolio_57k/       tests direct MT5, rapport et configs .ini
├── out_orb_both_oos/            simulation OOS 2022-2025 et full 2016-2026
├── out_orb_both_oos_risk/       frontière de risque OOS
├── out_orb_entry_features/      features ORB (or_close_pos, prev_mom6, etc.)
├── out_orb_entry_scan/          scans de filtres et 1 000 combinaisons
├── data_live/                   parquets M15 NAS100 et US30
├── web/                         dashboard Flask connecté à MT5
├── dashboard/                   Frontend Vercel (index.html, app.js, style.css)
└── docs/                        manifeste de nettoyage et notes
```

## Règle de base

- Range : 09:30 → 09:45 New York.
- Entrée : cassure du high (long) ou du low (short).
- Stop : côté opposé du range.
- Target : 3R.
- Clôture de sécurité : 15:55 NY (15:50 le vendredi).
- Maximum 1 trade par jour et par instrument.
- Risque forward : **0,5 %**.

## Dashboard web

Le site est un serveur Flask local, **lecture seule**. Il n'exécute aucun ordre
et ne touche pas au compte.

Lancer :

```powershell
# terminal MT5 demo
C:\Python314\python.exe tools\launch_demo_both.py --risk 0.5

# dashboard
.\start_web.ps1 -Open
# ou
.\start_web.bat
```

ou directement :

```powershell
C:\Python314\python.exe web\app.py --port 8050
```

Puis ouvrir `http://127.0.0.1:8050`.

Le dashboard affiche :

- équity, solde, P&L du jour, P&L flottant, marge libre ;
- positions, ordres en attente et deals du jour ;
- fenêtre de trading (09:30 NY, range, filtres, clôture) ;
- logs MQL5 et terminal MT5 ;
- résultats OOS, frontière de risque, calibration bar-level ;
- rapport complet et configuration EA `BOTH.set`.

Le serveur ne se lie qu'à `127.0.0.1` et ne partage rien sur le réseau.

## Mode agressif (novembre 2026)

L'EA supporte désormais les **re-entrées multiples** :

- `InpMaxTradesPerDay` : nombre max de trades/jour si `InpOneTradePerDay=false`
- `InpRequireFreshCross` : re-entrée uniquement après un retour sous le niveau
  du range (pas de re-chasse immédiate après un TP)

Lancement :

```powershell
# mode agressif 1R, max 2 trades/jour
C:\Python314\python.exe tools\launch_demo_both.py --risk 0.5 --target 1.0 --max-trades 2

# variante 2R (meilleur rapport rendement/DD sur l'OOS)
C:\Python314\python.exe tools\launch_demo_both.py --risk 0.5 --target 2.0 --max-trades 2
```

Résultats OOS 2022-2025 (bar-level, coût 1,7 pt) : 1R max 2 = +7,79 %
/DD 4,63 % ; 2R max 2 = +21,70 % / DD 5,89 % ; 3R max 1 (ancien) = +15,72 %
/DD 7,56 %. Détail : `out_orb_target_sweep/`.

## Pressure ORB (novembre 2026)

Variante de l'EA avec **filtre de pression des bougies** pour améliorer la qualité des entrées :

- Calcul de la pression acheteur/vendeur sur les 3 dernières bougies M15
- Entrée uniquement si la pression dépasse le seuil (0.6 par défaut)
- Money management corrigé : equity de base constante pour éviter l'explosion des lots
- Cap dur sur la taille de position : maximum 10 lots

Lancement :

```powershell
# Lancer le système Pressure ORB complet
.\start_pressure_simple.ps1

# Ou manuellement :
C:\Python314\python.exe tools\launch_pressure_demo.py --risk 0.5 --target 2.0 --max-trades 10 --buy-pressure 0.6 --sell-pressure 0.6 --pressure-bars 3
C:\Python314\python.exe web\app.py --port 8050
cloudflared tunnel --url http://127.0.0.1:8050 --no-autoupdate
```

Dashboard local : http://127.0.0.1:8050

## Déploiement Vercel

Le dashboard est déployé sur Vercel pour accès distant :

```powershell
# Déployer sur GitHub et Vercel
.\deploy_github.ps1
```

Voir `DEPLOYMENT_GUIDE.md` pour les instructions détaillées.

Architecture :
- **Frontend (Vercel)** : https://pressure-orb-dashboard.vercel.app
- **Backend (Local + Tunnel)** : Flask + Cloudflare Tunnel
- **MT5 (Local)** : Terminal avec EA attaché

## Notes importantes

- Le forward est en **0,5 %**, seul réglage compatible avec la règle de
  10 % de drawdown (DD OOS 7,56 %, ~6,6 $/jour OOS).
- Le 2,5 % et le 3,0 % donnent ~48-60 $/jour mais **31-16 % de drawdown OOS** ;
  ce ne sont pas des tests conformes.
- Aucun réglage testé ne donne 50 $/jour sous 10 % de drawdown avec ce seul
  instrument et ce capital.
- Le test 12 mois mélange ticks générés Q4 2025 et ticks réels 2026 ; la
  fenêtre 2026 est la plus fiable.
- Le token Telegram reste local dans `tools/telegram.env` et n'est jamais
  exposé par le site.

## Nettoyage

Les dossiers et fichiers obsolètes ont été supprimés ; le détail figure dans
`docs/CLEANUP_MANIFEST.md`. Le dépôt Git est enraciné dans le dossier
utilisateur, donc aucune commande `git clean` globale n'a été utilisée.
