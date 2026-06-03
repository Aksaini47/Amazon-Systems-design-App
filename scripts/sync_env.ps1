# Sync Mahika + backend env vars from workspace root .env to child projects.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\sync_env.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$RootEnv = Join-Path $Root ".env"
$AgentEnv = Join-Path $Root "agent\.env"
$BackendEnv = Join-Path $Root "backend\.env"

if (-not (Test-Path $RootEnv)) {
    Write-Host "ERROR: $RootEnv missing. Copy .env.example to .env first."
    exit 1
}

function Read-EnvMap([string]$Path) {
    $map = @{}
    Get-Content $Path -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if ($line -eq "" -or $line.StartsWith("#")) { return }
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            $val = $Matches[2].Trim().Trim('"').Trim("'")
            $map[$Matches[1]] = $val
        }
    }
    return $map
}

$src = Read-EnvMap $RootEnv

# --- agent/.env ---
$mahikaKeys = @(
    "MAHIKA_STORAGE_ROOT", "MAHIKA_MODE",
    "MAHIKA_DB_HOST", "MAHIKA_DB_PORT", "MAHIKA_DB_NAME", "MAHIKA_DB_USER", "MAHIKA_DB_PASSWORD",
    "MAHIKA_SP_API_REFRESH_TOKEN", "MAHIKA_SP_API_LWA_CLIENT_ID", "MAHIKA_SP_API_LWA_CLIENT_SECRET",
    "MAHIKA_SP_API_ROLE_ARN", "MAHIKA_SP_API_REGION", "MAHIKA_SP_API_MARKETPLACE_ID",
    "MAHIKA_SP_API_SANDBOX",
    "MAHIKA_TELEGRAM_BOT_TOKEN", "MAHIKA_TELEGRAM_CHAT_ID",
    "MAHIKA_COCKPIT_TOKEN", "MAHIKA_COCKPIT_PORT", "MAHIKA_RUNNER_ID", "MAHIKA_SENTRY_DSN",
    "AMAZON_SELLER_EMAIL", "AMAZON_SELLER_PASSWORD",
    "AMAZON_ADMIN_EMAIL", "AMAZON_ADMIN_PASSWORD"
)

$agentLines = @(
    "# Mahika agent - auto-synced from workspace root .env",
    "# Edit root .env then re-run: powershell -File scripts\sync_env.ps1",
    ""
)
foreach ($k in $mahikaKeys) {
    if ($src.ContainsKey($k) -and $src[$k] -ne "") {
        $agentLines += "$k=$($src[$k])"
    } elseif ($src.ContainsKey($k)) {
        $agentLines += "$k="
    }
}
if (-not $src.ContainsKey("MAHIKA_STORAGE_ROOT") -or $src["MAHIKA_STORAGE_ROOT"] -eq "") {
    $agentLines += "MAHIKA_STORAGE_ROOT=C:/Projects/Amazon Systems Design/data/mahika"
}
if (-not $src.ContainsKey("MAHIKA_MODE") -or $src["MAHIKA_MODE"] -eq "") {
    $agentLines += "MAHIKA_MODE=shadow"
}
$agentLines | Set-Content -Path $AgentEnv -Encoding UTF8
Write-Host "OK: $AgentEnv"

# --- backend/.env ---
$storage = if ($src["BACKEND_STORAGE_ROOT"]) { $src["BACKEND_STORAGE_ROOT"] } else { "./data" }
$port = if ($src["BACKEND_PORT"]) { $src["BACKEND_PORT"] } else { "3001" }
$backendLines = @(
    "# Legacy camera backend - auto-synced from workspace root .env",
    "STORAGE_ROOT=$storage",
    "PORT=$port",
    "AMAZON_CLIENT_ID=$($src['BACKEND_AMAZON_CLIENT_ID'])",
    "AMAZON_CLIENT_SECRET=$($src['BACKEND_AMAZON_CLIENT_SECRET'])",
    "AMAZON_REFRESH_TOKEN=$($src['BACKEND_AMAZON_REFRESH_TOKEN'])",
    "AMAZON_MARKETPLACE_ID=$($src['BACKEND_AMAZON_MARKETPLACE_ID'])"
)
if (-not $src["BACKEND_AMAZON_MARKETPLACE_ID"]) {
    $backendLines[-1] = "AMAZON_MARKETPLACE_ID=A21TJRUUN4KGV"
}
$backendLines | Set-Content -Path $BackendEnv -Encoding UTF8
Write-Host "OK: $BackendEnv"

Write-Host ""
Write-Host "Done. Next: cd agent && scripts\quick_setup.bat"
