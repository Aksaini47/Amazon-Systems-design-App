# Mahika operational runbook

Single source of truth for Sir on how to launch, operate, and recover Mahika.
Read top-to-bottom on first boot; bookmark sections for later.

> ❄️ This runbook assumes the build is already complete (commit `02b4885` or later).
> If you're setting up Mahika on a fresh machine for the first time, run
> `scripts\mahika-setup.bat` first, then return here.

---

## 1. Phase 7a launch checklist — one-time setup

Tick each in order. ~30 minutes total. Most steps are 1-2 minutes; the SP-API
codegen step is the longest.

### 1.1 Generate cockpit token

```powershell
cd "C:\Projects\Amazon Systems Design\agent"
.\.venv\Scripts\python.exe -c "import secrets; print('MAHIKA_COCKPIT_TOKEN=' + secrets.token_urlsafe(32))"
```

Copy the output into `.env`, replacing the empty `MAHIKA_COCKPIT_TOKEN=` line.

### 1.2 Install Tesseract OCR (unlocks Layer 4 FPC matching)

```powershell
winget install UB-Mannheim.TesseractOCR
```

Verify after install (open a new PowerShell):
```powershell
tesseract --version
```
Should print `tesseract 5.x.x ...`. If not, restart PowerShell and try again.

**Optional**: If `tesseract` isn't found on PATH but is installed, add the
path to `.env`:
```
MAHIKA_TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
```

### 1.3 Create Telegram bot

1. Open Telegram on your phone, message `@BotFather`
2. Send `/newbot`, follow prompts. Pick a name like `Mahika alerts`
3. BotFather returns a token like `1234567890:AAH...`. Copy it to `.env`:
   ```
   MAHIKA_TELEGRAM_BOT_TOKEN=1234567890:AAH...
   ```
4. Get your chat ID:
   - Send your bot any message (e.g. `/start`)
   - From PowerShell:
     ```powershell
     $token = "<the token from step 3>"
     Invoke-RestMethod "https://api.telegram.org/bot$token/getUpdates" | ConvertTo-Json -Depth 10
     ```
   - Look for `chat.id` in the response. Paste into `.env`:
     ```
     MAHIKA_TELEGRAM_CHAT_ID=<the id>
     ```

### 1.4 Capture Seller Central selectors (Playwright codegen)

This populates the `# TODO(codegen)` placeholders in
`src/mahika/playwright/selectors.py`. Done once per Amazon UI refresh.

```powershell
cd "C:\Projects\Amazon Systems Design\agent"
.\.venv\Scripts\activate
playwright codegen https://sellercentral.amazon.in
```

In the opened browser:
1. Sign in (OTP if Amazon prompts)
2. Navigate: **Performance → SAFE-T Claims → File New Claim**
3. Walk through filing a test claim (or abort before submitting)
4. Playwright's inspector window prints Python code as you click
5. Copy each selector into `src/mahika/playwright/selectors.py`, replacing
   the placeholders. Comments mark which page each block belongs to.
6. Remove the `# TODO(codegen)` comments once filled
7. Save the file

**Pro tip**: capture the cookies too. After login, in the inspector click
"Save" → save to `D:\Mahika\sessions\seller_central_cookies.json`. Skips
the manual-login flow on first agent boot.

### 1.5 Verify the wiring

Run all phase smoke tests in order. Each should print `PASS`:

```powershell
cd "C:\Projects\Amazon Systems Design\agent"
$env:PYTHONIOENCODING="utf-8"
.\.venv\Scripts\python.exe -m tests.test_phase3_smoke
.\.venv\Scripts\python.exe -m tests.test_phase4_smoke
.\.venv\Scripts\python.exe -m tests.test_phase5_smoke
.\.venv\Scripts\python.exe -m tests.test_phase6_smoke
```

If any fails, see §6 below for diagnostics.

---

## 2. Day-to-day operations

Two processes run side-by-side:

### Terminal 1 — Scheduler daemon

```powershell
cd "C:\Projects\Amazon Systems Design\agent"
.\.venv\Scripts\python.exe -m mahika.cli start
```

This is the agent itself. Blocks until `Ctrl-C`. Tasks fire on their own
cadence (every 30min for filing, every 4h for returns, etc.).

### Terminal 2 — Cockpit dashboard

```powershell
cd "C:\Projects\Amazon Systems Design\agent"
.\.venv\Scripts\python.exe -m mahika.cli cockpit
```

Then open http://127.0.0.1:8765 in your browser and paste `MAHIKA_COCKPIT_TOKEN`.

### CLI utilities (one-shot, no process)

```powershell
.\.venv\Scripts\python.exe -m mahika.cli status        # quick snapshot
.\.venv\Scripts\python.exe -m mahika.cli queue         # claim queue depth
.\.venv\Scripts\python.exe -m mahika.cli audit-tail 50 # last 50 audit events
.\.venv\Scripts\python.exe -m mahika.cli start --once  # run all tasks once + exit
.\.venv\Scripts\python.exe -m mahika.cli process 407-1234567-1234567  # manual Phase 3
```

---

## 3. Mode flip — shadow → live

Mahika starts in `shadow` mode (per `.env`). She runs everything except
clicking the actual "Submit" button on Seller Central.

