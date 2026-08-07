param([switch]$Install)

# Builds the demo-flavor APK for handing to a prospect. Deliberately
# separate from ship.ps1 (which is Shorebird-centric) — the demo never
# receives OTA patches, it's a static handout APK, so it needs none of
# Shorebird's release/patch machinery.
#
# Prereq: app\android\app\src\demo\google-services.json must exist first
# (see app\android\app\src\demo\README.md for the Firebase console steps —
# this script will fail loudly at the Gradle step if it's missing).

$ErrorActionPreference = 'Stop'

$FlutterBat = if ($env:RF_FLUTTER_BAT) { $env:RF_FLUTTER_BAT } else { 'C:\Projects\apps\flutter_sdk\bin\flutter.bat' }
$AppDir = Split-Path -Parent $PSScriptRoot

$demoConfig = Join-Path $AppDir 'android\app\src\demo\google-services.json'
if (-not (Test-Path $demoConfig)) {
    Write-Host "Missing $demoConfig" -ForegroundColor Red
    Write-Host "See app\android\app\src\demo\README.md for the Firebase console steps." -ForegroundColor Yellow
    exit 1
}

Push-Location $AppDir
try {
    # No --no-tree-shake-icons here on purpose: that flag exists only to
    # keep Shorebird patches from being rejected as asset diffs. The demo
    # never receives Shorebird patches, so it gets normal (smaller) icon
    # tree-shaking.
    & $FlutterBat build apk --flavor demo -t lib/main_demo.dart --release
    if ($LASTEXITCODE -ne 0) { throw "flutter build apk failed (exit $LASTEXITCODE)" }

    $apk = Get-ChildItem "$AppDir\build\app\outputs\flutter-apk" -Filter 'app-demo-release.apk' -ErrorAction Stop |
        Select-Object -First 1
    Write-Host "Demo APK: $($apk.FullName)" -ForegroundColor Green

    if ($Install) {
        $adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
        if (-not (Test-Path $adb)) { throw "adb not found at $adb" }
        & $adb install -r $apk.FullName
    }
} finally {
    Pop-Location
}
