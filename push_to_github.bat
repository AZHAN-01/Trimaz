@echo off
title Push Trimaz to GitHub
color 0B
cd /d "%~dp0"

echo =======================================================
echo             PUSH TRIMAZ TO GITHUB
echo =======================================================
echo.
echo Please create a new repository on GitHub:
echo https://github.com/new (Name: Trimaz, leave README unchecked)
echo.
set /p REPO_URL="Paste your GitHub repository URL (e.g. https://github.com/your-username/Trimaz.git): "

if "%REPO_URL%"=="" (
    echo [!] No URL provided. Exiting.
    pause
    exit /b 1
)

echo.
echo [*] Setting remote origin...
git remote remove origin >nul 2>&1
git remote add origin %REPO_URL%
git branch -M main

echo [*] Pushing to GitHub...
git push -u origin main

if %ERRORLEVEL% equ 0 (
    echo.
    echo [SUCCESS] Trimaz has been successfully pushed to GitHub!
) else (
    echo.
    echo [!] Push failed. Please check your GitHub credentials or URL.
)

pause
