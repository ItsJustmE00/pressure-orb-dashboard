# Script pour configurer GitHub avec votre username
Set-Location c:\Users\moham\Downloads\agency-agents-main\agency-agents-main

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "SETUP GITHUB REMOTE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$username = Read-Host "Entrez votre username GitHub"

Write-Host ""
Write-Host "Configuration du remote..." -ForegroundColor Yellow
git remote add origin "https://github.com/$username/pressure-orb-dashboard.git"

Write-Host ""
Write-Host "Remote configuré: https://github.com/$username/pressure-orb-dashboard.git" -ForegroundColor Green
Write-Host ""
Write-Host "Prochaine étape:" -ForegroundColor Yellow
Write-Host "1. Créez le dépôt sur GitHub: https://github.com/new" -ForegroundColor White
Write-Host "   - Nom: pressure-orb-dashboard" -ForegroundColor Gray
Write-Host "   - Public (pour Vercel gratuit)" -ForegroundColor Gray
Write-Host "   - NE PAS initialiser avec README" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Puis lancez:" -ForegroundColor White
Write-Host "   git push -u origin main" -ForegroundColor Gray
Write-Host ""
