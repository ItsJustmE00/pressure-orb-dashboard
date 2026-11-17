param(
    [switch]$Check,
    [switch]$Renew,
    [switch]$Status,
    [switch]$NoDeploy
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root 'logs'
$logPath = Join-Path $logDir 'quick_tunnel.log'
$statePath = Join-Path $logDir 'quick_tunnel_state.json'
$lockPath = Join-Path $logDir 'quick_tunnel.lock'
$configJs = Join-Path $root 'dashboard\config.js'
$cf = 'C:\Program Files (x86)\cloudflared\cloudflared.exe'
$vercelDomain = 'orb-dashboard-five.vercel.app'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-TunnelLog {
    param([string]$Message)
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Add-Content -Path $logPath -Value $line -Encoding UTF8
    Write-Host $line
}

if ((Test-Path $logPath) -and ((Get-Item $logPath).Length -gt 2MB)) {
    Move-Item $logPath "$logPath.1" -Force
}

Get-ChildItem $logDir -Filter 'cloudflared_*.log' -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } |
    Remove-Item -Force -ErrorAction SilentlyContinue

function Get-ConfigUrl {
    $content = [System.IO.File]::ReadAllText($configJs, [System.Text.Encoding]::UTF8)
    if ($content -match '(?m)^window\.ORB_API_BASE\s*=\s*"(https://[^"]+)"\s*;') {
        return $matches[1].TrimEnd('/')
    }
    return $null
}

function Test-TunnelUrl {
    param([string]$Url)
    if (-not $Url) { return $false }
    try {
        $health = Invoke-RestMethod -Uri "$Url/api/health" -TimeoutSec 15
        return ($health.ok -eq $true)
    }
    catch {
        return $false
    }
}

function Wait-TunnelHealthy {
    param([string]$Url, [int]$Attempts = 40, [int]$DelaySec = 4)
    for ($i = 0; $i -lt $Attempts; $i++) {
        if (Test-TunnelUrl $Url) { return $true }
        Start-Sleep -Seconds $DelaySec
    }
    return $false
}

function Get-QuickProcesses {
    return Get-CimInstance Win32_Process -Filter "Name='cloudflared.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match '--url\s+http://127\.0\.0\.1:8050' }
}

function Start-Candidate {
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $out = Join-Path $logDir "cloudflared_$stamp.out.log"
    $err = Join-Path $logDir "cloudflared_$stamp.err.log"
    $proc = Start-Process -FilePath $cf `
        -ArgumentList 'tunnel', '--url', 'http://127.0.0.1:8050', '--no-autoupdate' `
        -RedirectStandardOutput $out -RedirectStandardError $err `
        -WindowStyle Hidden -PassThru

    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Seconds 2
        $text = ''
        if (Test-Path $out) { $text += (Get-Content $out -Raw -ErrorAction SilentlyContinue) }
        if (Test-Path $err) { $text += (Get-Content $err -Raw -ErrorAction SilentlyContinue) }
        if ($text -match 'https://[a-z0-9-]+\.trycloudflare\.com') {
            return [pscustomobject]@{
                Url = $matches[0]
                Pid = $proc.Id
                Out = $out
                Err = $err
            }
        }
        if ($proc.HasExited) { break }
    }

    $tail = ''
    if (Test-Path $err) { $tail = (Get-Content $err -Tail 20 -ErrorAction SilentlyContinue) -join "`n" }
    throw "URL trycloudflare introuvable. Dernieres lignes:`n$tail"
}

function Update-ConfigJs {
    param([string]$Url)
    $content = [System.IO.File]::ReadAllText($configJs, [System.Text.Encoding]::UTF8)
    $newLine = 'window.ORB_API_BASE = "' + $Url + '";'
    $updated = [regex]::Replace($content, '(?m)^window\.ORB_API_BASE\s*=\s*"[^"]*";', $newLine, 1)
    [System.IO.File]::WriteAllText($configJs, $updated, (New-Object System.Text.UTF8Encoding($false)))
}

function Test-VercelHasUrl {
    param([string]$Url)
    for ($i = 0; $i -lt 12; $i++) {
        $cfg = curl.exe -s --max-time 30 "https://$vercelDomain/config.js?ts=$(Get-Date -Format HHmmssfff)"
        if ($cfg -match [regex]::Escape($Url)) { return $true }
        Start-Sleep -Seconds 5
    }
    return $false
}

function Deploy-Dashboard {
    & (Join-Path $PSScriptRoot 'deploy_dashboard.ps1')
}

function Ensure-Vercel {
    param([string]$Url)
    if ($NoDeploy) { return $true }
    if (Test-VercelHasUrl $Url) { return $true }
    Write-TunnelLog "Deploiement Vercel pour $Url..."
    Deploy-Dashboard
    return (Test-VercelHasUrl $Url)
}

function Stop-OldTunnels {
    param([int]$KeepPid)
    $procs = Get-QuickProcesses
    foreach ($p in $procs) {
        if ($KeepPid -and $p.ProcessId -eq $KeepPid) { continue }
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    if ($procs) { Start-Sleep -Seconds 2 }
}

function Save-State {
    param($State)
    $State | ConvertTo-Json | Set-Content -Path $statePath -Encoding UTF8
}

function Read-State {
    if (-not (Test-Path $statePath)) { return $null }
    try {
        return Get-Content $statePath -Raw | ConvertFrom-Json
    }
    catch {
        return $null
    }
}

function Save-Git {
    param([string]$Url)
    $dash = Join-Path $root 'dashboard'
    git -C $dash add config.js
    $staged = git -C $dash diff --cached --name-only
    if ($staged) {
        git -C $dash commit -m "config: quick tunnel $Url" | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-TunnelLog "ATTENTION commit dashboard echoue" }
        git -C $dash push origin main | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-TunnelLog "ATTENTION push dashboard echoue" }

        git -C $root add dashboard
        $outerStaged = git -C $root diff --cached --name-only
        if ($outerStaged) {
            git -C $root commit -m "dashboard: pointeur quick tunnel $Url" | Out-Null
            if ($LASTEXITCODE -ne 0) { Write-TunnelLog "ATTENTION commit outer echoue" }
            git -C $root push origin main | Out-Null
            if ($LASTEXITCODE -ne 0) { Write-TunnelLog "ATTENTION push outer echoue" }
        }
    }
}

