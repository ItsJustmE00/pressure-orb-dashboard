param([switch]$Once)

$ErrorActionPreference = 'SilentlyContinue'
$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root 'logs'
$logPath = Join-Path $logDir 'watchdog.log'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$terminal = 'C:\Program Files\MetaTrader 5\terminal64.exe'
$data = 'C:\Users\moham\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075'
$startIni = Join-Path $data 'PRESSURE_start.ini'
$preset = Join-Path $data 'MQL5\Presets\PRESSURE.set'
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

function Get-PresetValue {
    param([string]$Key, $Default)
    if (-not (Test-Path $preset)) {
        return $Default
    }
    $line = Get-Content $preset -Encoding Unicode -ErrorAction SilentlyContinue |
        Where-Object { $_ -match ('^\s*' + [regex]::Escape($Key) + '\s*=') } |
        Select-Object -First 1
    if (-not $line) {
        return $Default
    }
    return ($line -split '=', 2)[1].Trim()
}

function Test-MarketHours {
    $ny = Get-NYNow
    if ($ny.DayOfWeek -eq [DayOfWeek]::Saturday -or $ny.DayOfWeek -eq [DayOfWeek]::Sunday) {
        return $false
    }
    $rangeHour = [int](Get-PresetValue 'InpRangeHourNY' 9)
    $rangeMinute = [int](Get-PresetValue 'InpRangeMinuteNY' 30)
    $closeHour = [int](Get-PresetValue 'InpCloseHourNY' 23)
    $closeMinute = [int](Get-PresetValue 'InpCloseMinuteNY' 0)
    $minutes = $ny.Hour * 60 + $ny.Minute
    $start = $rangeHour * 60 + $rangeMinute
    $end = $closeHour * 60 + $closeMinute
    return ($minutes -ge $start -and $minutes -lt $end)
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
    # Liveness = the Flask process actually listens on 8050.
    $listener = Get-NetTCPConnection -LocalPort 8050 -State Listen -ErrorAction SilentlyContinue
    return [bool]$listener
}

function Test-BackendHealth {
    try {
        $response = Invoke-WebRequest -Uri 'http://127.0.0.1:8050/api/health' `
            -UseBasicParsing -TimeoutSec 8 -ErrorAction Stop
        return ($response.StatusCode -eq 200)
    }
    catch {
        return $false
    }
}

function Start-Backend {
    # Remove a hung/duplicate backend before starting a fresh one.
    $stale = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'web[\\/]app\.py' }
    foreach ($proc in $stale) {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
        Write-WatchdogLog "Backend zombie arrete (PID $($proc.ProcessId))"
    }

    $out = Join-Path $logDir 'backend.out.log'
    $err = Join-Path $logDir 'backend.err.log'
    Start-Process -FilePath $python -ArgumentList 'web\app.py','--port','8050' `
        -WorkingDirectory $root -RedirectStandardOutput $out -RedirectStandardError $err `
        -WindowStyle Hidden | Out-Null
    Write-WatchdogLog 'Backend absent -> relance sur le port 8050'
}

function Test-EALoaded {
    $logDirTerminal = Join-Path $data 'logs'
    $files = Get-ChildItem $logDirTerminal -Filter '*.log' -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^\d{8}\.log$' } |
        Sort-Object Name |
        Select-Object -Last 7
    if (-not $files) {
        return $false
    }
    $lines = @()
    foreach ($file in $files) {
        $lines += Get-Content $file.FullName -Tail 1200 -ErrorAction SilentlyContinue
    }
    $lastStart = -1
    $lastLoad = -1
    $lastRemove = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match 'MetaTrader 5 x64 build .* started') { $lastStart = $i }
        if ($lines[$i] -match 'expert ORB_Pressure.*loaded successfully') { $lastLoad = $i }
        if ($lines[$i] -match 'expert ORB_Pressure.*removed') { $lastRemove = $i }
    }
    if ($lastRemove -gt $lastLoad) {
        return $false
    }
    if ($lastStart -ge 0) {
        return ($lastLoad -gt $lastStart)
    }
    # Terminal started before the scanned window but a load was seen since.
    return ($lastLoad -ge 0)
}

function Test-WatchdogGap {
    $statePath = Join-Path $logDir 'watchdog_last_run.txt'
    $now = (Get-Date).ToUniversalTime()
    if (Test-Path $statePath) {
        try {
            $lastText = (Get-Content $statePath -Raw).Trim()
            if ($lastText) {
                $last = [datetime]::Parse($lastText).ToUniversalTime()
                $gap = ($now - $last).TotalMinutes
                if ($gap -gt 5) {
                    Write-WatchdogLog ('ATTENTION trou de surveillance de {0:N0} min (veille/reveil ?)' -f $gap)
                }
            }
        }
        catch {
        }
    }
    Set-Content -Path $statePath -Value $now.ToString('o') -Encoding UTF8
}

function Enable-TaskStartWhenAvailable {
    param([string]$Name)
    try {
        $task = Get-ScheduledTask -TaskName $Name -ErrorAction Stop
        $settings = $task.Settings
        if (-not $settings.StartWhenAvailable) {
            $settings.StartWhenAvailable = $true
            Set-ScheduledTask -TaskName $Name -Settings $settings | Out-Null
            Write-WatchdogLog "Tache $Name : StartWhenAvailable active"
        }
    }
    catch {
    }
}

function Invoke-Watchdog {
    Test-WatchdogGap
    Enable-TaskStartWhenAvailable 'ORB Watchdog'
    Enable-TaskStartWhenAvailable 'ORB Tunnel Keeper'

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
        Start-Sleep -Seconds 2
        for ($i = 0; $i -lt 20; $i++) {
            if (Test-Backend) { break }
            Start-Sleep -Seconds 1
        }
        if (-not (Test-Backend)) {
            Write-WatchdogLog 'ECHEC relance backend -> port 8050 toujours ferme'
        }
    }
    else {
        $healthFlag = Join-Path $logDir 'backend_health.flag'
        if (-not (Test-BackendHealth)) {
            if (-not (Test-Path $healthFlag)) {
                Write-WatchdogLog 'ATTENTION backend port 8050 ouvert mais /api/health KO'
                New-Item -ItemType File -Path $healthFlag -Force | Out-Null
            }
        }
        else {
            Remove-Item $healthFlag -Force -ErrorAction SilentlyContinue
        }
    }

    $tunnel = Get-Process cloudflared -ErrorAction SilentlyContinue
    $tunnelFlag = Join-Path $logDir 'tunnel_missing.flag'
    if (-not $tunnel) {
        if (-not (Test-Path $tunnelFlag)) {
            Write-WatchdogLog 'Tunnel cloudflared absent -> declenchement ORB Tunnel Keeper'
            New-Item -ItemType File -Path $tunnelFlag -Force | Out-Null
        }
        Start-ScheduledTask -TaskName 'ORB Tunnel Keeper' -ErrorAction SilentlyContinue
    }
    else {
        Remove-Item $tunnelFlag -Force -ErrorAction SilentlyContinue
    }

    if (Test-Terminal) {
        $eaFlag = Join-Path $logDir 'ea_missing.flag'
        $eaBinary = Join-Path $data 'MQL5\Experts\ORB_Pressure.ex5'
        if (-not (Test-Path $eaBinary)) {
            Write-WatchdogLog "ERREUR binaire EA introuvable: $eaBinary"
        }
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
