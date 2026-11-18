param([switch]$Once)

$ErrorActionPreference = 'SilentlyContinue'
$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root 'logs'
$logPath = Join-Path $logDir 'watchdog.log'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$terminal = 'C:\Program Files\MetaTrader 5\terminal64.exe'
$data = 'C:\Users\moham\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075'
$startIni = Join-Path $data 'PRESSURE_start.ini'
$python = 'C:\Python314\python.exe'

function Write-WatchdogLog {
    param([string]$Message)
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Add-Content -Path $logPath -Value $line -Encoding UTF8
    Write-Host $line
}

if ((Test-Path $logPath) -and ((Get-Item $logPath).Length -gt 2MB)) {
    Move-Item $logPath "$logPath.1" -Force
}

function Get-NYNow {
    $tz = [System.TimeZoneInfo]::FindSystemTimeZoneById('Eastern Standard Time')
    return [System.TimeZoneInfo]::ConvertTimeFromUtc((Get-Date).ToUniversalTime(), $tz)
}

function Test-MarketHours {
    $ny = Get-NYNow
    if ($ny.DayOfWeek -eq [DayOfWeek]::Saturday -or $ny.DayOfWeek -eq [DayOfWeek]::Sunday) {
        return $false
    }
    $minutes = $ny.Hour * 60 + $ny.Minute
    return ($minutes -ge 570 -and $minutes -lt 1380)   # 09:30 -> 23:00 NY
}

function Test-Terminal {
    return [bool](Get-Process terminal64 -ErrorAction SilentlyContinue)
}

function Start-Terminal {
    if (-not (Test-Path $terminal)) {
        Write-WatchdogLog "ERREUR terminal introuvable: $terminal"
        return $false
    }
    if (-not (Test-Path $startIni)) {
        Write-WatchdogLog "ERREUR config introuvable: $startIni"
        return $false
    }
    Start-Process -FilePath $terminal -ArgumentList "/config:$startIni" | Out-Null
    Write-WatchdogLog 'MT5 absent -> relance avec PRESSURE_start.ini'
    return $true
}

function Test-Backend {
    if (Get-NetTCPConnection -LocalPort 8050 -State Listen -ErrorAction SilentlyContinue) {
        return $true
    }
    $proc = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'web[\\/]app\.py' }
    return [bool]$proc
}

function Start-Backend {
    $out = Join-Path $logDir 'backend.out.log'
    $err = Join-Path $logDir 'backend.err.log'
    Start-Process -FilePath $python -ArgumentList 'web\app.py','--port','8050' `
        -WorkingDirectory $root -RedirectStandardOutput $out -RedirectStandardError $err `
        -WindowStyle Hidden | Out-Null
    Write-WatchdogLog 'Backend absent -> relance sur le port 8050'
}

function Test-EALoaded {
    $logDir = Join-Path $data 'logs'
    $files = Get-ChildItem $logDir -Filter '*.log' -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^\d{8}\.log$' } |
        Sort-Object Name |
        Select-Object -Last 3
    if (-not $files) {
        return $false
    }
    $lines = @()
    foreach ($file in $files) {
        $lines += Get-Content $file.FullName -Tail 1000 -ErrorAction SilentlyContinue
    }
    $lastStart = -1
    $lastLoad = -1
    $lastRemove = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match 'MetaTrader 5 x64 build .* started') { $lastStart = $i }
        if ($lines[$i] -match 'expert ORB_Pressure.*loaded successfully') { $lastLoad = $i }
        if ($lines[$i] -match 'expert ORB_Pressure.*removed') { $lastRemove = $i }
    }
    return ($lastStart -ge 0 -and $lastLoad -gt $lastStart -and $lastLoad -gt $lastRemove)
}

function Invoke-Watchdog {
    $terminalWasRunning = Test-Terminal

    $offhoursFlag = Join-Path $logDir 'offhours_missing.flag'
    if (-not $terminalWasRunning) {
        if (Test-MarketHours) {
            Remove-Item $offhoursFlag -Force -ErrorAction SilentlyContinue
            if (Start-Terminal) {
                Start-Sleep -Seconds 12
                if (-not (Test-Terminal)) {
                    Write-WatchdogLog 'ECHEC relance MT5 -> terminal toujours absent'
                }
            }
        }
        else {
            if (-not (Test-Path $offhoursFlag)) {
                Write-WatchdogLog 'MT5 absent hors session NY -> pas de relance'
                New-Item -ItemType File -Path $offhoursFlag -Force | Out-Null
            }
        }
    }
    else {
        Remove-Item $offhoursFlag -Force -ErrorAction SilentlyContinue
    }

    if (-not (Test-Backend)) {
        Start-Backend
        Start-Sleep -Seconds 6
        if (-not (Test-Backend)) {
            Write-WatchdogLog 'ECHEC relance backend -> port 8050 toujours ferme'
        }
    }

    $tunnel = Get-Process cloudflared -ErrorAction SilentlyContinue
    $tunnelFlag = Join-Path $logDir 'tunnel_missing.flag'
    if (-not $tunnel) {
        if (-not (Test-Path $tunnelFlag)) {
            Write-WatchdogLog 'ATTENTION tunnel cloudflared absent -> URL Vercel a recreer manuellement'
            New-Item -ItemType File -Path $tunnelFlag -Force | Out-Null
        }
    }
    else {
        Remove-Item $tunnelFlag -Force -ErrorAction SilentlyContinue
    }

    if (Test-Terminal) {
        $eaFlag = Join-Path $logDir 'ea_missing.flag'
        if (-not (Test-EALoaded)) {
            $proc = Get-Process terminal64 -ErrorAction SilentlyContinue | Select-Object -First 1
            $uptime = if ($proc) { ((Get-Date) - $proc.StartTime).TotalSeconds } else { 0 }
            if ($uptime -gt 90 -and -not (Test-Path $eaFlag)) {
                Write-WatchdogLog 'ATTENTION EA ORB_Pressure non charge -> verifier le graphique USTECm M15'
                New-Item -ItemType File -Path $eaFlag -Force | Out-Null
            }
        }
        else {
            Remove-Item $eaFlag -Force -ErrorAction SilentlyContinue
        }
    }
}

if ($Once) {
    Invoke-Watchdog
    exit 0
}

while ($true) {
    Invoke-Watchdog
    Start-Sleep -Seconds 60
}
