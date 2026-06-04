@echo off
REM Mahika quick setup — venv + deps + Chromium (NO database required)
REM Run after filling workspace root .env, then: powershell -File ..\..\scripts\sync_env.ps1

setlocal
set "PROJECT_ROOT=%~dp0..\"
cd /d "%PROJECT_ROOT%"

echo.
echo === Mahika quick setup (no DB) ===
echo.

if not exist ".env" (
    echo ERROR: agent\.env missing. Run from workspace root:
    echo   powershell -File scripts\sync_env.ps1
    exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python 3.11+ not on PATH.
    exit /b 1
)

echo [1/4] Virtualenv...
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
)
echo   OK

echo [2/4] Python packages (~3 min)...
.\.venv\Scripts\python.exe -m pip install --quiet --upgrade pip
.\.venv\Scripts\python.exe -m pip install --quiet --no-deps -e .
.\.venv\Scripts\python.exe -m pip install --quiet ^
    "psycopg[binary]>=3.2,<4.0" ^
    "sqlalchemy>=2.0,<3.0" ^
    "pydantic>=2.0,<3.0" ^
    "pydantic-settings>=2.0,<3.0" ^
    "python-dotenv>=1.0,<2.0" ^
    "structlog>=24.0,<25.0" ^
    "Pillow>=10.0,<12.0" ^
    "numpy>=1.26,<3.0" ^
    "opencv-python-headless>=4.10,<5.0" ^
    "scikit-image>=0.24,<1.0" ^
    "pytesseract>=0.3.13,<1.0" ^
    "apscheduler>=3.10,<4.0" ^
    "python-telegram-bot>=21.0,<22.0" ^
    "tenacity>=8.2,<9.0" ^
    "httpx>=0.27,<1.0" ^
    "playwright>=1.45,<2.0" ^
    "fastapi>=0.115,<1.0" ^
    "uvicorn>=0.30,<1.0" ^
    "jinja2>=3.1,<4.0" ^
    "itsdangerous>=2.0,<3.0" ^
    "python-multipart>=0.0.9" ^
    "python-amazon-sp-api>=1.7,<2.0"
if errorlevel 1 exit /b 1
echo   OK

echo [3/4] Playwright Chromium...
.\.venv\Scripts\python.exe -m playwright install chromium
if errorlevel 1 exit /b 1
echo   OK

echo [4/4] Storage folders...
set MAHIKA_SETUP_NONINTERACTIVE=1
.\.venv\Scripts\python.exe -m scripts.setup_nvme_folders
echo.

echo === Quick setup done ===
echo.
echo Sir ab root .env mein DB + SP-API + Telegram bharo, phir:
echo   scripts\quick_verify.bat
echo.
exit /b 0
