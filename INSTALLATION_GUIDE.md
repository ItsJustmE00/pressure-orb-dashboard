# Guide d'installation Pressure ORB - Étape par étape

## ⚠️ IMPORTANT : L'attachement automatique est limité par MT5

MetaTrader 5 a des restrictions de sécurité qui empêchent l'attachement automatique d'Expert Advisors via API externe. Vous devez effectuer quelques étapes manuelles simples.

---

## ÉTAPE 1 : Lancer le système complet

```powershell
cd c:\Users\moham\Downloads\agency-agents-main\agency-agents-main
.\start_pressure_complete.ps1
```

Cela va :
- ✅ Compiler ORB_Pressure.ex5
- ✅ Compiler Auto_Attach_Pressure.ex5
- ✅ Lancer MT5 avec config PRESSURE.set
- ✅ Démarrer le backend Flask
- ✅ Démarrer le tunnel Cloudflare
- ✅ Ouvrir le dashboard

---

## ÉTAPE 2 : Attacher l'EA (MANUEL - 2 minutes)

### 2.1 Ouvrir le graphique USTECm M15

1. Dans MT5, appuyez sur **Ctrl+N** pour ouvrir le Navigator
2. Allez dans le dossier **Scripts**
3. Double-cliquez sur **Auto_Attach_Pressure**
4. Cela va automatiquement ouvrir le graphique USTECm M15

### 2.2 Attacher l'EA

1. Dans le Navigator, allez dans le dossier **Experts**
2. Trouvez **ORB_Pressure.ex5**
3. **Glissez-le** sur le graphique USTECm M15
4. Une fenêtre "Expert Advisor" apparaît

### 2.3 Configurer l'EA

1. Dans la fenêtre de l'EA, cliquez sur l'onglet **Inputs**
2. Cliquez sur le bouton **Load**
3. Sélectionnez **PRESSURE.set**
4. Cliquez sur **OK**

### 2.4 Activer le trading

1. Sur le graphique, vous verrez un smiley 😊 dans le coin supérieur droit
2. Cliquez sur le smiley pour ouvrir les propriétés de l'EA
3. Cochez **"Allow live trading"**
4. Cliquez sur **OK**

### 2.5 Activer Algo Trading global

1. Dans la barre d'outils supérieure de MT5
2. Cliquez sur le bouton **"Algo Trading"** (icône de robot)
3. Il doit devenir **VERT** (activé)

---

## ÉTAPE 3 : Vérifier le dashboard

1. Ouvrez votre navigateur sur **http://127.0.0.1:8050**
2. Vous devriez voir :
   - ✅ "Pressure ORB" dans le titre
   - ✅ "MT5 connecté" dans la sidebar
   - ✅ Section "Pression des bougies" avec barres
   - ✅ Section "Candle Analysis" avec 3 bougies
   - ✅ Valeurs de pression qui se mettent à jour

---

## ÉTAPE 4 : Vérifier que l'EA fonctionne

Dans MT5, vous devriez voir :

1. **Dashboard visuel** sur le graphique (coin supérieur gauche)
2. **Message dans le journal** : "PRESSURE ORB initialized"
3. **Message de range** : "PRESSURE range high=... low=..." (après 09:30 NY)

Si vous ne voyez pas le dashboard visuel :
- Clic droit sur le graphique → Indicators → List
- Vérifiez que "ORB_Pressure" est dans la liste

---

## ÉTAPE 5 : Attendre le premier trade

- L'EA attendra **09:30 NY** pour commencer
- Le range est calculé de **09:30 à 09:45 NY**
- Après 09:45, l'EA surveille les cassures
- Si la pression ≥ 0.6, un trade sera pris

---

## Dépannage

### Problème : EA ne s'attache pas

**Solution :**
- Vérifiez que ORB_Pressure.ex5 existe dans `MQL5/Experts/orb_portfolio/`
- Recompilez : MetaEditor → File → Open → ORB_Pressure.mq5 → Compile

### Problème : Dashboard affiche "MT5 indisponible"

**Solution :**
- Vérifiez que le backend Flask tourne (terminal avec "Running on http://127.0.0.1:8050")
- Redémarrez le backend : Ctrl+C → relancez `python web\app.py --port 8050`

### Problème : Pression affiche "—"

**Solution :**
- L'EA doit être attaché et actif
- Les données de bougies doivent être disponibles
- Vérifiez que USTECm M15 a des données historiques

### Problème : Pas de trades

**Solution :**
- Vérifiez l'heure NY (doit être après 09:45)
- Vérifiez que "Algo Trading" est VERT
- Vérifiez que "Allow live trading" est coché sur l'EA
- Vérifiez le journal MT5 pour les erreurs

---

## Résumé rapide

1. ✅ Lancer `start_pressure_complete.ps1`
2. ✅ Dans MT5 Navigator → Scripts → Double-cliquer Auto_Attach_Pressure
3. ✅ Navigator → Experts → Glisser ORB_Pressure.ex5 sur le graphique
4. ✅ Load PRESSURE.set
5. ✅ Allow live trading
6. ✅ Activer Algo Trading (bouton vert)
7. ✅ Vérifier dashboard http://127.0.0.1:8050
8. ✅ Attendre 09:30 NY

---

## Configuration actuelle

- **Risque** : 0.5% par trade
- **Target** : 2R
- **Max trades/jour** : 10
- **Seuil pression** : 0.6 (buy et sell)
- **Barres analysées** : 3
- **Magic number** : 20261117

---

## Support

Si vous rencontrez des problèmes :
1. Vérifiez le journal MT5 (Journal onglet)
2. Vérifiez le terminal Flask (erreurs affichées)
3. Vérifiez que tous les fichiers sont compilés
4. Redémarrez MT5 et le backend si nécessaire
