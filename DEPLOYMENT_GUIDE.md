# Guide de Déploiement - Pressure ORB Dashboard

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Vercel (Frontend)                        │
│  https://pressure-orb-dashboard.vercel.app                  │
│  - dashboard/index.html                                      │
│  - dashboard/app.js                                          │
│  - dashboard/style.css                                       │
│  - dashboard/config.js (API URL)                             │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Cloudflare Tunnel (Backend)                     │
│  https://compact-recovery-renaissance-veterans.trycloudflare.com │
│  - Redirige vers localhost:8050                             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Flask Backend (Local)                          │
│  http://127.0.0.1:8050                                       │
│  - web/app.py                                               │
│  - web/mt5_service.py                                       │
│  - web/results_service.py                                   │
│  - MT5 Terminal (local)                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Étape 1 : Préparer le dépôt GitHub

### 1.1 Initialiser Git (si pas déjà fait)

```bash
cd c:\Users\moham\Downloads\agency-agents-main\agency-agents-main
git init
git add .
git commit -m "Initial commit - Pressure ORB Dashboard"
```

### 1.2 Créer le dépôt sur GitHub

1. Allez sur https://github.com/new
2. Nom du dépôt : `pressure-orb-dashboard`
3. Public ou Private (Public pour Vercel gratuit)
4. Ne PAS initialiser avec README
5. Créer

### 1.3 Connecter le local au distant

```bash
git remote add origin https://github.com/VOTRE_USERNAME/pressure-orb-dashboard.git
git branch -M main
git push -u origin main
```

---

## Étape 2 : Déployer sur Vercel

### 2.1 Installer Vercel CLI (si pas déjà installé)

```bash
npm install -g vercel
```

### 2.2 Se connecter à Vercel

```bash
vercel login
```

### 2.3 Déployer le dashboard

```bash
cd c:\Users\moham\Downloads\agency-agents-main\agency-agents-main\dashboard
vercel
```

Répondre aux questions :
- **Set up and deploy?** `Y`
- **Scope:** Votre compte Vercel
- **Link to existing project?** `N`
- **Project name:** `pressure-orb-dashboard`
- **Directory:** `./` (dashboard)
- **Override settings?** `N`

Vercel va déployer et donner une URL comme :
`https://pressure-orb-dashboard.vercel.app`

### 2.4 Déployer en production

```bash
vercel --prod
```

---

## Étape 3 : Lancer le backend avec tunnel

### 3.1 Lancer le backend Flask

```bash
cd c:\Users\moham\Downloads\agency-agents-main\agency-agents-main
C:\Python314\python.exe web\app.py --port 8050
```

### 3.2 Lancer le tunnel Cloudflare

Dans un nouveau terminal :

```bash
cloudflared tunnel --url http://127.0.0.1:8050 --no-autoupdate
```

Notez l'URL générée (ex: `https://xxx.trycloudflare.com`)

### 3.3 Mettre à jour config.js

Si l'URL du tunnel change, modifiez `dashboard/config.js` :

```javascript
window.ORB_API_BASE = "https://VOTRE_NOUVELLE_URL.trycloudflare.com";
```

Puis redéployez sur Vercel :

```bash
cd dashboard
vercel --prod
```

---

## Étape 4 : Lancer le système complet

Utilisez le script PowerShell :

```powershell
cd c:\Users\moham\Downloads\agency-agents-main\agency-agents-main
.\start_pressure_simple.ps1
```

Ou manuellement :

1. **Lancer MT5** avec config PRESSURE
2. **Attacher ORB_Pressure.ex5** au graphique USTECm M15
3. **Lancer backend** : `python web\app.py --port 8050`
4. **Lancer tunnel** : `cloudflared tunnel --url http://127.0.0.1:8050`
5. **Ouvrir dashboard** : https://pressure-orb-dashboard.vercel.app

---

## Étape 5 : Vérifier le déploiement

### 5.1 Vérifier le frontend

Ouvrez : `https://pressure-orb-dashboard.vercel.app`

Vous devriez voir :
- ✅ Interface "Pressure ORB"
- ✅ Barres de pression
- ✅ Bougies visualisées
- ✅ Données MT5 (si backend actif)

### 5.2 Vérifier l'API

Ouvrez dans le navigateur :
`https://pressure-orb-dashboard.vercel.app/api/health`

Vous devriez voir :
```json
{
  "ok": true,
  "time": "2026-11-17T02:45:00Z",
  "terminal_running": true|false,
  "mt5_connected": true|false
}
```

---

## Mises à jour

### Pour mettre à jour le frontend

```bash
cd dashboard
# Modifier les fichiers
git add .
git commit -m "Update dashboard"
git push
vercel --prod
```

### Pour mettre à jour le backend

Le backend reste local, pas besoin de redéployer sur Vercel.
Juste redémarrez le backend Flask :

```bash
# Arrêter (Ctrl+C)
C:\Python314\python.exe web\app.py --port 8050
```

---

## Dépannage

### Dashboard affiche "MT5 indisponible"

- Vérifiez que le backend Flask tourne (localhost:8050)
- Vérifiez que le tunnel Cloudflare est actif
- Vérifiez que l'URL dans `config.js` correspond au tunnel

### CORS errors

- Le backend a déjà les headers CORS configurés
- Vérifiez que `config.js` pointe vers la bonne URL

### Tunnel Cloudflare ne fonctionne pas

```bash
# Réessayer
cloudflared tunnel --url http://127.0.0.1:8050 --no-autoupdate
```

---

## URLs importantes

- **Frontend (Vercel)** : https://pressure-orb-dashboard.vercel.app
- **Backend (Tunnel)** : https://compact-recovery-renaissance-veterans.trycloudflare.com
- **Backend (Local)** : http://127.0.0.1:8050
- **GitHub** : https://github.com/VOTRE_USERNAME/pressure-orb-dashboard

---

## Structure des fichiers

```
agency-agents-main/
├── dashboard/              # Frontend (Vercel)
│   ├── index.html
│   ├── app.js
│   ├── style.css
│   ├── config.js          # API URL
│   └── vercel.json       # Config Vercel
├── web/                   # Backend (Local)
│   ├── app.py
│   ├── mt5_service.py
│   └── results_service.py
├── mql5/orb_portfolio/    # EA MT5
│   ├── ORB_Pressure.mq5
│   └── ORB_Pressure.ex5
└── tools/                 # Scripts utilitaires
    ├── compile_ea.py
    └── launch_pressure_demo.py
```

---

## Sécurité

- Le backend reste local (pas exposé publiquement)
- Le tunnel Cloudflare fournit un HTTPS sécurisé
- Le dashboard Vercel est public mais ne contient pas de données sensibles
- Les clés API MT5 ne sont pas stockées dans le code
