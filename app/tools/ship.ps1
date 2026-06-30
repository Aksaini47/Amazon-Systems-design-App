#requires -Version 5.1
<#
.SYNOPSIS
  RF Logger -> Shorebird ship automation. Ek hi command for "fixes".

.DESCRIPTION
  Patch vs release ka decision automatic leta hai aur Shorebird se ship karta
  hai, ek stable icon-font strategy ke saath taaki patches dobara silently
  fail na ho.

  WHY --no-tree-shake-icons EVERYWHERE (permanent fix):
    Flutter MaterialIcons-Regular.otf ko tree-shake karke sirf wahi icons
    rakhta hai jo Dart code use karta hai. Agar patch ka icon-set release se
    alag hua, to font asset alag ban jaata hai -> Shorebird use reject kar deta
    hai (UnpatchableChangeException / asset diff) aur patch phone tak kabhi
    nahi pohanchta. FULL font ko release AUR patch dono me force karne se yeh
    drift hamesha ke liye khatam ho jaata hai.

  GOLDEN RULE:
    Patch tabhi apply hota hai jab phone par install RELEASE version EXACTLY
    patch ke --release-version se match kare. Isse kabhi guess mat karo.

.PARAMETER Mode
  patch   : OTA Dart-only fix current/active release line ko.
  release : +build bump, fresh Shorebird release APK (full reinstall chahiye).
  auto    : git changes dekho; native/asset/dep change -> release, warna patch.

.PARAMETER ReleaseVersion
  Patch target override (e.g. 2.0.0+7). Default: newest active release.

.PARAMETER DryRun
  Build/validate karega par upload NAHI karega (pipeline test ke liye safe).

.PARAMETER Changelog
  Optional "what's new" text. UpdateService.latestChangelog ko
  <release>:<patch> marker ke saath set karta hai aur flutter analyze se verify.

.PARAMETER AllowAssetDiffs
  Escape hatch: legacy release (jo --no-tree-shake-icons ke bina bana tha) ko
  patch karte waqt asset diff allow karna ho to. Normally zaroorat nahi.

.EXAMPLE
  ./tools/ship.ps1 -Mode patch
.EXAMPLE
  ./tools/ship.ps1 -Mode release -Changelog "Fix: gallery crash"
.EXAMPLE
  ./tools/ship.ps1 -Mode auto -DryRun
#>
param(
  [ValidateSet('patch', 'release', 'auto')]
  [string]$Mode = 'auto',
  [string]$ReleaseVersion,
  [switch]$DryRun,
  [string]$Changelog,
  [switch]$AllowAssetDiffs,
  [switch]$AllowNativeDiffs
)

# Native CLIs (shorebird.bat) stderr par warnings likhte hain; unhe terminating
# error mat banao. Real success/failure $LASTEXITCODE se decide hota hai.
$ErrorActionPreference = 'Continue'

# --- Fixed environment (project setup ke hisaab se) -----------------------
$ShorebirdBat = 'C:\Users\DELL\.shorebird\bin\shorebird.bat'
$FlutterBat   = 'C:\Projects\apps\flutter_sdk\bin\flutter.bat'
$AppDir       = Split-Path -Parent $PSScriptRoot          # ...\app\tools -> ...\app
$Pubspec      = Join-Path $AppDir 'pubspec.yaml'
$UpdateSvc    = Join-Path $AppDir 'lib\services\update_service.dart'
$AdbDir       = Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools'
# NOTE: flutter passthrough flag (--no-tree-shake-icons) Invoke-ShorebirdBuild
# me literal hardcoded hai (single source of truth, drift-proof).

function Write-Step([string]$m) { Write-Host "`n=== $m ===" -ForegroundColor Cyan }
function Write-Ok([string]$m)   { Write-Host "  [ok] $m"   -ForegroundColor Green }
function Write-Note([string]$m) { Write-Host "  [..] $m"   -ForegroundColor Gray }
function Write-Warn2([string]$m){ Write-Host "  [!!] $m"   -ForegroundColor Yellow }
function Die([string]$m) { Write-Host "`nFAILED: $m" -ForegroundColor Red; exit 1 }

# Shorebird ko run karke combined text return karta hai (parsing ke liye).
function Get-ShorebirdOutput([string[]]$ArgList) {
  $out = & $ShorebirdBat @ArgList 2>&1 | Out-String
  return $out
}

