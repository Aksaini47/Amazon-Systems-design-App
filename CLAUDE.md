# Amazon Systems Design (Mahika) — project rules

Global rules live in `~/.claude/CLAUDE.md`. This file carries what is specific to this workspace.

## Communication style (Sir)

Write like a helpful colleague, not a textbook.

**Default shape:**

1. **Ho chuka** — 2–4 bullets, facts only
2. **Ab kya** — numbered steps, max 3–5
3. **Kaise** — one line or a tiny table; optional "detail chahiye?" at the end

- Keep replies **short**. Big tables/diagrams only when Sir asks, or when the task is architecture.
- **Simple Hindi-English mix** is fine. Avoid heavy jargon; explain once if needed.
- No long preambles, no repeating the question, no engagement bait.
- Code changes: say **what changed + why** in plain words.
- If blocked: say **exactly what Sir must do** (one action).
- Don't re-explain Mahika architecture unless asked.

## Browser — must be visible (never headless, never external Chrome)

Sir uses the **in-editor browser only** for Seller Central discovery. This rule survived the Cursor migration; only the mechanism changed.

- Use the **Browser pane** (`mcp__Claude_Browser__*`) or **Claude in Chrome** (`mcp__claude-in-chrome__*`) — Sir must be able to **see** the window.
- **Never** run `mahika.cli seller-login` / `support-case` in a background shell during testing — Sir must watch it.
- **Never** `Start-Process` an external Chrome for login tests unless Sir explicitly says external is OK.
- Amazon sign-in URL: `https://sellercentral.amazon.in/signin?ref_=INscwp_signin_n&mons_sel_locale=en_IN&ld=SCINWPDirect` — **not** bare `/ap/signin` (404).
- Continue button: the DOM is `input#continue`, not a `button`. If a click fails, use `form.requestSubmit()` via the JS tool.

*Cursor's Glass-browser troubleshooting (`Ctrl+Shift+B`, `glass-browser-*` viewIds, WebView mount bug) no longer applies — that rule is archived at `C:\CursorArchive\backup\dot-cursor\`.*

## Skills

| Skill | Use for |
|---|---|
| `seller-central-login` | Login flow, screen map S1–S7, 60s cooldown (R8), 3 OTP scenarios, Telegram relay |
| `create-seller-support-case` | SP-API / seller support case after login |
| `shorebird-release` | RF Logger patch vs release, `--no-tree-shake-icons`, ship.ps1 |

Full flow trees live under `agent/Graphs & workflows/`.

## Quick facts

- **Login command:** `python -m mahika.cli seller-login` — keep cookies; `--fresh` is for test/debug only.
- **Account switcher (S7):** Badeja Enterprises → India → Select account.
- **Never** re-click WhatsApp on S4, and never Send OTP twice inside 60s.

## Cursor history

15 Cursor conversations for this project are in `.claude/cursor-history/` (see `INDEX.md`). Reference material, not live instructions.
