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

# Identité locale obligatoire pour pouvoir committer
if (-not (git config user.name)) {
    git config user.name "Moham"
    Write-Host "[OK] Local user.name configured" -ForegroundColor Green
}
if (-not (git config user.email)) {
    git config user.email "moham@example.com"
    Write-Host "[OK] Local user.email configured" -ForegroundColor Green
}

# Étape 2: Ajouter les fichiers
Write-Host ""
Write-Host "[2/3] Adding files to Git..." -ForegroundColor Yellow
git add .
$staged = git diff --cached --name-only
if ($staged) {
    git commit -m "Pressure ORB Dashboard - Fixed money management, pressure metrics, Vercel deployment"
    Write-Host "[OK] Files committed" -ForegroundColor Green
} else {
    Write-Host "[OK] Nothing to commit" -ForegroundColor Green
}

# Étape 3: Remote GitHub et push
Write-Host ""
Write-Host "[3/3] GitHub setup..." -ForegroundColor Yellow
$remote = git remote get-url origin 2>$null
if (-not $remote) {
    git remote add origin "https://ItsJustmE00@github.com/ItsJustmE00/pressure-orb-dashboard.git"
    $remote = git remote get-url origin
}
Write-Host "[OK] Remote configured: $remote" -ForegroundColor Green
if (-not (git rev-parse --verify HEAD 2>$null)) {
    git commit --allow-empty -m "Initial commit"
}
git branch -M main
Write-Host "Pushing to GitHub..." -ForegroundColor Yellow
git push -u origin main

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "GIT INITIALISATION COMPLETE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
