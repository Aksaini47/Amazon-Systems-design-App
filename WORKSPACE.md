# Amazon Systems Design — workspace map

Sir ka ek folder, **teen alag projects** + shared runtime data.

```
Amazon Systems Design/
├── specs/                 # Mahika authority docs (master plan, persona, protocol)
├── agent/                 # Mahika Python agent (git: mahika-agent)
├── data/mahika/           # RUNTIME only — orders, cookies, wizard screenshots (NOT code)
├── app/                   # RF Logger Flutter (capture app)
├── backend/               # Legacy Node API + SP-API sync
├── dashboard/             # Legacy Next.js ops UI
├── catalog-builder/       # Amazon listing + carousel tool (Vite, local IndexedDB)
├── graphify-out/          # Knowledge graph (graphify)
├── .env                   # Secrets (gitignored)
└── FINISH_GUIDE.md        # Camera app handover
```

---

## 1. Mahika (Project Alpha) — SAFE-T agent

| What | Path |
|------|------|
| Code | `agent/` |
| Specs | `specs/mahika_capture_specs.md`, `mahika.md`, `mahika_pipeline_protocol.md` |
| Evidence + sessions | `data/mahika/orders/`, `data/mahika/sessions/` |
| Wizard captures | `data/mahika/screenshots/wizard/` |

**Important:** `data/mahika/` = NVMe data (pehle `Mahika/` ya `D:/Mahika`). Agent `.env` mein `MAHIKA_STORAGE_ROOT` yahi point kare.

**Phase status (May 2026):** Phases 1–4, 6 built; Phase 5 Playwright ~70%; Phase 7 shadow not started.

---

## 2. RepairFully Camera App — evidence capture

| Layer | Path | Role |
|-------|------|------|
| Mobile | `app/` | PK/RT video, verdict, 407-* naming |
| Backend | `backend/` | Upload, SP-API cron, SQLite |
| Dashboard | `dashboard/` | Orders / returns / FBA UI |

Git repo: `Amazon-Systems-design-App` (root). Mobile folder repo mein `mobile/` tha; ab disk pe `app/` — same app.

**Target architecture (Mahika spec):** phone → `data/mahika/orders/` direct. Abhi legacy backend sync bhi chal sakta hai.

---

## 3. Catalog & Store Builder — listings (alag product)

| Path | `catalog-builder/` |
| Stack | Vite + React + Dexie (browser-only, no backend) |
| Use | SKU catalog, listing copy, 9-slot carousel, bulk flat file export |

**Not** Mahika. Amazon India generic parts listings ke liye. Run: `cd catalog-builder && npm install && npm run dev`

Reports/scripts: `catalog-builder/amazon-reports/`

---

## Quick commands

```powershell
# 1. Fill root .env, sync to agent + backend:
powershell -ExecutionPolicy Bypass -File scripts\sync_env.ps1

# 2. Mahika setup (venv + Chromium):
cd agent
scripts\quick_setup.bat

# 3. Verify (after DB credentials filled):
scripts\quick_verify.bat
```

---

## Recovery notes (post folder crisis)

- Agent code: `agent/` (GitHub `Aksaini47/mahika-agent`)
- Specs: `specs/` (restored from backup copies)
- Runtime evidence: `data/mahika/` (orders + Seller Central session)
- Uncommitted agent docs (LAUNCH_READINESS, Telegram setup) — re-create from chat if missing from GitHub
