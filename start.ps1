# Trimaz PowerShell Launcher
Set-Location -Path $PSScriptRoot

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "            TRIMAZ - 1-MINUTE REEL CUTTER" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[!] Python is not installed or not in PATH." -ForegroundColor Red
    pause
    exit 1
}

Write-Host "[*] Opening browser at http://localhost:5000 ..." -ForegroundColor Green
Start-Process "http://localhost:5000"

Write-Host "[*] Starting Trimaz Server (Press Ctrl+C to stop)..." -ForegroundColor Yellow
python app.py
