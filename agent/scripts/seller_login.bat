@echo off
REM Seller Central login: .env creds + Telegram OTP auto-fill + cookie save

setlocal
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
    echo Run scripts\quick_setup.bat first.
    exit /b 1
)

powershell -ExecutionPolicy Bypass -File "..\scripts\sync_env.ps1"
.\.venv\Scripts\python.exe -m mahika.cli seller-login
exit /b %ERRORLEVEL%
