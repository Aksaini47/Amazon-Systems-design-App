# Graphs & workflows (Mahika agent)

Canonical diagrams for Seller Central login and related automation.  
**Source of truth** for flow graphs — specs and `.cursor/rules` link here.

| Folder | Topic |
|--------|--------|
| [seller-central-login/](seller-central-login/) | Login, OTP, Call 711, account switcher |
| [create-seller-support-case/](create-seller-support-case/) | Case Log — SP-API / seller support case |
| [create-seller-support-case/CURSOR_BROWSER_TEACH.md](create-seller-support-case/CURSOR_BROWSER_TEACH.md) | **Cursor browser** — login + Case Log (Sir teaches) |

## Commands

```powershell
cd agent
.\.venv\Scripts\python.exe -m mahika.cli seller-login
```

Test-only reset: `--fresh`

```powershell
# After login:
.\.venv\Scripts\python.exe -m mahika.cli support-case
.\.venv\Scripts\python.exe -m mahika.cli support-case --submit
```

## Graphify

Regenerate from repo root (scope `agent/` — code + workflow docs):

```powershell
cd "C:\Projects\Amazon Systems Design"
# /graphify agent
```

Output: `graphify-out/` at repo root (gitignored). Indexes: `*/GRAPHIFY.md` in each workflow folder.