# Build (patch/release) - flutter args ko QUOTED '--' separator se bhejta hai.
# Kyun: shorebird.bat khud ek inner PowerShell -Command "& shorebird.ps1 %1.."
# chalata hai. Us inner PowerShell me bare "--" end-of-parameters marker ban ke
# GIR jaata hai, isliye shorebird ko "--no-tree-shake-icons" seedha option lagta
# hai aur reject kar deta hai. Literal '--' (single-quotes ke saath) bhejne par
# inner PowerShell use plain string rakhta hai -> shorebird -> flutter tak
# pohanchta hai. Flag yahin hardcoded (drift-proof) - release AUR patch dono.
function Invoke-ShorebirdBuild([string[]]$sbArgs) {
  $full = $sbArgs + @("'--'", '--no-tree-shake-icons')
  Write-Note ('shorebird ' + ($full -join ' '))
  $captured = New-Object System.Collections.Generic.List[string]
  & $ShorebirdBat @full 2>&1 | ForEach-Object {
    $line = [string]$_
    Write-Host $line
    $captured.Add($line)
  }
  $code = $LASTEXITCODE
  # Shorebird kabhi-kabhi (e.g. dry-run) UnpatchableChangeException ke baad bhi
  # exit 0 deta hai. Output text scan karke real failure pakdo.
  $text = ($captured -join "`n")
  if ($text -match 'UnpatchableChangeException' -or
      $text -match 'contains asset changes' -or
      $text -match 'cannot be patched') {
    # Shorebird may still publish when --allow-native-diffs / --allow-asset-diffs
    # are set; warnings in output are not a failure if patch was published.
    if ($text -match 'Published Patch') {
      if ($code -ne 0) { return 0 }
    } elseif ($code -eq 0) {
      return 99   # exit code lied -> force fail
    }
  }
  return $code
}

# releases list newest-first deta hai; pehla "android: active" = newest.
function Get-NewestActiveRelease {
  $txt = Get-ShorebirdOutput @('releases', 'list')
  foreach ($line in ($txt -split "`r?`n")) {
    if ($line -match '([0-9]+\.[0-9]+\.[0-9]+\+[0-9]+)\s+android:\s*active') {
      return $Matches[1]
    }
  }
  return $null
}

# Diye gaye release ka next patch number (max existing + 1).
function Get-NextPatchNumber([string]$rv) {
  $txt = Get-ShorebirdOutput @('patches', 'list', '--release-version', $rv)
  $max = 0
  foreach ($line in ($txt -split "`r?`n")) {
    if ($line -match '#\s*([0-9]+)') {
      $n = [int]$Matches[1]
      if ($n -gt $max) { $max = $n }
    }
  }
  return ($max + 1)
}

# pubspec.yaml ka +build number +1 karta hai (version name same rehta hai).
function Step-BumpBuild {
  $c = Get-Content $Pubspec -Raw
  if ($c -notmatch '(?m)^version:\s*([0-9]+)\.([0-9]+)\.([0-9]+)\+([0-9]+)\s*$') {
    Die "pubspec.yaml me 'version: x.y.z+b' parse nahi hua."
  }
  $maj = $Matches[1]; $min = $Matches[2]; $pat = $Matches[3]; $bld = [int]$Matches[4]
  $old = "$maj.$min.$pat+$bld"
  $new = "$maj.$min.$pat+$($bld + 1)"
  # [ \t] use karo, \s nahi - warna multiline mode me newline/blank line bhi
  # khaa jaata hai.
  $c2  = $c -replace ('(?m)^version:[ \t]*' + [regex]::Escape($old) + '[ \t]*$'), "version: $new"
  Set-Content -Path $Pubspec -Value $c2 -NoNewline
  Write-Ok "pubspec version bumped: $old -> $new"
  return @{ Old = $old; New = $new }
}

# git changes dekh kar decide: native/asset/dep change hai? (auto mode)
function Test-NeedsRelease {
  $changed = @()
  $changed += (& git -C $AppDir diff --name-only HEAD 2>$null)
  $changed += (& git -C $AppDir ls-files --others --exclude-standard 2>$null)
  foreach ($f in $changed) {
    if ([string]::IsNullOrWhiteSpace($f)) { continue }
    # Build/cache artifacts ignore karo.
    if ($f -match '(^|/)(build|\.dart_tool|\.gradle|\.cxx)/') { continue }
    if ($f -match '(^|/)(android|ios)/') { return $true }
    if ($f -match '(^|/)assets/')        { return $true }
  }
  # pubspec dependency change? (sirf version line ka bump ignore karo)
  $pd = & git -C $AppDir diff -U0 HEAD -- pubspec.yaml 2>$null
  if ($pd) {
    foreach ($l in ($pd -split "`r?`n")) {
      if ($l -match '^[+-]{3}') { continue }
      if ($l -match '^[+-]\s*version:') { continue }
      if ($l -match '^[+-]\s+\S+:\s') { return $true }   # changed dependency line
    }
  }
  return $false
}

