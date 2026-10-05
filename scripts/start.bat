@echo off
setlocal
set "PYTHONDONTWRITEBYTECODE=1"
title BJGBOT Launcher
for %%I in ("%~dp0..") do set "PROJECT_DIR=%%~fI"
cd /d "%PROJECT_DIR%"

if /i "%~1"=="--prepare-only" goto prepare_only

if not exist "config\bot_settings.json" (
    echo ERROR: config\bot_settings.json was not found.
    pause
    exit /b 1
)
for /f "delims=" %%P in ('powershell.exe -NoProfile -Command "(Get-Content -LiteralPath config\bot_settings.json -Raw | ConvertFrom-Json).bot.port"') do set "BOT_BACKEND_PORT=%%P"
for /f "delims=" %%P in ('powershell.exe -NoProfile -Command "(Get-Content -LiteralPath config\bot_settings.json -Raw | ConvertFrom-Json).napcat.webui_port"') do set "NAPCAT_WEBUI_PORT=%%P"
for /f "delims=" %%P in ('powershell.exe -NoProfile -Command "(Get-Content -LiteralPath config\bot_settings.json -Raw | ConvertFrom-Json).napcat.windows_launcher"') do set "NAPCAT_LAUNCHER=%%P"
if not defined BOT_BACKEND_PORT exit /b 1
if not exist "%NAPCAT_LAUNCHER%" (
    echo ERROR: NapCat launcher was not found.
    pause
    exit /b 1
)
set "BOT_BACKEND_RUNNING="
call :port_open %BOT_BACKEND_PORT%
if not errorlevel 1 set "BOT_BACKEND_RUNNING=1"
if not defined BOT_BACKEND_RUNNING (
    call :prepare_environment
    if errorlevel 1 (
        pause
        exit /b 1
    )
)

call :port_open %NAPCAT_WEBUI_PORT%
if errorlevel 1 (
    echo Starting NapCat. Complete QQ login in the NapCat window if requested.
    for %%F in ("%NAPCAT_LAUNCHER%") do start "NapCat" /D "%%~dpF" cmd.exe /c "%%~nxF"
) else (
    echo NapCat WebUI is already running. Skipping NapCat startup.
)

if defined BOT_BACKEND_RUNNING (
    echo BJGBOT is already running on port %BOT_BACKEND_PORT%. Skipping backend startup.
    pause
    exit /b 0
)

echo Starting BJGBOT using config\bot_settings.json
echo Keep this window and the NapCat window open while using the bot.
"%PROJECT_DIR%\.venv\Scripts\python.exe" -u -m src.main
pause
exit /b

:port_open
powershell.exe -NoProfile -Command "$botSocket = New-Object System.Net.Sockets.TcpClient; try { $botConnect = $botSocket.ConnectAsync('127.0.0.1', %1); if ($botConnect.Wait(1000) -and $botSocket.Connected) { exit 0 }; exit 1 } catch { exit 1 } finally { $botSocket.Dispose() }"
exit /b %errorlevel%

:prepare_only
call :prepare_environment
exit /b %errorlevel%

:prepare_environment
if not exist "%PROJECT_DIR%\requirements.txt" (
    echo ERROR: requirements.txt was not found.
    exit /b 1
)
if not exist "%PROJECT_DIR%\.venv\Scripts\python.exe" (
    call :create_venv
    if errorlevel 1 exit /b 1
)
"%PROJECT_DIR%\.venv\Scripts\python.exe" -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
if errorlevel 1 (
    echo ERROR: The existing .venv is broken or uses Python older than 3.10.
    echo Move the old .venv aside, install Python 3.10 or later, and retry.
    exit /b 1
)
if not exist "%PROJECT_DIR%\.venv\.bjgbot-requirements" goto install_dependencies
fc /b "%PROJECT_DIR%\requirements.txt" "%PROJECT_DIR%\.venv\.bjgbot-requirements" >nul 2>&1
if errorlevel 1 goto install_dependencies
"%PROJECT_DIR%\.venv\Scripts\python.exe" -c "import flask, requests, matplotlib, PIL, fontTools, boto3" >nul 2>&1
if errorlevel 1 goto install_dependencies
echo Python environment and dependencies are ready.
exit /b 0

:install_dependencies
echo Installing BJGBOT dependencies. An internet connection is required.
"%PROJECT_DIR%\.venv\Scripts\python.exe" -m pip --version >nul 2>&1
if errorlevel 1 (
    "%PROJECT_DIR%\.venv\Scripts\python.exe" -m ensurepip --upgrade
    if errorlevel 1 exit /b 1
)
"%PROJECT_DIR%\.venv\Scripts\python.exe" -m pip install -r "%PROJECT_DIR%\requirements.txt"
if errorlevel 1 (
    echo ERROR: Dependency installation failed. Check the error above and retry.
    exit /b 1
)
"%PROJECT_DIR%\.venv\Scripts\python.exe" -c "import flask, requests, matplotlib, PIL, fontTools, boto3"
if errorlevel 1 exit /b 1
copy /y "%PROJECT_DIR%\requirements.txt" "%PROJECT_DIR%\.venv\.bjgbot-requirements" >nul
exit /b %errorlevel%

:create_venv
echo Creating the Python virtual environment...
if defined PYTHON_BIN goto create_with_custom_python
py -3.12 -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
if not errorlevel 1 (
    py -3.12 -m venv "%PROJECT_DIR%\.venv"
    exit /b
)
py -3 -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
if not errorlevel 1 (
    py -3 -m venv "%PROJECT_DIR%\.venv"
    exit /b
)
python -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
if not errorlevel 1 (
    python -m venv "%PROJECT_DIR%\.venv"
    exit /b
)
echo ERROR: Install Python 3.10 or later, or set PYTHON_BIN to your python.exe path.
exit /b 1

:create_with_custom_python
"%PYTHON_BIN%" -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
if errorlevel 1 (
    echo ERROR: PYTHON_BIN must point to a working Python 3.10 or later executable.
    exit /b 1
)
"%PYTHON_BIN%" -m venv "%PROJECT_DIR%\.venv"
exit /b %errorlevel%
