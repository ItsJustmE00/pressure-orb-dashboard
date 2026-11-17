param(
    [switch]$KeepTemp
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$src = Join-Path $root 'dashboard'
$tmp = Join-Path $env:TEMP ("orb_dashboard_deploy_" + (Get-Date -Format 'yyyyMMdd_HHmmss'))

if (-not (Test-Path (Join-Path $src '.vercel\project.json'))) {
    throw "Lien Vercel absent: dashboard\.vercel\project.json"
}

New-Item -ItemType Directory -Force -Path $tmp | Out-Null
robocopy $src $tmp /E /XD .git /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "Echec copie vers $tmp (robocopy $LASTEXITCODE)" }

Push-Location $tmp
try {
    Write-Host "Deploiement Vercel depuis $tmp..."
    vercel --prod --yes
    if ($LASTEXITCODE -ne 0) { throw "Echec deploiement Vercel (code $LASTEXITCODE)" }
}
finally {
    Pop-Location
}

Write-Host "Deploiement Vercel termine."
if (-not $KeepTemp) {
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
