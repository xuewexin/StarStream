@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title M3U8 Sniffer - Native Host 安装工具

echo ============================================
echo   M3U8 Sniffer - Native Host 安装工具
echo ============================================
echo.

REM 获取当前目录 (native-host/)
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

REM 获取扩展目录 (m3u8-sniffer-extension/)
for %%I in ("%SCRIPT_DIR%") do set "EXT_DIR=%%~dpI"
set "EXT_DIR=%EXT_DIR:~0,-1%"

REM 获取 N_m3u8DL 项目根目录 (扩展目录的上一级)
for %%I in ("%EXT_DIR%") do set "PROJECT_DIR=%%~dpI"
set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

echo  扩展目录 : %EXT_DIR%
echo  项目目录 : %PROJECT_DIR%
echo.

REM ========== 检查 Python ==========
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python。请先安装 Python 3.6 或更高版本。
    echo       下载地址: https://www.python.org/downloads/
    echo       安装时请勾选 "Add Python to PATH"。
    echo.
    pause
    exit /b 1
)
for /f "delims=" %%V in ('python --version 2^>^&1') do set "PY_VERSION=%%V"
echo [OK] Python 已就绪: !PY_VERSION!
echo.

REM ========== 输入扩展 ID ==========
set "EXT_ID="
echo 请在 Chrome 中打开 chrome://extensions/，开启右上角「开发者模式」，
echo 找到 "M3U8 Sniffer" 扩展，点击其 ID 旁的「复制」图标，
echo 或直接在下方粘贴扩展 ID（一长串小写字母，共 32 位）。
echo.
set /p "EXT_ID=请输入扩展 ID: "

REM 移除输入中的空格（扩展 ID 不含空格）
if defined EXT_ID set "EXT_ID=%EXT_ID: =%"

if "%EXT_ID%"=="" (
    echo [错误] 扩展 ID 不能为空，安装中止。
    echo.
    pause
    exit /b 1
)

REM 校验扩展 ID 长度（Chromium 扩展 ID 通常为 32 位，仅作提示）
for /f "delims=" %%L in ('python -c "import sys;print(len(sys.argv[1]))" "%EXT_ID%"') do set "ID_LEN=%%L"
if not "!ID_LEN!"=="32" (
    echo [提示] 扩展 ID 长度不是 32 位（当前 %ID_LEN% 位），请确认复制无误后继续。
    echo        若确认无误可忽略此提示。
)
echo.

REM ========== 生成文件 ==========
set "HOST_PATH=%SCRIPT_DIR%\m3u8-sniffer-host.bat"
set "MANIFEST_PATH=%SCRIPT_DIR%\com.m3u8.sniffer.json"

REM 确认包装脚本存在 (m3u8-sniffer-host.bat)
if not exist "%HOST_PATH%" (
    echo [信息] 正在生成包装脚本: %HOST_PATH%
    echo @echo off> "%HOST_PATH%"
    echo python "%%~dp0m3u8-sniffer-host.py">> "%HOST_PATH%"
) else (
    echo [OK] 包装脚本已存在: %HOST_PATH%
)

REM 生成 Native Host 清单 (JSON)
echo [信息] 正在生成清单: %MANIFEST_PATH%
python -c "import json,sys;m={'name':'com.m3u8.sniffer','description':'M3U8 Sniffer Native Messaging Host','path':sys.argv[1],'type':'stdio','allowed_origins':['chrome-extension://'+sys.argv[2]+'/']};json.dump(m,open(sys.argv[3],'w',encoding='utf-8'),indent=2,ensure_ascii=False)" "%HOST_PATH%" "%EXT_ID%" "%MANIFEST_PATH%"
if errorlevel 1 (
    echo [错误] 生成清单失败，请检查 Python 环境。
    pause
    exit /b 1
)

REM 校验清单 JSON 格式
python -c "import json,sys;json.load(open(sys.argv[1],encoding='utf-8'))" "%MANIFEST_PATH%"
if errorlevel 1 (
    echo [错误] 清单 JSON 格式无效，安装中止。
    pause
    exit /b 1
)
echo [OK] 已生成: %MANIFEST_PATH%

REM ========== 写入注册表 ==========
echo.
echo 正在注册 Native Messaging Host ...
reg add "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.m3u8.sniffer" /ve /t REG_SZ /d "%MANIFEST_PATH%" /f >nul 2>&1
if errorlevel 1 (
    echo [警告] Chrome 注册表写入失败
) else (
    echo [OK] Chrome 注册表: HKCU\Software\Google\Chrome\NativeMessagingHosts\com.m3u8.sniffer
)

reg add "HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.m3u8.sniffer" /ve /t REG_SZ /d "%MANIFEST_PATH%" /f >nul 2>&1
if errorlevel 1 (
    echo [警告] Edge 注册表写入失败
) else (
    echo [OK] Edge 注册表: HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.m3u8.sniffer
)

REM 回读校验
reg query "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.m3u8.sniffer" /ve >nul 2>&1
if errorlevel 1 (
    echo [警告] 未能在注册表中找到 Chrome 注册项，请手动检查。
)

echo.
echo ============================================
echo   安装完成!
echo ============================================
echo.
echo   Native Host : %HOST_PATH%
echo   清单文件    : %MANIFEST_PATH%
echo.
echo   下一步:
echo    1. 打开 chrome://extensions/，点击「重新加载」刷新 M3U8 Sniffer 扩展
echo    2. 打开包含 M3U8 视频的网页
echo    3. 点击浏览器右上角扩展图标，选择要下载的 M3U8 地址
echo.
pause
endlocal
