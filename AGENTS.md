# Mahika agent — active goal

**Mode:** `MAHIKA_MODE=manual` (testing — visible browser, Sir can intervene)

## Current goal

**Successful Seller Central login** in **Cursor browser** (side panel, always visible).

- Lane: Cursor `browser_navigate` with `position: "side"` + `newTab: true`
- **Not:** Playwright Chromium in background
- OTP: Telegram `@mahika_arun_bot` (6-digit) + `mahika.cli otp-watch --force`
- After OTP: **Badeja Enterprises → India → Select account**

## Flow reference

- `agent/Graphs & workflows/seller-central-login/FLOW.md`
- `.cursor/rules/seller-central-login.mdc`
- `.cursor/rules/cursor-glass-browser.mdc`

## Success criteria

- URL contains `sellercentral.amazon.in/home` OR account switcher completed → home
- Sir confirms login OK
