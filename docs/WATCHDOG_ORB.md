# Watchdog ORB Pressure

Surveille la chaine live et relance automatiquement les composants critiques.

## Ce qu'il fait

- Toutes les minutes, via la tache planifiee **ORB Watchdog**.
- Si `terminal64.exe` est absent **pendant la session NY (09:30-23:00, lundi-vendredi)** :
  relance MT5 avec `PRESSURE_start.ini` (EA `ORB_Pressure` sur USTECm M15).
- Si le backend Flask ne repond plus sur le port `8050` : le relance en arriere-plan
  (logs dans `logs/backend.out.log` et `logs/backend.err.log`).
- Si `cloudflared` est absent : ecrit un avertissement (le renouvellement du tunnel
  est assure par **ORB Tunnel Keeper**, voir plus bas).
- Si le terminal tourne mais que l'EA n'est pas charge : avertissement dans le log.

Hors session NY, MT5 n'est pas relance automatiquement.

## Renouvellement du quick tunnel

Le quick tunnel Cloudflare (`trycloudflare.com`) est gratuit mais ephemere. La tache
planifiee **ORB Tunnel Keeper** execute `tools/quick_tunnel.ps1 -Check` toutes les
5 minutes :

1. verifie que l'URL de `dashboard/config.js` repond sur `/api/health` ;
2. verifie que Vercel sert bien cette meme URL ;
3. si le tunnel est mort, demarre un **candidat** sans couper l'ancien ;
4. attend que le candidat soit reellement joignable (propagation DNS) ;
5. met a jour `dashboard/config.js`, redéploie Vercel, puis seulement ensuite
   arrete l'ancien tunnel ;
6. commit et pousse `dashboard` et le depot principal.

Le candidat et son PID sont conserves dans `logs/quick_tunnel_state.json` : si une
bascule est interrompue, la verification suivante reprend la finalisation.

## Commandes utiles

```powershell
# Voir le log
Get-Content logs\watchdog.log -Tail 20

# Executer une verification immediate
.\tools\watchdog_orb.ps1 -Once

# Desactiver / reactiver la surveillance
Disable-ScheduledTask -TaskName 'ORB Watchdog'
Enable-ScheduledTask  -TaskName 'ORB Watchdog'

# Etat de la tache
Get-ScheduledTaskInfo -TaskName 'ORB Watchdog'

# Tunnel : etat, verification, renouvellement force
.\tools\quick_tunnel.ps1 -Status
.\tools\quick_tunnel.ps1 -Check
.\tools\quick_tunnel.ps1 -Renew

# Etat de la tache tunnel
Get-ScheduledTaskInfo -TaskName 'ORB Tunnel Keeper'
```

## Notes

- Le terminal doit rester en une seule instance : le watchdog ne lance rien si
  `terminal64.exe` est deja present.
- L'EA restaure le range 09:30 NY et le nombre de trades du jour depuis l'historique
  apres un redemarrage, donc une relance ne bloque plus la journee.
- La detection de l'EA lit les trois derniers journaux du terminal (et les lignes
  `removed`), donc le passage a minuit ne declenche plus de fausse alerte.
- Ne pas lancer `cloudflared` manuellement : passer par `tools/quick_tunnel.ps1`
  pour que `dashboard/config.js` et Vercel restent synchronises.
- Le renouvellement peut prendre 1 a 2 minutes (creation du tunnel + propagation DNS
  + deploiement Vercel). L'ancien tunnel reste actif pendant cette phase.
