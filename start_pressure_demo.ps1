# Script PowerShell pour lancer Pressure ORB Demo
cd c:\Users\moham\Downloads\agency-agents-main\agency-agents-main

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PRESSURE ORB DEMO - COMPLETE LAUNCH" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Étape 1: Compiler l'EA
Write-Host "[1/5] Compiling ORB_Pressure EA..." -ForegroundColor Yellow
& "C:\Program Files\MetaTrader 5\metaeditor64.exe" /compile /log "mql5\orb_portfolio\ORB_Pressure.mq5"
Start-Sleep -Seconds 5

# Étape 2: Lancer MT5
Write-Host "[2/5] Launching MT5 Terminal with Pressure config..." -ForegroundColor Yellow
C:\Python314\python.exe tools\launch_pressure_demo.py --risk 0.5 --target 2.0 --max-trades 10 --buy-pressure 0.6 --sell-pressure 0.6 --pressure-bars 3
Start-Sleep -Seconds 10

# Étape 3: Backend Flask
Write-Host "[3/5] Starting Flask Backend..." -ForegroundColor Yellow
Start-Process cmd -ArgumentList "/k", "cd /d c:\Users\moham\Downloads\agency-agents-main\agency-agents-main && C:\Python314\python.exe web\app.py --port 8050" -WindowStyle Normal
Start-Sleep -Seconds 5

# Étape 4: Tunnel Cloudflare
Write-Host "[4/5] Starting Cloudflare Tunnel..." -ForegroundColor Yellow
Start-Process cmd -ArgumentList "/k", "cloudflared tunnel --url http://127.0.0.1:8050 --no-autoupdate" -WindowStyle Normal
Start-Sleep -Seconds 5

# Étape 5: Ouvrir dashboard
Write-Host "[5/5] Opening local dashboard..." -ForegroundColor Yellow
Start-Process "http://127.0.0.1:8050"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "LAUNCH COMPLETE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Dashboard local: http://127.0.0.1:8050" -ForegroundColor White
Write-Host ""
Write-Host "MANUAL STEPS REQUIRED:" -ForegroundColor Yellow
Write-Host "1. In MT5, open USTECm M15 chart" -ForegroundColor White
Write-Host "2. Attach ORB_Pressure.ex5 to chart" -ForegroundColor White
Write-Host "3. Load PRESSURE.set preset" -ForegroundColor White
Write-Host "4. Enable Algo Trading" -ForegroundColor White
Write-Host "5. Wait for 09:30 NY for first trade" -ForegroundColor White
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
