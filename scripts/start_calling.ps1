# =============================================================================
#  START CALLING  -  run this from the project folder:
#
#      .\scripts\start_calling.ps1     (or double-click start_calling.bat)
#
#  It does 3 things for you:
#    1. Opens a public tunnel (cloudflared) so Twilio can reach your PC
#    2. Writes that public URL into your .env automatically
#    3. Starts the voice server (this window then shows live call logs)
#
#  Keep this window OPEN during calls. Press Ctrl+C to stop everything.
#  Then, in a SECOND window, place a call from the dashboard Call button,
#  or run:  python -m app.caller --phone +91XXXXXXXXXX
# =============================================================================

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

$cloudflared = Join-Path $root "cloudflared.exe"
$venvPy      = Join-Path $root ".venv312\Scripts\python.exe"
$envPath     = Join-Path $root ".env"
$log         = Join-Path $root "cloudflared.log"

if (-not (Test-Path $cloudflared)) { Write-Host "cloudflared.exe not found." -ForegroundColor Red; exit 1 }
if (-not (Test-Path $venvPy))      { Write-Host ".venv312 not found - the voice env is not set up." -ForegroundColor Red; exit 1 }

# --- 0. Clean up anything left over from a previous run ---------------------
# (a leftover tunnel locks the log file; a leftover server holds port 8080)
Write-Host "Cleaning up any previous session..." -ForegroundColor Cyan
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
$busy = Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue
if ($busy) {
    $busy.OwningProcess | Select-Object -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
}
Start-Sleep -Milliseconds 700
Remove-Item $log, "$log.out" -Force -ErrorAction SilentlyContinue

# --- 1. Start the tunnel and capture its public URL -------------------------
Write-Host "Opening public tunnel..." -ForegroundColor Cyan
$tunnel = Start-Process -FilePath $cloudflared `
    -ArgumentList "tunnel","--url","http://localhost:8080" `
    -RedirectStandardError $log -RedirectStandardOutput "$log.out" -PassThru -WindowStyle Hidden

$publicUrl = $null
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    foreach ($f in @($log, "$log.out")) {
        if (Test-Path $f) {
            $m = Select-String -Path $f -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($m) { $publicUrl = $m.Matches[0].Value; break }
        }
    }
    if ($publicUrl) { break }
}

if (-not $publicUrl) {
    Write-Host "Could not read the tunnel URL. See cloudflared.log" -ForegroundColor Red
    if ($tunnel -and -not $tunnel.HasExited) { Stop-Process -Id $tunnel.Id -Force }
    exit 1
}
Write-Host "Public URL: $publicUrl" -ForegroundColor Green

# --- 2. Write PUBLIC_URL into .env ------------------------------------------
$lines = Get-Content $envPath
if ($lines -match '^PUBLIC_URL=') {
    $lines = $lines -replace '^PUBLIC_URL=.*', ("PUBLIC_URL=" + $publicUrl)
} else {
    $lines += ("PUBLIC_URL=" + $publicUrl)
}
Set-Content -Path $envPath -Value $lines -Encoding utf8
Write-Host "Saved PUBLIC_URL to .env" -ForegroundColor Green

# --- 3. Start the voice server (foreground; shows call logs) -----------------
Write-Host ""
Write-Host "Starting voice server. Keep this window open." -ForegroundColor Cyan
Write-Host "Now go to the dashboard (http://localhost:8000), refresh, and click Call." -ForegroundColor Yellow
Write-Host ""

# Make Python print UTF-8 (Hindi text) without crashing. The server writes its
# own detailed log to voice_server.log (configured inside app/server.py).
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"
$ErrorActionPreference = "Continue"   # uvicorn logs to stderr; don't treat that as fatal
try {
    & $venvPy -m app.server
} finally {
    Write-Host ""
    Write-Host "Stopping tunnel..." -ForegroundColor Cyan
    if ($tunnel -and -not $tunnel.HasExited) { Stop-Process -Id $tunnel.Id -Force }
}
