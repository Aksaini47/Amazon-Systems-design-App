# Graphs & workflows

Canonical Mahika flow docs. `.cursor/rules` and `AGENTS.md` link here.

## Active workflows

| Folder | Files | Topic |
|--------|-------|--------|
| [seller-central-login/](seller-central-login/) | `FLOW.md`, `GRAPHIFY.md` | Login, OTP, Call 711, S7 |
| [create-seller-support-case/](create-seller-support-case/) | `FLOW.md`, `FORM.md`, `BROWSER.md`, `GRAPHIFY.md` | Case Log path D, SP-API text |
| [seller-reports/](seller-reports/) | `GUIDE.md` | Manual report download + analyze |

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