**Phase 7a — Shadow week** (recommended):
- Leave `MAHIKA_MODE=shadow` for 1 week
- Every day, check the cockpit's `/claims` page — verify queued claims look
  right, verify screenshots in `D:\Mahika\orders\{order_id}\` look submittable
- No SAFE-T claims actually file during this week

**Phase 7b — Whitelisted live**:
- When confidence is high, flip `MAHIKA_MODE=live` in `.env`
- Restart the scheduler (Ctrl-C, re-run `mahika.cli start`)
- Mahika now files autonomously

**Pause anytime**: `MAHIKA_MODE=paused` in `.env` + restart. Filing halts;
polling continues; state preserved.

---

## 4. Failure modes & responses

### Telegram alert "Mahika needs Sir's Seller Central OTP"

Cookies expired (typically every 7-14 days). On the active runner machine, a
headed Chrome window auto-opens. Log in there with OTP. Mahika detects the
home page and resumes automatically — no Telegram reply needed.

### Telegram alert "Claim filing crashed: 407-..."

Open the cockpit `/claims` page. Find the order. Click the row to see
`last_error`. Common causes:
- Selector drift (Amazon changed the UI) → re-run codegen §1.4
- Network blip → leaves `attempt_count++`, next scheduler tick retries
- Session expired → handled automatically, see above

### Cockpit shows "Last heartbeat: STALE"

Active runner crashed or is paused. From the runner machine:
```powershell
.\.venv\Scripts\python.exe -m mahika.cli status
```
If status shows the heartbeat, the scheduler is alive — refresh the cockpit.
If not, restart the scheduler.

### Runner conflict (two laptops running)

The heartbeat lease enforces single-active-runner. If both Dell + ThinkPad
try to run the scheduler with the NVMe plugged in via different methods,
the second one will alert Sir and refuse to schedule tasks. To switch
runners:
1. On the currently-active machine: `Ctrl-C` the scheduler
2. Unplug NVMe
3. Plug NVMe into the new machine
4. Start scheduler there

### Postgres unreachable (Oracle Mumbai issue)

Mahika audit_log writes fail → scheduler treats as hard stop, halts tasks,
fires CRITICAL Telegram. To diagnose:
```powershell
.\.venv\Scripts\python.exe -c "from sqlalchemy import text; from mahika.db.connection import db_engine; print(db_engine.connect().execute(text('SELECT now()')).scalar())"
```
If that fails, check:
1. Oracle VM status in the Oracle Cloud console (might have been reclaimed
   if idle > 7 days — see `scripts\setup_oracle_vm.md §11`)
2. Local internet
3. `.env` `MAHIKA_DB_HOST` matches the VM's current public IP

---

## 5. Insights review (weekly)

Every Sunday 23:00 UTC, the Insights Engine runs. Monday morning Sir checks
the cockpit's `/insights` page:

1. **Pending suggestions** — Mahika's proposals. For each, click Approve or
   Reject. Approved ones go on the build backlog; rejected ones are logged
   with reason so Mahika doesn't re-propose them.
2. **Recent insight metrics** — raw pattern data. Useful for sanity-checking
   approval rates, refund delays, hard-stop frequency.
3. **Decided** history — your past calls, for accountability.

No-action mode: ignoring the page won't break anything. Suggestions live
forever in the DB.

---

## 6. Diagnostics cheatsheet

| Symptom | First check |
|---|---|
| Smoke test fails | Re-read `.env` — DB host, password, cockpit token all set? |
| Cockpit returns 401 on login | Token in `.env` matches what you're pasting? |
| Cockpit returns 502/503 | `mahika.cli cockpit` actually running? Port collision? |
| Scheduler does nothing | `MAHIKA_MODE=paused`? Heartbeat lease lost to another machine? |
| No Telegram alerts arriving | `TELEGRAM_BOT_TOKEN` + `CHAT_ID` set? Bot blocked? |
| Composite generation fails | `D:\Mahika\orders\{order_id}\` exists with all 4 source JPGs? |
| OCR layer reports unavailable | Tesseract not on PATH — see §1.2 |

For deeper debugging, tail the audit log:
```powershell
.\.venv\Scripts\python.exe -m mahika.cli audit-tail 100
```

The audit log is court-grade — every action Mahika takes is in there.
Search for `task.failed` or `*.crashed` for recent errors.

---

## 7. Backup discipline (manual, per storage decision)

Per `mahika_capture_specs.md §1.2`, evidence is NVMe-only. No cloud DR.
Sir's manual backup discipline:

**Quarterly cold copy**:
1. Stop the scheduler (`Ctrl-C`)
2. Plug a second physical drive
3. Copy `D:\Mahika\orders\` to `<other-drive>\mahika-archive-YYYY-Q?\`
4. Verify a random sample of files opened cleanly
5. Disconnect the cold drive, store somewhere physically distinct
6. Restart scheduler

Why quarterly: enough cadence that NVMe loss costs ≤3 months of evidence.
Active claims (still pending Amazon decision) are also mirrored to the
audit_log JSONB payload in Postgres — so claim metadata survives even total
NVMe loss; only the source media (videos/photos/composites) is lost.

---

## 8. Decommission / sunset checklist

When Sir winds down a runner machine:

1. `mahika.cli status` — verify the lease can be released cleanly
2. Stop the scheduler
3. Unplug NVMe (move to the new runner)
4. On the new runner: `scripts\mahika-setup.bat`
5. The heartbeat lease will be re-acquired by the new runner on next tick

Don't delete the venv on the old machine immediately — wait a week to be
sure the new runner is stable. Then `rmdir /s /q .venv` on the old box.

---

❄️ *Prepared for Sir by the Coordinator. Project Alpha — Mahika माहिका.*
