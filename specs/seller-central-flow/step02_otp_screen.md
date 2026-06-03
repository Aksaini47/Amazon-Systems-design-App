# Step 2 — Two-Step Verification (OTP)

**URL:** https://sellercentral.amazon.in/ap/mfa  
**Phone hint:** ending in **711**

## Screen A — OTP delivery picker (before OTP box)

**When SMS to …711 fails**, Amazon shows radio list + **Send OTP**.

| # | Option | Mahika picks |
|---|--------|--------------|
| 1 | WhatsApp …711 | no |
| 2 | **Call me …711** | **yes** → then **Send OTP** |
| 3–5 | …013 variants | no |

**Scenario 1 (ideal):** default option + Send OTP → `run_otp_phase(scenario=1)` in `seller_login.py`  
**Scenario 2 (busy):** 3×60s fail → Didn't receive → Call …711 → Send OTP → wait again  
**Scenario 3 (shortcut):** already on picker → Call …711 → `run_otp_phase(scenario=3)`  
Always: tick **Don't ask for codes on this device** on OTP entry screen.

## Screen B — OTP entry (after Send OTP)

| Element | Label | Notes |
|---------|-------|-------|
| OTP input | Enter OTP: | single textbox |
| Trust device | Don't ask for codes on this device | checkbox — **tick for 7–14 day session** |
| Sign in | button | submit OTP |
| Resend | Didn't receive the OTP? | link |
| WhatsApp fallback | Send OTP to WhatsApp | optional |

## Flow edge

```
PasswordEntry --valid_password--> MFA_OTP
MFA_OTP --requires--> SMS_OTP_or_WhatsApp
MFA_OTP --trust_device_checked--> LongLivedSession
MFA_OTP --submit--> SellerCentralHome
```

## Mahika automation link (INFERRED)

- Playwright: 3×60s Telegram OTP wait → then click **Didn't receive the OTP?** → voice call **…711** → submit
- Sir receives call, sends 6-digit code to `@mahika_arun_bot`
- Env override: `AMAZON_OTP_PHONE_SUFFIX=711`

## Playwright selectors (from agent code)

- `#auth-mfa-otpcode` or `input[name=otpCode]`
- `#auth-signin-button` for submit
