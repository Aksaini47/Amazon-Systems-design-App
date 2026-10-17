# Graphs & workflows

Canonical Mahika flow docs. `.claude/skills/` and `AGENTS.md` link here.

## Active workflows

| Folder | Files | Topic |
|--------|-------|--------|
| [seller-central-login/](seller-central-login/) | `FLOW.md`, `GRAPHIFY.md` | Login, OTP, Call 711, S7 |
| [create-seller-support-case/](create-seller-support-case/) | `FLOW.md`, `FORM.md`, `BROWSER.md`, `GRAPHIFY.md` | Case Log path D, SP-API text |
| [seller-reports/](seller-reports/) | `GUIDE.md` | Manual report download + analyze |
| [bulk-listing-create/](bulk-listing-create/) | `FLOW.md`, `GRAPHIFY.md` | PHONE_ACCESSORY template cols, C/L dropdowns, bulk upload, stock match gaps |
| [mahika-ads-flow/](mahika-ads-flow/) | `FLOW.md` (process), `KEYWORD_PATTERNS.md` (content — data-driven positive/negative keyword rules), `SEARCH_TERM_ANALYSIS_2026-07-20.md` + `TOP10_KEYWORD_ANALYSIS_2026-07-20.md` (source analysis) | Which keywords/negatives to use for max ROAS/CTR, min cross-model leakage |
| [mahika-sp-api/](mahika-sp-api/) | `FLOW.md`, `GRAPHIFY.md` | SP-API sandbox/production setup, LWA creds, probe, env sync |

## Status snapshots

| File | Covers |
|--------|--------|
| [PROGRESS_2026-07-17.md](PROGRESS_2026-07-17.md) | Snapshot — **superseded in 4 places**, see below |
| [CHAT_MIGRATION_ANALYSIS_2026-07-17.md](CHAT_MIGRATION_ANALYSIS_2026-07-17.md) | Cursor chat migration analysis + disk-verified state. **Batch 50001020639 verified FAILED (0/25 live).** Read this before trusting the snapshot above. |

## Commands

```powershell
cd agent
.\.venv\Scripts\python.exe -m mahika.cli seller-login          # cookies save
.\.venv\Scripts\python.exe -m mahika.cli support-case          # after login
.\.venv\Scripts\python.exe -m mahika.cli reports analyze       # reports lane
.\.venv\Scripts\python.exe -m mahika.cli sp-api status          # SP-API wiring check
.\.venv\Scripts\python.exe -m mahika.cli sp-api probe           # full endpoint matrix
```

Test-only login reset: `seller-login --fresh`

## Graphify

```powershell
cd "C:\Projects\Amazon Systems Design"
# /graphify agent
```

Output: repo-root `graphify-out/` (gitignored).
