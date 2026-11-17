# Nettoyage du projet — 14 novembre 2026

## Conservé
- `mql5/orb_portfolio/` : EA ORB BOTH, README, binaires et logs de compilation.
- `tools/` : uniquement les scripts ORB récents (recherche, features, configs tester, lancement démo, parsing, Telegram ORB).
- `out_nas100_orb*`, `out_orb_*`, `out_us30_orb*`, `out_us500_orb_recent`, `out_spy_orb`, `out_xauusd_orb` : sorties de recherche ORB et validations multi-instruments.
- `data_live/` : parquets NAS100/US30 utiles, sans ticks ni archives obsolètes.
- `out_orb_portfolio_57k/`, `out_orb_both_oos/`, `out_orb_both_oos_risk/` : résultats de référence et configurations MT5.
- `mql5/` : `orb_portfolio` uniquement ; les anciens EAs sont supprimés.
- `LICENSE`, `.gitignore`, `.gitattributes`, `opencode.json`.

## Supprimé
- `agent-world/` : application Tauri/Vite sans rapport avec le bot (environ 6 Go, principalement `node_modules`).
- Dossiers du template `agency-agents` : `academic/`, `design/`, `engineering/`, `examples/`, `finance/`, `game-development/`, `gis/`, `healthcare/`, `integrations/`, `marketing/`, `paid-media/`, `product/`, `project-management/`, `research/`, `sales/`, `scripts/`, `security/`, `spatial-computing/`, `specialized/`, `strategy/`, `support/`, `testing/`, `.github/`, `assets/`.
- Ancien projet Quant9/XAU : fichiers `xau_*`, `gold_*`, `XAU_GoldRecette.*`, `RAPPORT_PROJET.md`, `RAPPORT_RISK_MANAGER.md`, `equity_final.*`, `optim_grid.csv`, `growth_paths.png`, `repartition_curve.png`, `data/`, `state/`, `mmbot/`.
- Anciennes recherches crypto, forex, news et micro-structure : dossiers `out_ab`, `out_check`, `out_crypto`, `out_daily_conditions`, `out_demo`, `out_edge_scan_fx`, `out_funding`, `out_intraday_edge`, `out_loop`, `out_narrow_overnight`, `out_nas100_ict_news*`, `out_news_*`, `out_oos_m15_*`, `out_real*`, `out_research`, `out_search`, `out_sessions`, `out_sim_*`, `out_test`, `out_validation`, `out_val_smoke`, `out` ; scripts et données associés.
- Anciens EAs : `mql5/nas100_ict_news/` et presets/experts XAU.
- Archives et données inutiles : `data_live/ticks/`, `data_live/kaggle_us30.zip`, `kaggle_sp500_intraday.zip`, `kaggle_spx500_15m.zip`, `kaggle_xauusd.zip`, `USTEC_all_timeframes.zip`, `data_live/fx_h1.parquet`, `h1_sessions.pkl`, `nas100_h1_kaggle.parquet`, `spy_m15_utc.parquet`, `us500_m15.parquet`, `xauusd_m15_kaggle_utc.parquet`, `us_news_*`, `state.json`, `heartbeat.json`.
- Template racine : `README.md` (remplacé), `CONTRIBUTING*`, `SECURITY.md`, `divisions.json`, `tools.json`.
- Caches et logs temporaires : `__pycache__/`, `.pytest_cache/`, `sim_logs/`, `tools/telegram_bridge.*`, `tools/telegram_histoire.txt`, `tools/telegram_inbox.jsonl`, `tools/telegram_summary.txt`.

## Remarque
Le dépôt Git est enraciné dans `C:\Users\moham`, pas dans ce dossier. Aucun `git clean` global n'a été utilisé. Les suppressions ont été limitées au dossier du projet.

## Après nettoyage
- `README.md` : README du projet ORB et lancement du dashboard.
- `web/` : dashboard Flask connecté à MT5 et aux résultats.
- `web/data/direct_runs.json` : résultats direct MT5 consolidés.
- `start_web.ps1` : lancement local du dashboard.
- `requirements-web.txt` : dépendances Python du dashboard.
- `docs/CLEANUP_MANIFEST.md` : ce manifeste.

