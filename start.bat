@echo off
cd /d "%~dp0"
title StarStream Pro Downloader

echo ========================================================
echo   StarStream Pro - Starting Application...
echo ========================================================
echo.

where python >nul 2>&1
if %errorlevel% equ 0 (
    python run_app.py
    goto end
)

where py >nul 2>&1
if %errorlevel% equ 0 (
    py run_app.py
    goto end
)

echo [ERROR] Python not found in system PATH!
echo Please make sure Python 3 is installed.
echo Download: https://www.python.org/downloads/
echo.
pause
exit /b 1

:end
if %errorlevel% neq 0 (
    echo.
    echo ========================================================
    echo Application exited with code %errorlevel%.
    echo ========================================================
    pause
)
