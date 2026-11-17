param(
    [Parameter(Mandatory = $true)][string]$Hostname,
    [string]$TunnelName = 'orb-live',
    [switch]$SkipDeploy
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$cf = 'C:\Program Files (x86)\cloudflared\cloudflared.exe'
$cert = Join-Path $env:USERPROFILE '.cloudflared\cert.pem'
$configPath = Join-Path $env:USERPROFILE '.cloudflared\config.yml'

if (-not (Test-Path $cf)) { throw "cloudflared introuvable: $cf" }
if (-not (Test-Path $cert)) { throw "cloudflared non authentifie: $cert absent. Lance 'cloudflared tunnel login'." }
if ($Hostname -notmatch '^[a-zA-Z0-9.-]+$') { throw "Hostname invalide: $Hostname" }

function Get-TunnelByName([string]$name) {
    $json = & $cf tunnel list --output json 2>$null
    if (-not $json) { return $null }
    $tunnels = $json | ConvertFrom-Json
    return ($tunnels | Where-Object { $_.name -eq $name } | Select-Object -First 1)
}

$tunnel = Get-TunnelByName $TunnelName
if (-not $tunnel) {
    Write-Host "Creation du tunnel $TunnelName..."
    & $cf tunnel create $TunnelName
    if ($LASTEXITCODE -ne 0) { throw "Echec creation tunnel $TunnelName" }
    $tunnel = Get-TunnelByName $TunnelName
}
if (-not $tunnel) { throw "Tunnel $TunnelName introuvable apres creation" }

$uuid = $tunnel.id
if (-not $uuid) { $uuid = $tunnel.uuid }
Write-Host "Tunnel $TunnelName -> $uuid"

$cred = Join-Path $env:USERPROFILE ".cloudflared\$uuid.json"
if (-not (Test-Path $cred)) { throw "Credentials introuvables: $cred" }

$config = @"
tunnel: $uuid
credentials-file: $($cred -replace '\\', '/')
ingress:
  - hostname: $Hostname
    service: http://127.0.0.1:8050
  - service: http_status:404
"@
[System.IO.File]::WriteAllText($configPath, $config, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "Config ecrite: $configPath"

& $cf tunnel route dns $TunnelName $Hostname --overwrite-dns
if ($LASTEXITCODE -ne 0) { throw "Echec route DNS pour $Hostname" }

$configJs = Join-Path $root 'dashboard\config.js'
$content = Get-Content $configJs -Raw
$newLine = 'window.ORB_API_BASE = "https://' + $Hostname + '";'
$content = [regex]::Replace($content, 'window\.ORB_API_BASE\s*=\s*"[^"]*";', $newLine, 1)
[System.IO.File]::WriteAllText($configJs, $content, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "dashboard/config.js -> $newLine"

$old = Get-Process cloudflared -ErrorAction SilentlyContinue
if ($old) {
    Write-Host "Arret du tunnel existant (PID $($old.Id))..."
    $old | Stop-Process -Force
    Start-Sleep -Seconds 2
}

Start-Process -FilePath $cf -ArgumentList 'tunnel', 'run', $TunnelName -WindowStyle Hidden
Write-Host "Tunnel nomme demarre."

$ok = $false
for ($i = 1; $i -le 12; $i++) {
    Start-Sleep -Seconds 5
    try {
        $health = Invoke-RestMethod -Uri "https://$Hostname/api/health" -TimeoutSec 15
        if ($health.ok -eq $true) {
            $ok = $true
            break
        }
    }
    catch {
        Write-Host "Attente DNS/tunnel ($i/12)..."
    }
}
if (-not $ok) { throw "Le tunnel nomme ne repond pas encore sur https://$Hostname/api/health" }
Write-Host "Tunnel nomme operationnel: https://$Hostname"

# Commit dashboard/config.js et pointeur de submodule
$dashChanged = git -C (Join-Path $root 'dashboard') status --porcelain
if ($dashChanged) {
    git -C (Join-Path $root 'dashboard') add config.js
    git -C (Join-Path $root 'dashboard') commit -m "config: tunnel nomme $Hostname"
    git -C (Join-Path $root 'dashboard') push origin main
    git -C $root add dashboard
    git -C $root commit -m "dashboard: pointeur vers tunnel nomme $Hostname"
    git -C $root push origin main
}

if (-not $SkipDeploy) {
    & (Join-Path $PSScriptRoot 'deploy_dashboard.ps1')
}
