# Script PowerShell pour déployer sur GitHub et Vercel
Set-Location c:\Users\moham\Downloads\agency-agents-main\agency-agents-main

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "DEPLOIEMENT GITHUB + VERCEL" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Étape 1: Vérifier Git
Write-Host "[1/5] Checking Git installation..." -ForegroundColor Yellow
try {
    $gitVersion = git --version
    Write-Host "[OK] Git installed: $gitVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Git not installed. Install from https://git-scm.com/" -ForegroundColor Red
    exit 1
}

# Étape 2: Initialiser Git si nécessaire
Write-Host ""
Write-Host "[2/5] Checking Git repository..." -ForegroundColor Yellow
if (-not (Test-Path .git)) {
    Write-Host "Initializing Git repository..." -ForegroundColor Yellow
    git init
    git add .
    git commit -m "Initial commit - Pressure ORB Dashboard with fixed money management"
    Write-Host "[OK] Git repository initialized" -ForegroundColor Green
} else {
    Write-Host "[OK] Git repository already exists" -ForegroundColor Green
}

# Étape 3: Vérifier remote
Write-Host ""
Write-Host "[3/5] Checking Git remote..." -ForegroundColor Yellow
$remote = git remote get-url origin 2>$null
if (-not $remote) {
    Write-Host "[WARN] No Git remote configured" -ForegroundColor Yellow
    Write-Host "Please run: git remote add origin https://github.com/YOUR_USERNAME/pressure-orb-dashboard.git" -ForegroundColor White
    Write-Host "Then run: git push -u origin main" -ForegroundColor White
} else {
    Write-Host "[OK] Remote: $remote" -ForegroundColor Green
}

# Étape 4: Déployer sur Vercel
Write-Host ""
Write-Host "[4/5] Deploying dashboard to Vercel..." -ForegroundColor Yellow
Set-Location dashboard

try {
    $vercelVersion = vercel --version 2>$null
    if ($vercelVersion) {
        Write-Host "[OK] Vercel CLI installed: $vercelVersion" -ForegroundColor Green
    } else {
        Write-Host "[WARN] Vercel CLI not installed. Installing..." -ForegroundColor Yellow
        npm install -g vercel
    }
} catch {
    Write-Host "[WARN] npm not found. Please install Node.js from https://nodejs.org/" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Deploying to Vercel..." -ForegroundColor Yellow
Write-Host "This will open a browser window for Vercel authentication." -ForegroundColor White
Write-Host ""
Start-Sleep -Seconds 2

# Déploiement Vercel
vercel

Write-Host ""
Write-Host "[5/5] Deployment to production..." -ForegroundColor Yellow
vercel --prod

Set-Location ..

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "DEPLOIEMENT TERMINÉ" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. If Git remote not set, run:" -ForegroundColor White
Write-Host "   git remote add origin https://github.com/YOUR_USERNAME/pressure-orb-dashboard.git" -ForegroundColor Gray
Write-Host "   git push -u origin main" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Dashboard URL: (check Vercel output above)" -ForegroundColor White
Write-Host ""
Write-Host "3. Start backend locally:" -ForegroundColor White
Write-Host "   C:\Python314\python.exe web\app.py --port 8050" -ForegroundColor Gray
Write-Host ""
Write-Host "4. Start Cloudflare tunnel:" -ForegroundColor White
Write-Host "   cloudflared tunnel --url http://127.0.0.1:8050 --no-autoupdate" -ForegroundColor Gray
Write-Host ""
Write-Host "5. Update config.js if tunnel URL changes" -ForegroundColor White
Write-Host ""
