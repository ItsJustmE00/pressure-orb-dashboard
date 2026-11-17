# Script PowerShell pour initialiser Git et pousser vers GitHub
Set-Location c:\Users\moham\Downloads\agency-agents-main\agency-agents-main

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "INITIALISATION GIT + PUSH GITHUB" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Étape 1: Initialiser Git si nécessaire
Write-Host "[1/3] Initializing Git repository..." -ForegroundColor Yellow
if (-not (Test-Path .git)) {
    git init
    Write-Host "[OK] Git repository initialized" -ForegroundColor Green
} else {
    Write-Host "[OK] Git repository already exists" -ForegroundColor Green
}

# Étape 2: Ajouter les fichiers
Write-Host ""
Write-Host "[2/3] Adding files to Git..." -ForegroundColor Yellow
git add .
git commit -m "Pressure ORB Dashboard - Fixed money management, pressure metrics, Vercel deployment"
Write-Host "[OK] Files committed" -ForegroundColor Green

# Étape 3: Instructions pour GitHub
Write-Host ""
Write-Host "[3/3] GitHub setup..." -ForegroundColor Yellow
$remote = git remote get-url origin 2>$null
if ($remote) {
    Write-Host "[OK] Remote already configured: $remote" -ForegroundColor Green
    Write-Host ""
    Write-Host "Pushing to GitHub..." -ForegroundColor Yellow
    git push -u origin main
} else {
    Write-Host "[WARN] No Git remote configured" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Please follow these steps:" -ForegroundColor White
    Write-Host "1. Create a new repository on GitHub: https://github.com/new" -ForegroundColor Gray
    Write-Host "   - Repository name: pressure-orb-dashboard" -ForegroundColor Gray
    Write-Host "   - Make it Public (for free Vercel deployment)" -ForegroundColor Gray
    Write-Host "   - DO NOT initialize with README" -ForegroundColor Gray
    Write-Host ""
    Write-Host "2. Add the remote:" -ForegroundColor White
    Write-Host "   git remote add origin https://github.com/YOUR_USERNAME/pressure-orb-dashboard.git" -ForegroundColor Gray
    Write-Host ""
    Write-Host "3. Push to GitHub:" -ForegroundColor White
    Write-Host "   git push -u origin main" -ForegroundColor Gray
    Write-Host ""
    Write-Host "4. Then run: .\deploy_github.ps1" -ForegroundColor White
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "GIT INITIALISATION COMPLETE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
