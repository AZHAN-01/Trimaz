@echo off
title Trimaz - 1-Min Reel Cutter
color 0B
cd /d "%~dp0"

echo =======================================================
echo             TRIMAZ - 1-MINUTE REEL CUTTER
echo =======================================================
echo.
echo [*] Checking Python environment...
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [!] Python is not found in PATH! Please install Python 3.
    pause
    exit /b 1
)

echo [*] Launching Web Interface...
echo [*] Opening browser at http://localhost:5000 ...
start "" http://localhost:5000

echo [*] Starting Trimaz Server (Press Ctrl+C to stop)...
echo.
python app.py

pause
