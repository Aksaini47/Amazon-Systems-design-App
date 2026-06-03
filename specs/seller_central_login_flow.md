# Seller Central login flow (Mahika / arunsaini416)

**Account:** `arunsaini416@gmail.com` (sub-user, OTP via Telegram `@mahika_arun_bot`)

## Browser lanes

| Use | Tool |
|-----|------|
| **Sir-driven login test (default)** | **Cursor built-in browser** — agent `cursor-ide-browser` MCP + `mahika.cli otp-watch` |
| Cookies export / headless automation | **Playwright Chromium** (`mahika.cli seller-login`) |
| SP-API case, SAFE-T filing (after cookies) | Playwright Chromium |

Cookies file: `data/mahika/sessions/seller_central_cookies.json` — load **before** first navigation.

## Rule: already logged in → click through until OTP

Amazon often skips the email form when cookies exist and shows:

1. **Account picker** — saved account `arunsaini416@gmail.com`
2. **Continue** — confirm that account
3. **Password** (sometimes skipped if session fresh)
4. **OTP** — SMS to phone ending **503** → forward full SMS to Telegram bot

**Do not** treat account-picker as "cookies expired". Use `advance_signin_until_otp_or_home()` in `mahika.playwright.amazon_signin_flow` to:

- Click the account row matching `AMAZON_SELLER_EMAIL`
- Click **Continue** / **Sign in** on each intermediate screen
- Stop only when **OTP input** appears or **Seller Central home** loads

## OTP scenarios + rules (editable)

**Sir-maintained rule list:** `.cursor/rules/seller-central-login.mdc` (alwaysApply)

| Scenario | When | Picker action | After OTP sent |
|----------|------|---------------|----------------|
| 1 Ideal | Email/password or account picker → OTP | Default radio + **Send OTP** once (no Call 711) | S4: wait Telegram **3×60s** — **no WhatsApp re-select** |
| 2 Busy | **3×60s** no OTP | Didn't receive → **Call …711** → Send OTP | S4 again, **3×60s** |
| 3 Shortcut | Reopen on OTP phase (saved cookies OK) | **Call …711** → Send OTP only if on S3 picker | S4, **3×60s** |

**Normal login:** `python -m mahika.cli seller-login` — loads `seller_central_cookies.json`, keeps browser cache.  
**Test-only reset:** `--fresh` — clears cookies + profile (debugging wrong screens only).

## Standard path (no saved session)

| Step | Screen | Action |
|------|--------|--------|
| 1 | Sign in | Fill email → **Continue** |
| 2 | Password | Fill password → **Sign in** |
| 3 | OTP | Tick trust device → enter OTP from Telegram |
| 4 | S7 Account switcher | Auto: **Badeja Enterprises → India → Select account** (after OTP) |
| 5 | Home | Cookies saved — login complete |

## Code entry points

| Command | Purpose |
|---------|---------|
| `python -m mahika.cli seller-login` | Save cookies after login |
| `python scripts/raise_sp_api_production_case.py` | Login + SP-API support case |

## SP-API production case (after login)

1. Badeja India context: `?mons_sel_dir_paid=amzn1.pa.d.AB5ZXZYCP3XOLA6T5BVNPV2EXP6A`
2. **Apps and Services → Develop Apps** or `developer.amazonservices.com/support`
3. Case: Developer Profile approval + Production app for Mahika V1

## Graphify tags

`login-flow`, `account-picker`, `otp-telegram`, `seller-central`, `sp-api-production-case`
