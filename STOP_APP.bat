@echo off
REM Double-click to stop the voice app (dashboard + engine + tunnel).
echo Stopping the voice app...
powershell -NoProfile -Command "Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue; Get-NetTCPConnection -LocalPort 8080,8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
echo Done. Everything is stopped. You can close this window.
timeout /t 3 >nul