function Finalize-Candidate {
    param($State, [string]$Url, [int]$CandidatePid)
    Update-ConfigJs $Url
    if (-not (Ensure-Vercel $Url)) {
        throw "Vercel ne sert pas encore $Url"
    }
    Stop-OldTunnels -KeepPid $CandidatePid
    $State.current = $Url
    $State.candidate = $null
    $State.candidate_pid = $null
    Save-State $State
    Save-Git $Url
    Write-TunnelLog "Tunnel actif: $Url"
}

function Invoke-Check {
    $state = Read-State
    if (-not $state) {
        $state = [pscustomobject]@{
            current = (Get-ConfigUrl)
            candidate = $null
            candidate_pid = $null
        }
    }

    $current = Get-ConfigUrl
    if ($current -and $state.current -ne $current) {
        $state.current = $current
        Save-State $state
    }

    if ($state.candidate) {
        $candidate = [string]$state.candidate
        $candidatePid = [int]$state.candidate_pid
        if (Test-TunnelUrl $candidate) {
            Write-TunnelLog "Candidat sain detecte: $candidate -> finalisation"
            Finalize-Candidate $state $candidate $candidatePid
            return
        }
        Write-TunnelLog "Candidat KO: $candidate -> abandon"
        if ($candidatePid -and (Get-Process -Id $candidatePid -ErrorAction SilentlyContinue)) {
            Stop-Process -Id $candidatePid -Force -ErrorAction SilentlyContinue
        }
        $state.candidate = $null
        $state.candidate_pid = $null
        Save-State $state
    }

    $active = Get-ConfigUrl
    if (Test-TunnelUrl $active) {
        if (Ensure-Vercel $active) {
            if ($Status) { Write-Host "OK tunnel=$active vercel=OK" }
            else { Write-TunnelLog "OK tunnel=$active" }
            return
        }
        throw "Tunnel sain mais Vercel ne sert pas $active"
    }

    Write-TunnelLog "Tunnel actif KO: $active -> creation d'un candidat"
    $new = Start-Candidate
    $state.candidate = $new.Url
    $state.candidate_pid = $new.Pid
    Save-State $state

    if (-not (Wait-TunnelHealthy $new.Url)) {
        throw "Nouveau candidat injoignable apres attente: $($new.Url)"
    }
    Finalize-Candidate $state $new.Url $new.Pid
}

function Invoke-ForcedRenew {
    $state = Read-State
    if (-not $state) {
        $state = [pscustomobject]@{
            current = (Get-ConfigUrl)
            candidate = $null
            candidate_pid = $null
        }
    }

    if ($state.candidate -and (Test-TunnelUrl ([string]$state.candidate))) {
        $candidate = [string]$state.candidate
        $candidatePid = [int]$state.candidate_pid
        Write-TunnelLog "Finalisation du candidat existant: $candidate"
        Finalize-Candidate $state $candidate $candidatePid
        return
    }

    if ($state.candidate) {
        $stalePid = [int]$state.candidate_pid
        Write-TunnelLog "Ancien candidat KO: $($state.candidate) -> arret"
        if ($stalePid -and (Get-Process -Id $stalePid -ErrorAction SilentlyContinue)) {
            Stop-Process -Id $stalePid -Force -ErrorAction SilentlyContinue
        }
        $state.candidate = $null
        $state.candidate_pid = $null
        Save-State $state
    }

    Write-TunnelLog 'Renouvellement force du quick tunnel...'
    $new = Start-Candidate
    $state.candidate = $new.Url
    $state.candidate_pid = $new.Pid
    Save-State $state
    if (-not (Wait-TunnelHealthy $new.Url)) {
        throw "Nouveau candidat injoignable apres attente: $($new.Url)"
    }
    Finalize-Candidate $state $new.Url $new.Pid
}

if ($Status) {
    $url = Get-ConfigUrl
    $healthy = Test-TunnelUrl $url
    $vercel = if ($url -and -not $NoDeploy) { Test-VercelHasUrl $url } else { $false }
    $quick = Get-QuickProcesses
    $state = Read-State
    "config_url=$url"
    "tunnel_ok=$healthy"
    "vercel_ok=$vercel"
    "quick_tunnel_processes=$(@($quick).Count)"
    if ($state -and $state.candidate) { "candidate=$($state.candidate) candidate_pid=$($state.candidate_pid)" }
    exit 0
}

if (Test-Path $lockPath) {
    $age = (Get-Date) - (Get-Item $lockPath).LastWriteTime
    if ($age.TotalMinutes -lt 15) {
        Write-TunnelLog 'Verrou actif -> sortie'
        exit 0
    }
    Remove-Item $lockPath -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType File -Path $lockPath -Force | Out-Null

try {
    if ($Renew) {
        Invoke-ForcedRenew
    }
    else {
        Invoke-Check
    }
}
catch {
    Write-TunnelLog "ERREUR: $($_.Exception.Message)"
    exit 1
}
finally {
    Remove-Item $lockPath -Force -ErrorAction SilentlyContinue
}
