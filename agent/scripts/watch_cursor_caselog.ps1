# Cursor-browser Case Log teach — OTP watcher (3×60s Telegram)
# Run in a separate terminal while Sir uses Cursor Browser side panel.
Set-Location $PSScriptRoot\..
.\.venv\Scripts\python.exe -m mahika.cli otp-watch --round-label caselog-teach
