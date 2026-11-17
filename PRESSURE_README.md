# Pressure ORB - Candle Buyer/Seller Momentum Strategy

## Nouvelle stratégie - Sans filtres EMA

Cette version remplace tous les filtres EMA/RSI par une analyse pure de la pression acheteur/vendeur basée sur les mouvements des bougies.

## Logique de calcul de la pression

### Pression Acheteuse (Buy Pressure)
Pour chaque bougie M15 :
- Calcul du body (|close - open|)
- Calcul du range (high - low)
- Calcul de la mèche supérieure (high - max(open, close))
- Si bougie verte (close > open) :
  - Pressure += (body/range) × (1 - mèche_supérieure/range)
- Si bougie rouge (close < open) :
  - Pressure -= (body/range) × (1 - mèche_inférieure/range)

Score final : normalisé entre 0 et 1

### Pression Vendeuse (Sell Pressure)
Même logique inversée pour les bougies rouges.

## Paramètres

- **InpMinPressureBars** : Nombre de bougies à analyser (défaut: 3)
- **InpBuyPressureMin** : Seuil de pression acheteuse (défaut: 0.6)
- **InpSellPressureMin** : Seuil de pression vendeuse (défaut: 0.6)
- **InpMaxTradesPerDay** : Max trades/jour (défaut: 10)
- **InpOneTradePerDay** : false (autorise multiples trades)
- **InpTargetR** : 2R (plus conservateur que 3R)

## Signal d'entrée

**Long** :
1. Cassure du high du range (09:30-09:45 NY)
2. Pression acheteuse ≥ 0.6 sur les 3 dernières bougies

**Short** :
1. Cassure du low du range
2. Pression vendeuse ≥ 0.6 sur les 3 dernières bougies

## Avantages

- **Pas de warmup D1** : Pas besoin de 360 barres daily
- **Plus de trades** : Jusqu'à 10/jour au lieu de 1
- **Réactivité** : Basé sur les bougies récentes uniquement
- **Mathématique pur** : Calcul basé sur la structure des bougies

## Lancement en démo

### Option 1 : Script tout-en-un

```powershell
cd c:\Users\moham\Downloads\agency-agents-main\agency-agents-main
.\start_pressure_demo.bat
```

### Option 2 : Manuel

#### Étape 1 : Compiler l'EA

```powershell
"C:\Program Files\MetaTrader 5\metaeditor64.exe" /compile "mql5\orb_portfolio\ORB_Pressure.mq5"
```

#### Étape 2 : Lancer MT5 avec config

```powershell
C:\Python314\python.exe tools\launch_pressure_demo.py --risk 0.5 --target 2.0 --max-trades 10
```

#### Étape 3 : Backend Flask

```powershell
C:\Python314\python.exe web\app.py --port 8050
```

#### Étape 4 : Tunnel Cloudflare (pour Vercel)

```powershell
cloudflared tunnel --url http://127.0.0.1:8050 --no-autoupdate
```

#### Étape 5 : Mettre à jour Vercel

```powershell
cd dashboard
notepad config.js
# Changer window.ORB_API_BASE avec l'URL du tunnel
vercel --prod
```

## Configuration Vercel

Le backend Flask est déjà configuré pour accepter les requêtes CORS de Vercel.

### Mettre à jour config.js

```javascript
// dashboard/config.js
window.ORB_API_BASE = "https://VOTRE-URL-TRYCLOUDFLARE.trycloudflare.com";
```

### Redéployer

```powershell
cd dashboard
vercel --prod
```

## Objectif : 50+ trades

Avec cette configuration :
- Max 10 trades/jour
- 5 jours/semaine = 50 trades/semaine
- 2 semaines = 100 trades
- 1 mois = ~200 trades

## Surveillance

Le dashboard affiche :
- Pression acheteuse/vendeuse en temps réel
- Filtres actifs (OK/WAIT)
- Nombre de trades du jour
- P&L et drawdown

## Avertissement

- Toujours en **DÉMO uniquement**
- Aucun ordre réel autorisé
- La pression calculée est basée sur les bougies passées
- Les résultats futurs peuvent différer
- DD potentiel >10% avec 10 trades/jour
