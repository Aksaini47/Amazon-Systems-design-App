---
name: create-seller-support-case
description: Create an Amazon seller / SP-API support case after login (Case Log). Use when running `mahika.cli support-case`, filing an SP-API production case, or working through the Develop Apps / SPP support-case flow.
---

# Create seller support case (Case Log)

**Prerequisite:** `python -m mahika.cli seller-login` OK (cookies saved)  
**Command:** `python -m mahika.cli support-case`  
**Account:** Badeja Enterprises → India (S7 — same as login)  
**Full tree:** `agent/Graphs & workflows/create-seller-support-case/FLOW.md`

## Quick flow

1. Load cookies → re-login only if session expired  
2. S7 Badeja → India  
3. Case Log: Develop Apps → SPP **or** developer.amazonservices.com/support **or** direct `/support/cases`  
4. Fill SP-API production case (Mahika V1 defaults)  
5. Default: **review 120s** — use `--submit` to auto-send  

## Visible browser (teach / manual)

**Sir sikhata hai:** `agent/Graphs & workflows/create-seller-support-case/BROWSER.md`  
**OTP:** `python -m mahika.cli otp-watch` → `data/mahika/sessions/cursor_otp.txt` (filename is legacy — path is still live, see `agent/src/mahika/cli.py:645`)  
**Browser:** Browser pane (`mcp__Claude_Browser__*`) or Claude in Chrome (`mcp__claude-in-chrome__*`) — Sir must see the window  
**Not:** Playwright Chromium for this lane unless Sir asks

## Code (automation lane)

- `agent/src/mahika/playwright/support_case_flow.py`
- Legacy: `agent/scripts/raise_sp_api_production_case.py`
