@echo off
REM ============================================================
REM   DOUBLE-CLICK THIS ONE FILE TO START EVERYTHING.
REM
REM   It opens:
REM     - the dashboard (the web page you type questions into)
REM     - the calling engine (tunnel + voice server)
REM     - your browser at the dashboard
REM
REM   Keep the two black windows open while you make calls.
REM   Close them (or run STOP_APP.bat) when you're done.
REM ============================================================
cd /d "%~dp0"

echo Starting the dashboard...
start "Voice Dashboard - keep open" ".venv\Scripts\python.exe" -m app.dashboard

echo Starting the calling engine (tunnel + voice server)...
start "Voice Engine - keep open" powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_calling.ps1"

echo Waiting a few seconds, then opening the dashboard in your browser...
timeout /t 8 >nul
start "" http://localhost:8000

echo.
echo ============================================================
echo  Everything is starting. Your browser will open the dashboard.
echo  Wait until the "Voice Engine" window shows: Uvicorn running ... 8080
echo  Then in the dashboard: type your question, Save, and click Call.
echo ============================================================
echo  You can close THIS window. Keep the other two open during calls.
timeout /t 6 >nul
