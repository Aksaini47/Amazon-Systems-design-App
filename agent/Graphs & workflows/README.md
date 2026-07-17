# Graphs & workflows

Canonical Mahika flow docs. `.claude/skills/` and `AGENTS.md` link here.

## Active workflows

| Folder | Files | Topic |
|--------|-------|--------|
| [seller-central-login/](seller-central-login/) | `FLOW.md`, `GRAPHIFY.md` | Login, OTP, Call 711, S7 |
| [create-seller-support-case/](create-seller-support-case/) | `FLOW.md`, `FORM.md`, `BROWSER.md`, `GRAPHIFY.md` | Case Log path D, SP-API text |
| [seller-reports/](seller-reports/) | `GUIDE.md` | Manual report download + analyze |
| [bulk-listing-create/](bulk-listing-create/) | `FLOW.md`, `GRAPHIFY.md` | PHONE_ACCESSORY template cols, C/L dropdowns, bulk upload, stock match gaps |

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
```

Test-only login reset: `seller-login --fresh`

## Graphify

```powershell
cd "C:\Projects\Amazon Systems Design"
# /graphify agent
```

Output: repo-root `graphify-out/` (gitignored).
