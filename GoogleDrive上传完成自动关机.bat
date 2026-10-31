@echo off
chcp 65001 >nul
title Google Drive 上传完成自动关机助手
set "SCRIPT_PATH=%~dp0auto_shutdown_when_upload_done.ps1"
if not exist "%SCRIPT_PATH%" (
    set "SCRIPT_PATH=E:\N_m3u8DL-CLI_v3.0.2_with_ffmpeg_and_SimpleG\auto_shutdown_when_upload_done.ps1"
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_PATH%"
if %errorlevel% neq 0 (
    echo.
    echo 脚本执行完毕或已被用户退出。
    pause
)
