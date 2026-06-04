@echo off
REM One-shot: sync env + NVMe folders + migrate (if DB set) + doctor + smoke tests

setlocal
set "PROJECT_ROOT=%~dp0..\"
set "WORKSPACE=%PROJECT_ROOT%.."
cd /d "%PROJECT_ROOT%"

echo.
echo === Mahika quick verify ===
echo.

if not exist ".venv\Scripts\python.exe" (
    echo venv missing — running quick_setup first...
    call "%~dp0quick_setup.bat"
    if errorlevel 1 exit /b 1
)

echo [1/5] Sync .env from workspace root...
powershell -ExecutionPolicy Bypass -File "%WORKSPACE%\scripts\sync_env.ps1"
if errorlevel 1 exit /b 1
echo.

echo [2/5] NVMe folder check...
set MAHIKA_SETUP_NONINTERACTIVE=1
.\.venv\Scripts\python.exe -m scripts.setup_nvme_folders
echo.

echo [3/5] Database migrate (skipped if MAHIKA_DB_PASSWORD empty)...
findstr /R /C:"^MAHIKA_DB_PASSWORD=." .env >nul 2>nul
if errorlevel 1 (
    echo   SKIP — fill MAHIKA_DB_* in root .env, sync, re-run
) else (
    .\.venv\Scripts\python.exe -m mahika.db.migrate
    if errorlevel 1 (
        echo   FAIL — check MAHIKA_DB_HOST + password
        exit /b 1
    )
    echo   OK
)
echo.

echo [4/5] Doctor...
.\.venv\Scripts\python.exe -m mahika.cli doctor
set DOCTOR_RC=%ERRORLEVEL%
echo.

echo [5/5] Smoke tests (need DB for full pass)...
findstr /R /C:"^MAHIKA_DB_PASSWORD=." .env >nul 2>nul
if errorlevel 1 (
    echo   SKIP smokes — DB not configured yet
) else (
    .\.venv\Scripts\python.exe -m tests.run_all
)
echo.

if %DOCTOR_RC% neq 0 (
    echo Some doctor checks failed — see hints above.
    exit /b 1
)
echo === Verify complete ===
exit /b 0
