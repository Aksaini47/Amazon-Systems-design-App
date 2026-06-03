# Step 0b — Saved account picker (cookies present)

**When:** Playwright Chromium loads `seller_central_cookies.json` before navigation.

**Screen:** Amazon shows saved account `arunsaini416@gmail.com` — NOT the empty email form.

## Actions (automation)

1. `load_cookies(context)` **before** `page.goto`
2. `advance_signin_until_otp_or_home()`:
   - Click **Continue** (yellow) if account pre-selected
   - Else click account row matching email
3. Stop at **OTP** (`#auth-mfa-otpcode`) or **Seller Central home**

## Do NOT

- Open Cursor IDE browser (separate cookie jar)
- Call `#ap_email` wait when picker is showing (causes 30s timeout)
- Label as "cookies expired"

## Tool

Playwright Chromium only — `ensure_seller_session()` in `seller_login.py`
