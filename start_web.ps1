param(
    [int]$Port = 8050,
    [switch]$Open
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = "C:\Python314\python.exe"
$out = Join-Path $root "web\server.out.log"
$err = Join-Path $root "web\server.err.log"

$existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    Write-Output "Le dashboard tourne déjà sur http://127.0.0.1:$Port"
    if ($Open) { Start-Process "http://127.0.0.1:$Port" }
    exit
}

$process = Start-Process -FilePath $python -ArgumentList "web\app.py", "--port", $Port -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
Start-Sleep -Seconds 2

Write-Output "Dashboard ORB : http://127.0.0.1:$Port"
Write-Output "PID : $($process.Id)"
Write-Output "Logs : $out"
if ($Open) {
    Start-Process "http://127.0.0.1:$Port"
}