# Build ke baad NEWEST release APK dhoondta hai (stale artifact se bachne ke liye).
function Get-ApkPath {
  $found = Get-ChildItem -Path (Join-Path $AppDir 'build') -Recurse -Filter '*-release.apk' -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch '\\intermediates\\' } |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if ($found) { return $found.FullName }
  return $null
}

# latestChangelog constant ko <release>:<patch> marker ke saath set karta hai.
function Set-Changelog([string]$marker, [string]$text) {
  if (-not (Test-Path $UpdateSvc)) { Write-Warn2 "update_service.dart nahi mila; changelog skip."; return $false }
  $c  = Get-Content $UpdateSvc -Raw
  $rx = [regex]'(?s)(static const String latestChangelog\s*=\s*).*?;'
  if (-not $rx.IsMatch($c)) { Write-Warn2 "latestChangelog locate nahi hua; manually update karo."; return $false }

  # -Changelog ki pehli line = summary, baaki = bullets.
  $parts   = $text -split "`r?`n"
  $summary = $parts[0].Trim()
  $bullets = $parts | Select-Object -Skip 1 | Where-Object { $_.Trim() -ne '' }
  $payload = "$marker - $summary"
  foreach ($b in $bullets) { $payload += '\n- ' + ($b.Trim() -replace '^[-*]\s*', '') }
  # Dart single-quoted string ke liye escape (backslash + quote).
  $esc = $payload -replace '\\', '\\' -replace "'", "\'"

  $eval = [System.Text.RegularExpressions.MatchEvaluator] {
    param($m) $m.Groups[1].Value + "'$esc';"
  }
  Copy-Item $UpdateSvc "$UpdateSvc.bak" -Force
  Set-Content $UpdateSvc ($rx.Replace($c, $eval, 1)) -NoNewline

  Push-Location $AppDir
  & $FlutterBat analyze lib/services/update_service.dart 2>&1 | Out-Null
  $code = $LASTEXITCODE
  Pop-Location
  if ($code -ne 0) {
    Copy-Item "$UpdateSvc.bak" $UpdateSvc -Force
    Remove-Item "$UpdateSvc.bak" -Force -ErrorAction SilentlyContinue
    Write-Warn2 "flutter analyze fail -> changelog edit revert. Manually update karo."
    return $false
  }
  Remove-Item "$UpdateSvc.bak" -Force -ErrorAction SilentlyContinue
  Write-Ok "latestChangelog set: $marker"
  return $true
}

# Phone connected? Connected ho to install, warna command print.
function Show-InstallStep([string]$apk) {
  Write-Step 'Phone install (Samsung RZCY40DLFBA)'
  if (-not $apk) { Write-Warn2 'APK path nahi mila - upar build output dekho.'; return }
  Write-Host "  APK: $apk"
  $adb = Join-Path $AdbDir 'adb.exe'
  $cmd = '"' + $adb + '" install -r "' + $apk + '"'
  if (-not (Test-Path $adb)) {
    Write-Warn2 'adb nahi mila. Install command:'
    Write-Host "  $cmd"
    return
  }
  $devs = & $adb devices 2>&1 | Out-String
  $online = @()
  foreach ($l in ($devs -split "`r?`n")) {
    if ($l -match '^(\S+)\s+device\b') { $online += $Matches[1] }
  }
  if ($online.Count -gt 0) {
    Write-Ok ('Device connected: ' + ($online -join ', ') + ' - installing...')
    & $adb install -r $apk 2>&1 | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -eq 0) { Write-Ok 'Install done. App khol ke verify karo.' }
    else { Write-Warn2 "Install fail. Manually: $cmd" }
  } else {
    Write-Warn2 'Koi device connected nahi (phone disconnected). Jab connect ho to chalao:'
    Write-Host "  $cmd"
  }
}

