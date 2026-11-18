# Watchdog ORB Pressure

Surveille la chaine live et relance automatiquement les composants critiques.

## Ce qu'il fait

- Toutes les minutes, via la tache planifiee **ORB Watchdog**.
- Si `terminal64.exe` est absent **pendant la session NY (09:30-23:00, lundi-vendredi)** :
  relance MT5 avec `PRESSURE_start.ini` (EA `ORB_Pressure` sur USTECm M15).
- Si aucun processus n'ecoute reellement sur le port `8050`, ou si `/api/health`
  ne repond pas : supprime les backends zombies puis relance Flask en arriere-plan
  (logs dans `logs/backend.out.log` et `logs/backend.err.log`).
- Si `cloudflared` est absent : declenche immediatement **ORB Tunnel Keeper**
  (au lieu d'attendre la prochaine execution planifiee, voir plus bas).
- Si le terminal tourne mais que l'EA n'est pas charge : avertissement dans le log.
- Detecte les trous de surveillance (veille/reveil) et active `StartWhenAvailable`
  sur les deux taches planifiees. Aucun reveil de la machine n'est programme.

Hors session NY, MT5 n'est pas relance automatiquement.

## Calculs live

- Le range ORB est uniquement la bougie **M15 de 09:30 NY**, exploitable apres
  sa cloture a **09:45 NY**. Avant 09:45, le dashboard affiche « en formation »
  et l'EA n'ouvre aucune position.
- La pression acheteur/vendeur est calculee sur les **N dernieres bougies M15
  cloturees** (`InpMinPressureBars`, 3 par defaut). Si la derniere bougie est deja
  cloturee (pause CME, reprise), elle est utilisee au lieu d'etre ignoree.
- Les dojis sont neutres : ils ne sont pas comptes dans le denominateur et ne
  tirent pas artificiellement la pression vers 0,5.
- L'EA et le backend appliquent la meme formule et le meme ordre de bougies.
  La pression affichee doit donc etre recalculable exactement depuis les bougies
  renvoyees par `/api/live`.
- Le sizing utilise l'equity courante, `SYMBOL_TRADE_TICK_VALUE_LOSS`, des SL/TP
  normalises au tick et refuse une entree si le lot minimum depasse le risque cible.
- La pause quotidienne CME de **17:00 a 18:00 NY** est affichee comme
  `feed_state=paused`, pas comme un flux figé.

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

Si le watchdog detecte `cloudflared` absent entre deux executions, il declenche
immediatement la tache **ORB Tunnel Keeper** : la coupure dure generalement
1 a 3 minutes au lieu de 5.

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
- La detection de l'EA lit les sept derniers journaux du terminal, les lignes
  `removed` et le demarrage du terminal, donc le passage a minuit ne declenche
  plus de fausse alerte.
- Le watchdog ne lance jamais une deuxieme instance de MT5 : il verifie d'abord
  `terminal64.exe` et ne demarre qu'une seule instance avec `PRESSURE_start.ini`.
- Ne pas lancer `cloudflared` manuellement : passer par `tools/quick_tunnel.ps1`
  pour que `dashboard/config.js` et Vercel restent synchronises.
- Le renouvellement peut prendre 1 a 2 minutes (creation du tunnel + propagation DNS
  + deploiement Vercel). L'ancien tunnel reste actif pendant cette phase.
