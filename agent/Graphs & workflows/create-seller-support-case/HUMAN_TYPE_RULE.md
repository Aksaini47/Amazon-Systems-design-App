# Human typing rule (Case Log)

Sir wants **human-style** entry — not paste / not instant fill.

## Copy tone

Plain seller English like Amazon Examples — short sentences, `Seller: …` / `App: …`, **no** jargon (403, LWA, SP-API caps). See [SP_API_CASE_FORM_TEXT.md](SP_API_CASE_FORM_TEXT.md). Variant `1`–`5`.

## Cursor browser

1. **Click** field first (focus).
2. **`browser_type`** with `slowly: true`, `clear: true`.
3. Short pause between fields (~1–2s).
4. **Click** buttons (Continue, chips, tabs) — never only CDP unless iframe blocks refs.

## Iframe (Help Hub wizard)

If refs missing → iframe `[1]` shadow DOM:
- Click **My issue is not listed** via button text match.
- Type in chunks with small delays (human-ish).
- **Do not** use preset issue card radios.

## Automation lane (later)

Playwright: `page.type(selector, text, delay=80)` per character.
