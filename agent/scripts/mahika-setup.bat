@echo off
REM ───────────────────────────────────────────────────────────────────────
REM  Mahika runner setup — Phase 5 deliverable
REM  Per mahika_capture_specs.md §1.3: any Windows laptop becomes a Mahika
REM  runner instantly when the NVMe is connected. Run this script once
REM  per machine to bootstrap the runner.
REM
REM  Pre-requisites (must be installed system-wide BEFORE running this):
REM    1. Python 3.11 or newer    — https://www.python.org/downloads/
REM    2. Git                     — https://git-scm.com/download/win
REM    3. The 2TB NVMe plugged in at MAHIKA_STORAGE_ROOT (default D:\Mahika)
REM    4. The .env file copied to the agent\ folder (from previous runner
REM       or fresh-generated per scripts/sp_api_registration_checklist.md)
REM
REM  Usage:
REM    1. Open Command Prompt as a normal user (admin not required)
REM    2. cd to the cloned `agent\` folder
REM    3. scripts\mahika-setup.bat
REM
REM  Total time: ~5 minutes after the prerequisites are in place.
REM ───────────────────────────────────────────────────────────────────────

setlocal enabledelayedexpansion
set "PROJECT_ROOT=%~dp0..\"
cd /d "%PROJECT_ROOT%"

echo.
echo === Mahika runner setup ===
echo Project root: %CD%
echo Runner ID:    %COMPUTERNAME%
echo.

REM ─── Verify pre-requisites ─────────────────────────────────────────────
echo [1/7] Verifying pre-requisites...

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: python.exe not found on PATH. Install Python 3.11+ from python.org.
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version') do set PY_VERSION=%%v
echo   Python: !PY_VERSION!

where git >nul 2>nul
if errorlevel 1 (
    echo ERROR: git.exe not found on PATH. Install Git from git-scm.com.
    exit /b 1
)
echo   Git: OK

if not exist ".env" (
    echo ERROR: .env file missing. Copy your runner's .env from a previous machine
    echo        or generate fresh creds per scripts\sp_api_registration_checklist.md.
    exit /b 1
)
echo   .env: present
echo.

REM ─── Create virtualenv ────────────────────────────────────────────────
echo [2/7] Creating Python virtualenv...
if exist ".venv\Scripts\python.exe" (
    echo   .venv already exists, skipping.
) else (
    python -m venv .venv
    if errorlevel 1 exit /b 1
    echo   .venv created.
)
echo.

REM ─── Install Python deps ──────────────────────────────────────────────
echo [3/7] Installing Python dependencies (this can take ~3 minutes)...
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
    "playwright>=1.45,<2.0"
if errorlevel 1 (
    echo ERROR: pip install failed.
    exit /b 1
)
echo   Dependencies installed.
echo.

REM ─── Install Playwright Chromium binary ───────────────────────────────
echo [4/7] Installing Playwright Chromium browser (~150MB, ~1 min)...
.\.venv\Scripts\python.exe -m playwright install chromium
if errorlevel 1 (
    echo ERROR: playwright install failed.
    exit /b 1
)
echo   Chromium installed.
echo.

REM ─── Create NVMe folder hierarchy ─────────────────────────────────────
echo [5/7] Initializing NVMe folder structure...
.\.venv\Scripts\python.exe -m scripts.setup_nvme_folders
if errorlevel 1 (
    echo WARNING: NVMe folder setup encountered an error. Check MAHIKA_STORAGE_ROOT
    echo          in .env and verify the NVMe drive is connected at that path.
)
echo.

REM ─── Verify DB connectivity + apply migrations ────────────────────────
echo [6/7] Applying database migrations against Oracle Postgres...
.\.venv\Scripts\python.exe -m mahika.db.migrate
if errorlevel 1 (
    echo ERROR: DB migration failed. Verify MAHIKA_DB_HOST + MAHIKA_DB_PASSWORD in .env.
    exit /b 1
)
echo.

REM ─── Smoke-test heartbeat ─────────────────────────────────────────────
echo [7/7] Verifying heartbeat + claiming active-runner role...
.\.venv\Scripts\python.exe -c "from mahika.runner.heartbeat import claim_active, am_i_active; ok = claim_active(notes='setup smoke-test'); active = am_i_active(); print('claim_active:', ok); print('am_i_active:', active)"
if errorlevel 1 (
    echo ERROR: heartbeat smoke test failed.
    exit /b 1
)
echo.

echo ===========================================================
echo  Setup complete. This machine is now a Mahika runner.
echo.
echo  Next steps:
echo    1. Boot the daemon:   .\.venv\Scripts\python.exe -m mahika.cli start
echo    2. Check status:      .\.venv\Scripts\python.exe -m mahika.cli status
echo    3. Tail audit log:    .\.venv\Scripts\python.exe -m mahika.cli audit-tail 20
echo.
echo  First-time Seller Central authentication will trigger a headed
echo  browser. Log in there and Mahika will save the cookies for
echo  future runs.
echo ===========================================================
exit /b 0
