# Watch seller-login progress — refresh terminal status every 60 seconds.

# Run in a second PowerShell window while seller-login is active:

#   cd agent

#   powershell -File scripts\watch_seller_login.ps1



$ErrorActionPreference = "SilentlyContinue"

$AgentDir = Split-Path $PSScriptRoot -Parent

$ProjectRoot = Split-Path $AgentDir -Parent



# Match MAHIKA_STORAGE_ROOT from agent/.env when set

$StorageRoot = $null

$EnvFile = Join-Path $AgentDir ".env"

if (Test-Path $EnvFile) {

    Get-Content $EnvFile | ForEach-Object {

        if ($_ -match '^\s*MAHIKA_STORAGE_ROOT=(.+)$') {

            $StorageRoot = $Matches[1].Trim().Trim('"')

        }

    }

}

if (-not $StorageRoot) {

    $StorageRoot = Join-Path $ProjectRoot "data\mahika"

}



$StatusFile = [System.IO.Path]::GetFullPath((Join-Path $StorageRoot "logs\seller_login_live.txt"))

$LogDir = [System.IO.Path]::GetFullPath((Join-Path $StorageRoot "logs"))



Write-Host "Mahika login watcher — refresh every 60s"

Write-Host "Status file: $StatusFile"

Write-Host "Log dir:     $LogDir"

Write-Host ""



while ($true) {

    Clear-Host

    Write-Host ("=== " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " ===")



    if (Test-Path $StatusFile) {

        Write-Host "`n--- Live status ---"

        Get-Content $StatusFile -Tail 5

    } else {

        Write-Host "`n(no seller_login_live.txt yet — seller-login not on OTP step?)"

    }



    $latest = Get-ChildItem $LogDir -Filter "*.log" -ErrorAction SilentlyContinue |

        Sort-Object LastWriteTime -Descending |

        Select-Object -First 1

    if ($latest) {

        Write-Host "`n--- Latest log ($($latest.Name)) ---"

        Get-Content $latest.FullName -Tail 8

    } else {

        Write-Host "`n(no .log files in $LogDir)"

    }



    Write-Host "`n(next refresh in 60s — Ctrl+C to stop)"

    Start-Sleep -Seconds 60

}

