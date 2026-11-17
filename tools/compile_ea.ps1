# Script PowerShell pour compiler les fichiers MQL5 sans bloquer
Set-Location c:\Users\moham\Downloads\agency-agents-main\agency-agents-main

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "COMPILING PRESSURE EA - ROBUST METHOD" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Arrêter MetaEditor s'il est ouvert
Write-Host "[Prep] Stopping any MetaEditor instances..." -ForegroundColor Yellow
Get-Process metaeditor64 -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

# Méthode 1: Utiliser MetaEditor avec /close
Write-Host "[1/3] Compiling ORB_Pressure.mq5..." -ForegroundColor Yellow
Start-Process -FilePath "C:\Program Files\MetaTrader 5\metaeditor64.exe" -ArgumentList "/compile /close mql5\orb_portfolio\ORB_Pressure.mq5" -Wait
Start-Sleep -Seconds 3

# Vérifier
if (Test-Path "mql5\orb_portfolio\ORB_Pressure.ex5") {
    Write-Host "[OK] ORB_Pressure.ex5 created" -ForegroundColor Green
} else {
    Write-Host "[FAIL] ORB_Pressure.ex5 not found, trying method 2..." -ForegroundColor Red
    # Méthode 2: Sans /close
    Start-Process -FilePath "C:\Program Files\MetaTrader 5\metaeditor64.exe" -ArgumentList "/compile mql5\orb_portfolio\ORB_Pressure.mq5"
    Write-Host "Please close MetaEditor manually when compilation is done" -ForegroundColor Yellow
    Start-Sleep -Seconds 5
}

# Compiler le script
Write-Host ""
Write-Host "[2/3] Compiling Open_USTECm_M15.mq5..." -ForegroundColor Yellow
Start-Process -FilePath "C:\Program Files\MetaTrader 5\metaeditor64.exe" -ArgumentList "/compile /close mql5\Scripts\Open_USTECm_M15.mq5" -Wait
Start-Sleep -Seconds 3

if (Test-Path "mql5\Scripts\Open_USTECm_M15.ex5") {
    Write-Host "[OK] Open_USTECm_M15.ex5 created" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Open_USTECm_M15.ex5 not found" -ForegroundColor Red
}

# Vérification finale
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "COMPILATION STATUS" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if (Test-Path "mql5\orb_portfolio\ORB_Pressure.ex5") {
    Write-Host "[X] ORB_Pressure.ex5 - OK" -ForegroundColor Green
} else {
    Write-Host "[ ] ORB_Pressure.ex5 - MISSING" -ForegroundColor Red
}

if (Test-Path "mql5\Scripts\Open_USTECm_M15.ex5") {
    Write-Host "[X] Open_USTECm_M15.ex5 - OK" -ForegroundColor Green
} else {
    Write-Host "[ ] Open_USTECm_M15.ex5 - MISSING" -ForegroundColor Red
}

if (Test-Path "mql5\orb_portfolio\ORB_Portfolio.ex5") {
    Write-Host "[X] ORB_Portfolio.ex5 (backup) - OK" -ForegroundColor Green
}

Write-Host ""
Write-Host "If files are missing, compile manually in MetaEditor:" -ForegroundColor Yellow
Write-Host "1. Open MetaEditor" -ForegroundColor White
Write-Host "2. File -> Open -> mql5\orb_portfolio\ORB_Pressure.mq5" -ForegroundColor White
Write-Host "3. Press F7 to compile" -ForegroundColor White
Write-Host "4. Repeat for mql5\Scripts\Open_USTECm_M15.mq5" -ForegroundColor White
Write-Host ""
