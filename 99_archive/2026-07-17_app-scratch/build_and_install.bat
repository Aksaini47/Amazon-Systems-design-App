@echo off
echo ============================================
echo  RepairFully Camera App — Setup + Build
echo ============================================
echo.

set FLUTTER=D:\Downloads\flutter_windows_3.41.4-stable\flutter\bin\flutter.bat
set PROJECT=D:\RepairFully Camera App Project\mobile

cd /d "%PROJECT%"

echo [1/4] Initializing Flutter Android platform (generates Gradle files)...
call "%FLUTTER%" create --platforms android --project-name repairfully_camera --org com.repairfully .
if ERRORLEVEL 1 (
    echo.
    echo Flutter create failed. Check errors above.
    pause
    exit /b 1
)

echo.
echo [2/4] Fetching packages...
call "%FLUTTER%" pub get
if ERRORLEVEL 1 (
    echo.
    echo pub get failed.
    pause
    exit /b 1
)

echo.
echo [3/4] Building debug APK...
call "%FLUTTER%" build apk --debug
if ERRORLEVEL 1 (
    echo.
    echo BUILD FAILED. Check errors above.
    pause
    exit /b 1
)

echo.
echo [4/4] Installing on connected Android device...
call "%FLUTTER%" install
if ERRORLEVEL 1 (
    echo.
    echo Install failed. Make sure USB Debugging is ON and phone is unlocked.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  SUCCESS! App installed on your device.
echo ============================================
pause
