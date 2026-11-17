# Script simplifié pour lancer Pressure ORB
Set-Location c:\Users\moham\Downloads\agency-agents-main\agency-agents-main

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PRESSURE ORB - SIMPLE LAUNCH" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Étape 1: Compiler via Python (plus fiable)
Write-Host "[1/4] Compiling EA and script..." -ForegroundColor Yellow
C:\Python314\python.exe tools\compile_ea.py
Start-Sleep -Seconds 3

# Vérifier si les fichiers existent
if (-not (Test-Path "mql5\orb_portfolio\ORB_Pressure.ex5")) {
    Write-Host "[ERROR] ORB_Pressure.ex5 not found!" -ForegroundColor Red
    Write-Host "Please compile manually in MetaEditor" -ForegroundColor Yellow
    pause
    exit
}

if (-not (Test-Path "mql5\Scripts\Open_USTECm_M15.ex5")) {
    Write-Host "[ERROR] Open_USTECm_M15.ex5 not found!" -ForegroundColor Red
    Write-Host "Please compile manually in MetaEditor" -ForegroundColor Yellow
    pause
    exit
}

Write-Host "[OK] Compilation successful" -ForegroundColor Green

# Étape 2: Générer preset et lancer MT5
Write-Host ""
Write-Host "[2/4] Launching MT5 with Pressure config..." -ForegroundColor Yellow
C:\Python314\python.exe tools\launch_pressure_demo.py --risk 0.5 --target 2.0 --max-trades 10 --buy-pressure 0.6 --sell-pressure 0.6 --pressure-bars 3
Start-Sleep -Seconds 10

# Étape 3: Backend Flask (ne pas relancer si déjà actif)
Write-Host ""
Write-Host "[3/4] Checking Flask Backend..." -ForegroundColor Yellow
$backend = Get-NetTCPConnection -LocalPort 8050 -State Listen -ErrorAction SilentlyContinue
if ($backend) {
    Write-Host "[OK] Backend already running (PID $($backend.OwningProcess))" -ForegroundColor Green
} else {
    Start-Process cmd -ArgumentList "/k", "cd /d c:\Users\moham\Downloads\agency-agents-main\agency-agents-main && C:\Python314\python.exe web\app.py --port 8050" -WindowStyle Normal
    Start-Sleep -Seconds 3
}

# Étape 4: Tunnel Cloudflare (ne pas relancer si déjà actif)
Write-Host ""
Write-Host "[4/4] Checking Cloudflare Tunnel..." -ForegroundColor Yellow
$tunnel = Get-Process cloudflared -ErrorAction SilentlyContinue
if ($tunnel) {
    Write-Host "[OK] Tunnel already running (PID $($tunnel[0].Id))" -ForegroundColor Green
} else {
    Start-Process cmd -ArgumentList "/k", "cloudflared tunnel --url http://127.0.0.1:8050 --no-autoupdate" -WindowStyle Normal
    Start-Sleep -Seconds 3
}

# Ouvrir dashboard
Write-Host ""
Write-Host "Opening local dashboard..." -ForegroundColor Green
Start-Process "http://127.0.0.1:8050"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "LAUNCH COMPLETE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Dashboard: http://127.0.0.1:8050" -ForegroundColor White
Write-Host ""
Write-Host "MANUAL STEPS IN MT5:" -ForegroundColor Yellow
Write-Host "1. Ctrl+N to open Navigator" -ForegroundColor White
Write-Host "2. Scripts -> Double-click Open_USTECm_M15" -ForegroundColor White
Write-Host "3. Experts -> Drag ORB_Pressure.ex5 to chart" -ForegroundColor White
Write-Host "4. Right-click EA -> Properties -> Load PRESSURE.set" -ForegroundColor White
Write-Host "5. Allow live trading" -ForegroundColor White
Write-Host "6. Enable Algo Trading (green button)" -ForegroundColor White
Write-Host ""
