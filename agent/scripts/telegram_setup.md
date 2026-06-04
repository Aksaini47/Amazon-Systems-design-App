# Telegram setup (~5 min)

## 1. Create bot

1. Telegram mein **@BotFather** kholo
2. `/newbot` → naam do → token copy karo
3. Root `.env` mein:
   ```
   MAHIKA_TELEGRAM_BOT_TOKEN=123456:ABC...
   ```
4. Sync:
   ```powershell
   cd "C:\Projects\Amazon Systems Design"
   powershell -File scripts\sync_env.ps1
   ```

## 2. Get chat ID

1. Apne bot ko ek message bhejo (e.g. `hi`)
2. Agent folder se:
   ```powershell
   cd agent
   .\.venv\Scripts\python.exe -m mahika.cli telegram-chatid
   ```
3. Jo ID aaye, root `.env` mein:
   ```
   MAHIKA_TELEGRAM_CHAT_ID=123456789
   ```
4. Phir se `sync_env.ps1`

## 3. Test

```powershell
.\.venv\Scripts\python.exe -m mahika.cli telegram-test
```

Telegram par test message aana chahiye.

## 4. Daily digest (manual test)

```powershell
.\.venv\Scripts\python.exe -m mahika.cli digest
```

Scheduler roz 9am IST par bhejega jab daemon chal raha ho aur Telegram configured ho.

## Alerts

| Priority | Channel |
|----------|---------|
| CRITICAL | Telegram immediate (OTP, hard-stops) |
| HIGH | Telegram hourly batch |
| MEDIUM | Daily digest only |
| LOW | Audit log only |
