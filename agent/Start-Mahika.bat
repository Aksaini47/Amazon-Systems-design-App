@echo off
REM Start Mahika scheduler in background (shadow mode by default)

setlocal
set "AGENT=%~dp0"
cd /d "%AGENT%"

if not exist ".venv\Scripts\python.exe" (
    echo Run scripts\quick_setup.bat first.
    pause
    exit /b 1
)

for /f "usebackq tokens=1,* delims==" %%A in (`findstr /R "^MAHIKA_STORAGE_ROOT=" .env 2^>nul`) do set "STORAGE=%%B"
if "%STORAGE%"=="" set "STORAGE=C:/Projects/Amazon Systems Design/data/mahika"
set "LOGDIR=%STORAGE%\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

set "LOGFILE=%LOGDIR%\daemon.log"
echo Starting Mahika daemon — log: %LOGFILE%
echo Stop: Task Manager ^> python.exe, or close the hidden window.

start "Mahika" /MIN cmd /c "cd /d "%AGENT%" && .venv\Scripts\python.exe -m mahika.cli start >> "%LOGFILE%" 2>&1"

echo Mahika started in background.
timeout /t 3 >nul