# ==========================================================================
$banner = "RF Logger ship.ps1 - Mode=$Mode"
if ($DryRun) { $banner += ' (DRY-RUN)' }
Write-Host $banner -ForegroundColor Magenta
if (-not (Test-Path $ShorebirdBat)) { Die "shorebird.bat nahi mila: $ShorebirdBat" }
if (-not (Test-Path $AppDir))       { Die "App dir nahi mila: $AppDir" }

# auto -> patch/release decide
if ($Mode -eq 'auto') {
  Write-Step 'Auto-detect: native/asset/dep change?'
  if (Test-NeedsRelease) {
    Write-Note 'Native/asset/dep change mila -> RELEASE'
    $Mode = 'release'
  } else {
    Write-Note 'Sirf Dart change -> PATCH'
    $Mode = 'patch'
  }
}

Push-Location $AppDir
try {
  if ($Mode -eq 'patch') {
    Write-Step 'PATCH mode'
    if (-not $ReleaseVersion) {
      $ReleaseVersion = Get-NewestActiveRelease
      if (-not $ReleaseVersion) { Die 'Active release detect nahi hua. -ReleaseVersion do.' }
      Write-Ok "Auto release target: $ReleaseVersion (newest active)"
    } else {
      Write-Ok "Release target (override): $ReleaseVersion"
    }
    Write-Warn2 "Yaad rahe: patch tabhi dikhega jab phone par EXACTLY $ReleaseVersion install ho."

    $next = Get-NextPatchNumber $ReleaseVersion
    $marker = "${ReleaseVersion}:$next"
    if ($Changelog) { [void](Set-Changelog $marker $Changelog) }
    else { Write-Note "Changelog marker suggestion: $marker (update_service.dart latestChangelog me daalo)" }

    $sbArgs = @('patch', 'android', "--release-version=$ReleaseVersion")
    if ($DryRun)          { $sbArgs += '--dry-run' }
    if ($AllowAssetDiffs) { $sbArgs += '--allow-asset-diffs' }
    if ($AllowNativeDiffs){ $sbArgs += '--allow-native-diffs' }

    $code = Invoke-ShorebirdBuild $sbArgs
    if ($code -ne 0) {
      Write-Warn2 "Patch command non-zero (code $code)."
      Write-Warn2 "Agar UnpatchableChangeException / asset diff aaya: yeh release line"
      Write-Warn2 "purane (tree-shake ON) build se bana tha. Fix: -Mode release se nayi"
      Write-Warn2 "release cut karo (yeh --no-tree-shake-icons use karti hai), phir APK install."
      Die 'Patch fail.'
    }
    Write-Step 'DONE (patch)'
    if (-not $DryRun) {
      Write-Ok "Patch publish ho gaya. Release $ReleaseVersion, patch number $next, track stable."
      Write-Host '  Phone par: app ko POORA band karo (recents se swipe) phir dobara kholo.' -ForegroundColor White
      Write-Host '  Pehli baar khulte hi patch download hota hai; doosri baar khulne par active.' -ForegroundColor White
    } else {
      Write-Ok 'Dry-run complete - kuch upload nahi hua.'
    }
  }
  elseif ($Mode -eq 'release') {
    Write-Step 'RELEASE mode'
    if ($DryRun) {
      # Dry-run me pubspec mat chhedo - sirf current version validate karo.
      Write-Note 'Dry-run: pubspec version bump skip.'
      $code = Invoke-ShorebirdBuild @('release', 'android', '--artifact', 'apk', '--dry-run')
      if ($code -ne 0) { Die "Release dry-run fail (code $code)." }
      Write-Step 'DONE (release)'
      Write-Ok 'Dry-run complete - kuch upload nahi hua.'
      return
    }
    $ver = Step-BumpBuild
    $marker = "$($ver.New):0"
    if ($Changelog) { [void](Set-Changelog $marker $Changelog) }
    else { Write-Note "Changelog marker suggestion: $marker" }

    $code = Invoke-ShorebirdBuild @('release', 'android', '--artifact', 'apk')
    if ($code -ne 0) { Die "Release fail (code $code)." }

    Write-Step 'DONE (release)'
    Write-Ok "Release $($ver.New) publish ho gayi (--no-tree-shake-icons)."
    $apk = Get-ApkPath
    Show-InstallStep $apk
    Write-Host "`n  Aage se is line par Dart-only fixes:" -ForegroundColor White
    Write-Host "    ./tools/ship.ps1 -Mode patch -ReleaseVersion $($ver.New)" -ForegroundColor White
  }
}
finally {
  Pop-Location
}
