# Mahika agent — active goal

**Mode:** `MAHIKA_MODE=manual` (testing — visible browser, Sir can intervene)

## Current goal

**Successful Seller Central login** in a **visible browser** — Sir must be able to watch it.

- Lane: Browser pane (`mcp__Claude_Browser__*`) or Claude in Chrome (`mcp__claude-in-chrome__*`)
- **Not:** Playwright Chromium in background
- OTP: Telegram `@mahika_arun_bot` (6-digit) + `mahika.cli otp-watch --force`
- After OTP: **Badeja Enterprises → India → Select account**

## Flow reference

- `agent/Graphs & workflows/seller-central-login/FLOW.md`
- `.claude/skills/seller-central-login/SKILL.md`
- `CLAUDE.md` — "Browser — must be visible" section

## Success criteria

- URL contains `sellercentral.amazon.in/home` OR account switcher completed → home
- Sir confirms login OK
