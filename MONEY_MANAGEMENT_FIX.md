# Correction Money Management - ORB_Pressure

## Problème identifié dans le backtest

### Résultats catastrophiques
- **Perte totale : -50 004.42 $ (100%)**
- **Drawdown maximal : 100%**
- **Tailles de position explosives** : de 1-2 lots → 500 lots
- **Cause** : Le calcul de la taille de position utilisait `ACCOUNT_BALANCE` qui diminue avec les pertes

### Bug dans l'EA original
```mql5
// ANCIEN CODE (BUGGY)
double risk_money = AccountInfoDouble(ACCOUNT_BALANCE) * InpRiskPct / 100.0;
double lots = risk_money / (stop_distance / tick_size * tick_value);
```

**Problème** : Quand le solde diminue (après des pertes), le risque en dollars diminue aussi, MAIS la taille de position calculée augmente pour compenser, créant un effet de levier explosif.

---

## Corrections apportées

### 1. **Equity de base constante**
```mql5
// NOUVEAU CODE (FIXED)
double g_base_equity = 0.0;  // Stockée globalement

int OnInit()
{
   g_base_equity = AccountInfoDouble(ACCOUNT_EQUITY);
   // g_base_equity reste constant pendant toute la session
}

bool EnterTrade(...)
{
   if(g_base_equity <= 0.0)
      g_base_equity = AccountInfoDouble(ACCOUNT_EQUITY);
   
   double risk_money = g_base_equity * InpRiskPct / 100.0;
   double lots = risk_money / (stop_distance / tick_size * tick_value);
}
```

**Avantage** : Le risque en dollars reste constant (0.5% de l'equity initiale), donc la taille de position reste stable même après des pertes.

### 2. **Cap dur sur la taille de position**
```mql5
// SAFETY: Cap lots to prevent explosion
double max_lots = 10.0;  // Hard cap
if(lots > max_lots)
{
   Print("PRESSURE: Lot size capped at ", max_lots, " (calculated: ", lots, ")");
   lots = max_lots;
}
```

**Avantage** : Même en cas de bug, la taille de position ne peut pas dépasser 10 lots.

### 3. **Pas de reset de l'equity de base**
```mql5
void ResetDay(datetime day)
{
   g_day = day;
   g_high = 0.0;
   g_low = 0.0;
   g_range_ready = false;
   g_trades_today = 0;
   // Don't reset base equity - keep it constant
}
```

**Avantage** : L'equity de base reste constante d'un jour à l'autre, assurant une gestion du risque cohérente.

---

## Résultats attendus

### Avant la correction
- Tailles de position : 1 → 2 → 5 → 20 → 100 → 500 lots
- Risque réel : 0.5% → 1% → 5% → 20% → 100% → 500%
- Résultat : Perte totale du capital

### Après la correction
- Tailles de position : ~1-2 lots constantes
- Risque réel : 0.5% constant
- Résultat : Gestion du risque stable, drawdown contrôlé

---

## Configuration actuelle

- **Risque par trade** : 0.5% de l'equity initiale
- **Target** : 2R
- **Max trades/jour** : 10
- **Cap dur sur lots** : 10 lots maximum
- **Seuils de pression** : 0.6 buy/sell

---

## Recommandations pour le backtest

1. **Relancer le backtest** avec le nouvel EA
2. **Vérifier** que les tailles de position restent stables (~1-2 lots)
3. **Surveiller** le drawdown maximal (devrait être < 20%)
4. **Confirmer** que le facteur de profit est > 1.0

---

## Fichier modifié

- `mql5/orb_portfolio/ORB_Pressure.mq5` : Money management corrigé
- `mql5/orb_portfolio/ORB_Pressure.ex5` : Recompilé avec les corrections

---

## Prochaine étape

Relancer le backtest dans MT5 Strategy Tester pour vérifier que les corrections résolvent le problème de taille de position explosive.
