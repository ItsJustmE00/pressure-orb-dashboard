# Script PowerShell pour lancer le système Pressure ORB complet
# - MT5 avec EA
# - Backend Flask
# - Tunnel Cloudflare
# - Dashboard Vercel

Set-Location c:\Users\moham\Downloads\agency-agents-main\agency-agents-main

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PRESSURE ORB - FULL SYSTEM LAUNCH" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Étape 1: Compiler l'EA
Write-Host "[1/5] Compiling ORB_Pressure EA..." -ForegroundColor Yellow
C:\Python314\python.exe tools\compile_ea.py
Write-Host "[OK] EA compiled" -ForegroundColor Green
Write-Host ""

# Étape 2: Lancer MT5 (si pas déjà lancé)
Write-Host "[2/5] Checking MT5..." -ForegroundColor Yellow
$mt5Process = Get-Process -Name "terminal64" -ErrorAction SilentlyContinue
if ($mt5Process) {
    Write-Host "[OK] MT5 already running" -ForegroundColor Green
} else {
    Write-Host "[INFO] Please launch MT5 manually" -ForegroundColor Yellow
    Write-Host "   Path: C:\Program Files\MetaTrader 5\terminal64.exe" -ForegroundColor Gray
    Write-Host "   Config: PRESSURE.set" -ForegroundColor Gray
    Write-Host "   Attach ORB_Pressure.ex5 to USTECm M15 chart" -ForegroundColor Gray
}
Write-Host ""

# Étape 3: Lancer le backend Flask
Write-Host "[3/5] Starting Flask backend..." -ForegroundColor Yellow
$backendProcess = Start-Process -FilePath "C:\Python314\python.exe" -ArgumentList "web\app.py --port 8050" -PassThru -WindowStyle Minimized
Start-Sleep -Seconds 3
Write-Host "[OK] Backend started on http://127.0.0.1:8050" -ForegroundColor Green
Write-Host ""

# Étape 4: Lancer le tunnel Cloudflare
Write-Host "[4/5] Starting Cloudflare tunnel..." -ForegroundColor Yellow
$tunnelProcess = Start-Process -FilePath "cloudflared" -ArgumentList "tunnel --url http://127.0.0.1:8050 --no-autoupdate" -PassThru -WindowStyle Normal
Write-Host "[OK] Cloudflare tunnel starting..." -ForegroundColor Green
Write-Host "   Check the tunnel window for the public URL" -ForegroundColor Gray
Write-Host "   Update dashboard/config.js if URL changes" -ForegroundColor Gray
Write-Host ""

# Étape 5: Ouvrir le dashboard Vercel
Write-Host "[5/5] Opening Vercel dashboard..." -ForegroundColor Yellow
Start-Process "https://orb-dashboard-five.vercel.app"
Write-Host "[OK] Dashboard opened" -ForegroundColor Green
Write-Host ""

Write-Host "========================================" -ForegroundColor Green
Write-Host "SYSTEM LAUNCHED" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Backend PID: $($backendProcess.Id)" -ForegroundColor White
Write-Host "Tunnel PID: $($tunnelProcess.Id)" -ForegroundColor White
Write-Host ""
Write-Host "To stop the system:" -ForegroundColor Yellow
Write-Host "  1. Close tunnel window" -ForegroundColor Gray
Write-Host "  2. Stop backend: Stop-Process -Id $($backendProcess.Id)" -ForegroundColor Gray
Write-Host "  3. Close MT5" -ForegroundColor Gray
Write-Host ""
Write-Host "Trading hours:" -ForegroundColor Cyan
Write-Host "  - Range: 09:30-09:45 NY" -ForegroundColor White
Write-Host "  - Entry: 09:45-23:00 NY (FULL DAY)" -ForegroundColor White
Write-Host "  - Close: 23:00 NY" -ForegroundColor White
Write-Host ""
Write-Host "Time zones:" -ForegroundColor Cyan
Write-Host "  - New York: UTC-4 / UTC-5" -ForegroundColor White
Write-Host "  - Casablanca: GMT+1" -ForegroundColor White
Write-Host ""
