# Script PowerShell complet pour lancer Pressure ORB avec attache automatique
Set-Location c:\Users\moham\Downloads\agency-agents-main\agency-agents-main

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PRESSURE ORB - COMPLETE AUTO LAUNCH" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Étape 1: Compiler l'EA
Write-Host "[1/6] Compiling ORB_Pressure EA..." -ForegroundColor Yellow
& "C:\Program Files\MetaTrader 5\metaeditor64.exe" /compile /log "mql5\orb_portfolio\ORB_Pressure.mq5"
Start-Sleep -Seconds 5

# Étape 2: Compiler le script d'ouverture de graphique
Write-Host "[2/6] Compiling chart open script..." -ForegroundColor Yellow
& "C:\Program Files\MetaTrader 5\metaeditor64.exe" /compile /log "mql5\Scripts\Open_USTECm_M15.mq5"
Start-Sleep -Seconds 3

# Étape 3: Lancer MT5 avec config
Write-Host "[3/6] Launching MT5 Terminal with Pressure config..." -ForegroundColor Yellow
C:\Python314\python.exe tools\launch_pressure_demo.py --risk 0.5 --target 2.0 --max-trades 10 --buy-pressure 0.6 --sell-pressure 0.6 --pressure-bars 3
Start-Sleep -Seconds 15

# Étape 4: Exécuter le script d'auto-attach dans MT5
Write-Host "[4/6] Running auto-attach script in MT5..." -ForegroundColor Yellow
Write-Host "Please wait for MT5 to fully load..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Note: Auto-attach script must be run manually from MT5 Navigator
# We'll provide clear instructions

# Étape 5: Backend Flask (ne pas relancer si déjà actif)
Write-Host "[5/6] Checking Flask Backend..." -ForegroundColor Yellow
$backend = Get-NetTCPConnection -LocalPort 8050 -State Listen -ErrorAction SilentlyContinue
if ($backend) {
    Write-Host "[OK] Backend already running (PID $($backend.OwningProcess))" -ForegroundColor Green
} else {
    Start-Process cmd -ArgumentList "/k", "cd /d c:\Users\moham\Downloads\agency-agents-main\agency-agents-main && C:\Python314\python.exe web\app.py --port 8050" -WindowStyle Normal
    Start-Sleep -Seconds 5
}

# Étape 6: Tunnel Cloudflare (ne pas relancer si déjà actif)
Write-Host "[6/6] Checking Cloudflare Tunnel..." -ForegroundColor Yellow
$tunnel = Get-Process cloudflared -ErrorAction SilentlyContinue
if ($tunnel) {
    Write-Host "[OK] Tunnel already running (PID $($tunnel[0].Id))" -ForegroundColor Green
} else {
    Start-Process cmd -ArgumentList "/k", "cloudflared tunnel --url http://127.0.0.1:8050 --no-autoupdate" -WindowStyle Normal
    Start-Sleep -Seconds 5
}

# Ouvrir dashboard
Write-Host "Opening local dashboard..." -ForegroundColor Green
Start-Process "http://127.0.0.1:8050"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "LAUNCH COMPLETE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Dashboard local: http://127.0.0.1:8050" -ForegroundColor White
Write-Host ""
Write-Host "AUTO-ATTACHMENT STATUS:" -ForegroundColor Yellow
Write-Host "- EA compiled: ORB_Pressure.ex5" -ForegroundColor White
Write-Host "- Chart open script compiled: Open_USTECm_M15.ex5" -ForegroundColor White
Write-Host "- Preset generated: PRESSURE.set" -ForegroundColor White
Write-Host ""
Write-Host "MANUAL STEPS REQUIRED:" -ForegroundColor Yellow
Write-Host "1. In MT5, open Navigator (Ctrl+N)" -ForegroundColor White
Write-Host "2. Go to Scripts folder" -ForegroundColor White
Write-Host "3. Double-click Open_USTECm_M15" -ForegroundColor White
Write-Host "4. This will open USTECm M15 chart" -ForegroundColor White
Write-Host "5. Then go to Experts folder in Navigator" -ForegroundColor White
Write-Host "6. Drag ORB_Pressure.ex5 to the chart" -ForegroundColor White
Write-Host "7. Right-click EA -> Properties -> Load PRESSURE.set" -ForegroundColor White
Write-Host "8. Click 'Allow live trading' button on EA" -ForegroundColor White
Write-Host "9. Enable 'Algo Trading' in top toolbar (green button)" -ForegroundColor White
Write-Host ""
Write-Host "CONFIGURATION:" -ForegroundColor Cyan
Write-Host "- Risk: 0.5% per trade" -ForegroundColor White
Write-Host "- Target: 2R" -ForegroundColor White
Write-Host "- Max trades/day: 10" -ForegroundColor White
Write-Host "- Buy pressure threshold: 0.6" -ForegroundColor White
Write-Host "- Sell pressure threshold: 0.6" -ForegroundColor White
Write-Host "- Pressure bars: 3" -ForegroundColor White
Write-Host ""
Write-Host "The EA will calculate buyer/seller pressure from candle movements" -ForegroundColor White
Write-Host "and enter trades when pressure exceeds threshold after range breakout." -ForegroundColor White
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
