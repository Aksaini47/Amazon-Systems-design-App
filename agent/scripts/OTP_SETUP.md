# Mahika — OTP auto-fill + session cookies setup (~15 min)

Two pieces work together:

1. **Session cookies** — login once, trust device, Mahika reuses cookies 7–14 days  
2. **Telegram OTP** — Sir sends **only the 6-digit code** to the bot (full SMS optional)

---

## Part A — Telegram bot (5 min)

1. Telegram → **@BotFather** → `/newbot` → copy token  
2. Root `.env`:
   ```
   MAHIKA_TELEGRAM_BOT_TOKEN=...
   ```
3. Message your bot once (`hi`)  
4. Sync + get chat id:
   ```powershell
   cd "C:\Projects\Amazon Systems Design"
   powershell -File scripts\sync_env.ps1
   cd agent
   .\.venv\Scripts\python.exe -m mahika.cli telegram-chatid
   ```
5. Paste chat id into root `.env` as `MAHIKA_TELEGRAM_CHAT_ID=...`  
6. Sync again + test:
   ```powershell
   powershell -File ..\scripts\sync_env.ps1
   .\.venv\Scripts\python.exe -m mahika.cli telegram-test
   ```

---

## Part B — SMS → Telegram forward (Android, 10 min)

Amazon OTP SMS must reach your Telegram bot. Pick one:

### Option 1 — MacroDroid (easiest)

1. Install **MacroDroid** from Play Store  
2. New macro → **Trigger: SMS Received**  
   - Sender contains: `AMAZON` or `57575022` (Amazon short code)  
3. **Action: HTTP Request** OR use **Telegram Bot** plugin if installed  
   - Simpler: **Action → Send SMS** won't work — use **Webhook** or third-party  
4. **Easiest path:** Install app **"SMS Forwarder"** (Play Store)  
   - Forward to: your Telegram bot via **IFTTT** or **Tasker + Telegram plugin**

### Option 2 — Tasker + Telegram (reliable)

1. Tasker profile: Event → Phone → Received Text  
   - Sender: `57575022` OR content contains `Amazon` / `OTP`  
2. Task → Plugin → **Telegram Send Message** (Join or Telegram Bot API)  
   - Message: `%SMSRB` (full SMS body)  
   - Chat ID: your `MAHIKA_TELEGRAM_CHAT_ID`

### Option 3 — Manual (testing)

When OTP arrives, message the bot with **only the 6 digits** (e.g. `847291`). Full SMS also works.

**Automated login:** Mahika waits 5×1 minute on Telegram; if no code, clicks **Didn't receive OTP** → voice call to phone ending **711** (override: `AMAZON_OTP_PHONE_SUFFIX` in `.env`).  
Mahika will still auto-read it — no typing in browser.

**Test parser:**
```powershell
.\.venv\Scripts\python.exe -m mahika.cli otp-test
```

**Test live:** Forward a message like `123456 is your Amazon OTP` to your bot.

---

## Part C — Seller credentials in `.env`

Root `.env` (synced to `agent/.env`):
```
AMAZON_SELLER_EMAIL=your@email.com
AMAZON_SELLER_PASSWORD=your_password
MAHIKA_TELEGRAM_BOT_TOKEN=...
MAHIKA_TELEGRAM_CHAT_ID=...
```

```powershell
powershell -File scripts\sync_env.ps1
```

---

## Part D — Run login (cookies saved)

```powershell
cd agent
scripts\seller_login.bat
```

What happens:
1. Playwright opens Seller Central  
2. Email + password from `.env`  
3. **"Don't ask for codes on this device"** auto-ticked on OTP screen  
4. OTP read from Telegram → auto-filled  
5. Cookies saved to `data/mahika/sessions/seller_central_cookies.json`

**Verify session later:**
```powershell
.\.venv\Scripts\python.exe -m mahika.cli session-check
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| OTP not auto-filling | Send 6 digits to bot in **private chat**; run `telegram-chatid` + `otp-test` |
| Wrong password | Update `AMAZON_SELLER_PASSWORD` in root `.env`, sync |
| Session expired | Re-run `seller-login` |
| Telegram empty | `telegram-chatid` after messaging bot |
