# Register Mahika to start at Windows login (Task Scheduler)

$ErrorActionPreference = "Stop"
$AgentRoot = Split-Path $PSScriptRoot -Parent
$Bat = Join-Path $AgentRoot "Start-Mahika.bat"
$TaskName = "MahikaDaemon"

if (-not (Test-Path $Bat)) {
    Write-Host "ERROR: Start-Mahika.bat not found at $Bat"
    exit 1
}

$Action = New-ScheduledTaskAction -Execute $Bat -WorkingDirectory $AgentRoot
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Force | Out-Null

Write-Host "OK: Task '$TaskName' registered — runs Start-Mahika.bat at login."
Write-Host "Remove: Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
