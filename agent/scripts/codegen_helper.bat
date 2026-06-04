@echo off
REM ───────────────────────────────────────────────────────────────────────
REM  Mahika Playwright codegen helper — Phase 5 / Phase 7 launch prep
REM
REM  Purpose: Open Playwright's codegen browser pre-pointed at Seller
REM           Central so Sir can capture the actual selectors that go into
REM           src\mahika\playwright\selectors.py (replacing the
REM           # TODO(codegen) placeholders).
REM
REM  Workflow:
REM    1. Run this script
REM    2. A browser opens at https://sellercentral.amazon.in
REM    3. Log in (Amazon will OTP-challenge you)
REM    4. Navigate: Performance → SAFE-T Claims → File New Claim
REM    5. Walk through filing a claim (or abort before submitting)
REM    6. Playwright's inspector window shows captured selectors
REM    7. Copy each into selectors.py
REM    8. Optional: save cookies via the inspector's "Save" button to
REM       D:\Mahika\sessions\seller_central_cookies.json — skips manual
REM       login on first agent boot
REM
REM  Re-run when: Amazon refreshes the Seller Central UI (selectors drift)
REM ───────────────────────────────────────────────────────────────────────

setlocal
set "PROJECT_ROOT=%~dp0..\"
cd /d "%PROJECT_ROOT%"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: .venv not found. Run scripts\mahika-setup.bat first.
    exit /b 1
)

echo.
echo === Launching Playwright codegen for Seller Central ===
echo Project root: %CD%
echo.
echo Output language: Python
echo Target URL:      https://sellercentral.amazon.in
echo Selectors file:  src\mahika\playwright\selectors.py (replace the TODO(codegen) lines)
echo.

.\.venv\Scripts\python.exe -m playwright codegen ^
    --target=python ^
    --output=NUL ^
    https://sellercentral.amazon.in

echo.
echo === Codegen window closed ===
echo Next: open src\mahika\playwright\selectors.py and paste the selectors
echo       you captured from the inspector window. Replace the
echo       # TODO(codegen) lines, then commit selectors.py.
echo.
exit /b 0
