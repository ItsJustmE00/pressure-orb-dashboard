# Watchdog ORB Pressure

Surveille la chaine live et relance automatiquement les composants critiques.

## Ce qu'il fait

- Toutes les minutes, via la tache planifiee **ORB Watchdog**.
- Si `terminal64.exe` est absent **pendant la session NY (09:30-23:00, lundi-vendredi)** :
  relance MT5 avec `PRESSURE_start.ini` (EA `ORB_Pressure` sur USTECm M15).
- Si le backend Flask ne repond plus sur le port `8050` : le relance en arriere-plan
  (logs dans `logs/backend.out.log` et `logs/backend.err.log`).
- Si `cloudflared` est absent : ecrit un avertissement, sans recreer le tunnel
  (une relance du quick tunnel changerait l'URL et casserait `dashboard/config.js`).
- Si le terminal tourne mais que l'EA n'est pas charge : avertissement dans le log.

Hors session NY, MT5 n'est pas relance automatiquement.

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
```

## Notes

- Le terminal doit rester en une seule instance : le watchdog ne lance rien si
  `terminal64.exe` est deja present.
- L'EA restaure le range 09:30 NY et le nombre de trades du jour depuis l'historique
  apres un redemarrage, donc une relance ne bloque plus la journee.
- Ne pas relancer `cloudflared` sans mettre a jour `dashboard/config.js` et redeployer
  le frontend Vercel.
