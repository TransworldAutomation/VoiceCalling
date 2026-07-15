@echo off
REM ============================================================
REM  Double-click this file to turn ON calling.
REM  It opens the public tunnel, sets PUBLIC_URL, and starts
REM  the voice server. Keep the window OPEN while making calls.
REM  Close the window to turn calling OFF.
REM ============================================================
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_calling.ps1"
echo.
echo ------------------------------------------------------------
echo  The voice server has stopped. You can close this window.
echo ------------------------------------------------------------
pause
