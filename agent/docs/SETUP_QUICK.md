# Mahika — 15 minute Sir checklist

## Step 0 — Credentials (ek baar)

1. Workspace root `.env` kholo (`C:\Projects\Amazon Systems Design\.env`)
2. Blank lines bharo — priority order:
   - `MAHIKA_DB_*` — Oracle Postgres (ya local backup)
   - `MAHIKA_COCKPIT_TOKEN` — `python -c "import secrets; print(secrets.token_urlsafe(32))"`
   - `MAHIKA_SP_API_*` — guide: `scripts/sp_api_registration_checklist.md`
   - `MAHIKA_TELEGRAM_*` — guide: `scripts/telegram_setup.md`
3. Sync:
   ```powershell
   cd "C:\Projects\Amazon Systems Design"
   powershell -ExecutionPolicy Bypass -File scripts\sync_env.ps1
   ```

## Step 1 — Machine setup (~5 min)

```powershell
cd "C:\Projects\Amazon Systems Design\agent"
scripts\quick_setup.bat
```

Yeh karta hai: Python venv, packages, Chromium, storage folders.

## Step 2 — Verify (~2 min)

```powershell
scripts\quick_verify.bat
```

Green = doctor OK + smokes pass (DB chahiye smokes ke liye).

## Step 3 — Seller Central session (ek baar, ~10 min)

Cookies already hain: `data/mahika/sessions/seller_central_cookies.json`

Agar expire ho jaye — headed browser se login (future: `wizard_capture.py`).

## Step 4 — Shadow daemon

```powershell
Start-Mahika.bat
# ya foreground:
.\.venv\Scripts\python.exe -m mahika.cli start --once
.\.venv\Scripts\python.exe -m mahika.cli status
```

## Step 5 — Cockpit (optional)

```powershell
.\.venv\Scripts\python.exe -m mahika.cli cockpit
```

Browser: `http://127.0.0.1:8765/` — token `.env` se paste karo.

## Auto-start (optional)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1
```

Login par `Start-Mahika.bat` chalega.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Doctor DB fail | `MAHIKA_DB_PASSWORD` root `.env` mein, phir `sync_env.ps1` |
| Chromium fail | `.venv\Scripts\python.exe -m playwright install chromium` |
| Telegram fail | `mahika.cli telegram-test` after token + chat_id |

Full ops: `docs/RUNBOOK.md`
