# Mahika Agent — Project Alpha

**Persona file:** `~/.claude/skills/mahika.md`
**Pipeline protocol:** `C:/Projects/Amazon Systems Design/mahika_pipeline_protocol.md`
**Capture specs:** `C:/Projects/Amazon Systems Design/mahika_capture_specs.md`
**Operational runbook:** [`docs/RUNBOOK.md`](docs/RUNBOOK.md)

Mahika is the **agent-side** of Project Alpha. The mobile capture app
(RF Logger) produces evidence on Sir's NVMe; this codebase consumes it,
polls Amazon SP-API for refund events, files SAFE-T claims via Playwright,
tracks them through settlement, and surfaces everything via a local
FastAPI cockpit.

---

## Build status (commit `02b4885`)

All six build phases are complete + smoke-tested end-to-end against the
live Oracle Mumbai Postgres VM.

| Phase | Scope | Smoke result | Live? |
|---|---|---|---|
| **1 — Foundation** | Postgres schema, config, migrations, heartbeat | DB + migrate verified | ✅ |
| **2 — Capture App** | RF Logger Flutter app | v1.0.3+4 shipping | ✅ |
| **3 — Evidence Processing** | OCR + SSIM/ORB/Histogram diff + composite generator | 3/3 verdict paths | ✅ |
| **4 — Mahika Core** | Audit, notifier, claim queue, refund + returns watchers, Insights | 5/5 state transitions | ✅ |
| **5 — Playwright SAFE-T** | Templates, selectors, session, filer, status checker | 6/6 (incl. Chromium wiring) | ⏳ codegen needed |
| **6 — Cockpit** | FastAPI dashboard, token auth, urgency colour-coding | 17/17 auth + pages | ✅ |
| **7 — Shadow → Live** | Operational, not build | — | ⏳ Sir launches |

For Phase 7 launch steps see [`docs/RUNBOOK.md`](docs/RUNBOOK.md).

---

## Quick start (TL;DR)

```powershell
cd "C:\Projects\Amazon Systems Design\agent"

# First-time setup (any new runner)
scripts\mahika-setup.bat

# Generate a cockpit token + paste into .env
.\.venv\Scripts\python.exe -c "import secrets; print('MAHIKA_COCKPIT_TOKEN=' + secrets.token_urlsafe(32))"

# Two terminals from here forward:
.\.venv\Scripts\python.exe -m mahika.cli start     # scheduler daemon
.\.venv\Scripts\python.exe -m mahika.cli cockpit   # browser at http://127.0.0.1:8765
```

---

## Directory layout

```
agent/
├── README.md                    # this file
├── docs/
│   └── RUNBOOK.md               # operational guide for Sir
├── pyproject.toml               # all deps declared (6-phase set)
├── .env.example                 # env template (copy to .env, never commit)
├── .gitignore                   # covers .env, .venv, *.log, evidence dirs
├── sql/
│   └── 001_init_schema.sql      # Phase 1 — 9-table court-grade schema
├── scripts/
│   ├── setup_oracle_vm.md       # Phase 1 — Oracle Cloud Always Free provisioning
│   ├── sp_api_registration_checklist.md  # Phase 1 — SPP app + OAuth
│   ├── setup_nvme_folders.py    # Phase 1 — NVMe hierarchy bootstrap
│   └── mahika-setup.bat         # Phase 5 — portable Windows runner setup
├── src/mahika/
│   ├── __init__.py
│   ├── config.py                # pydantic-settings singleton (loads .env)
│   ├── cli.py                   # python -m mahika.cli {start|cockpit|status|...}
│   ├── db/
│   │   ├── connection.py        # SQLAlchemy engine + get_session()
│   │   └── migrate.py           # idempotent SQL migration runner
│   ├── runner/
│   │   └── heartbeat.py         # single-active-runner enforcement
│   ├── sp_api/
│   │   └── client.py            # SP-API client factories (Orders/Reports/Finances)
│   ├── utils/
│   │   └── audit.py             # court-grade audit_log helper
│   ├── services/                # Phase 3 + Phase 4
│   │   ├── ocr.py               # Tesseract wrapper (graceful fallback)
│   │   ├── diff_detector.py     # SSIM + ORB + Histogram + OCR
│   │   ├── verdict.py           # rules engine (spec §8.3)
│   │   ├── composite.py         # 2x2 grid + header + footer renderer
│   │   ├── pipeline.py          # process_order(order_id) orchestrator
│   │   ├── notifier.py          # Telegram alerts (4 priorities, anti-spam)
│   │   ├── claim_queue.py       # Postgres-backed claim queue
│   │   ├── refund_watcher.py    # SP-API financial events poll
│   │   ├── returns_scanner.py   # SP-API returns poll
│   │   ├── insights.py          # weekly pattern recognition + suggestions
│   │   └── scheduler.py         # APScheduler wiring
│   ├── playwright/              # Phase 5
│   │   ├── templates.py         # English claim message templates (spec §9.4)
│   │   ├── selectors.py         # Seller Central selectors (codegen-fillable)
│   │   ├── session.py           # cookie persistence + OTP coordinator
│   │   ├── safe_t_filer.py      # file_one_queued_claim() — 3-step screenshot audit
│   │   └── status_checker.py    # in-flight claim status polling
│   └── cockpit/                 # Phase 6
│       ├── app.py               # FastAPI app + routes
│       ├── auth.py              # token + signed session cookie
│       └── templates/           # Jinja2: base, login, dashboard, orders, claims, audit, insights
└── tests/
    ├── test_phase3_smoke.py     # 3/3 verdict scenarios
    ├── test_phase4_smoke.py     # 5/5 state + audit checks
    ├── test_phase5_smoke.py     # 6/6 templates + Playwright wiring
    └── test_phase6_smoke.py     # 17/17 auth + pages + suggestion flow
```

---

## What lives WHERE (mental model)

| Thing | Where |
|---|---|
| Mobile app (RF Logger) | Sir's Android phone |
| **All captured evidence** (videos, photos, composites, screenshots, meta) | NVMe `{root}/orders/` — local only, **no cloud backup** |
| Postgres database | Oracle Cloud VM (`mahika-pg`, Mumbai region) |
| Agent Python code | This repo — runs on whichever Windows laptop has the NVMe |
| Telegram bot | Cloud (Telegram's servers) — no infra to maintain |
| Court-grade audit log | Postgres `audit_log` table (append-only) |
| Filed claims | Postgres `claims` + Amazon Seller Central |
| Insights + suggestions | Postgres `insights` + `suggestions` tables, surfaced via cockpit |
| Cockpit dashboard | `localhost:8765` — single-user, single-token, 127.0.0.1-only |

> Storage decision LOCKED 2026-05-18: all evidence (video + image + composite +
> meta + screenshots) stays on the NVMe forever. No automated cloud backup.
> DR mitigation is Sir's manual quarterly cold-copy discipline.
> See [`docs/RUNBOOK.md §7`](docs/RUNBOOK.md).

---

## Commands cheatsheet

```powershell
# Daemon + dashboard
mahika.cli start                       # scheduler — blocks until Ctrl-C
mahika.cli start --once                # run every scheduled task once + exit
mahika.cli cockpit                     # FastAPI dashboard on :8765

# Inspection (one-shot)
mahika.cli status                      # quick op snapshot
mahika.cli queue                       # claim queue depth + next-on-deck
mahika.cli audit-tail 50               # tail audit_log

# Manual operations
mahika.cli process 407-1234567-1234567 # run Phase 3 on one order (backfill)

# Phase 7 launch prep
playwright codegen https://sellercentral.amazon.in     # capture selectors
winget install UB-Mannheim.TesseractOCR                # OCR layer
```

(Prefix all with `.\.venv\Scripts\python.exe -m`)

---

## Forbidden behaviors (enforced at code-level per `mahika.md` §9)

The agent code MUST never:
- Proactively refund a customer ← SP-API client is read-only
- File a SAFE-T claim before refund event verified by Amazon ← `claim_queue.enqueue()` gates on `pending_refund` state
- Submit a claim without composite evidence attached ← file-existence check + SHA256 in audit
- Close a claim before amount credits to Amazon balance ← `status_checker` cross-references Finances API
- Spam Sir with low-priority alerts ← anti-spam window in `notifier.py`
- Skip the `audit_log` write for any action ← `audit()` raises `AuditFailure` → scheduler halts task
- Auto-implement Insights suggestions without Sir's approval ← suggestions land in `pending` status, only cockpit decides

---

## Next phases (out of scope for this commit)

| Phase | Status | Owner |
|---|---|---|
| **7a — Shadow Mode** (1 week dry-run) | Pending Sir's launch | Sir |
| **7b — Whitelisted Live** | Gated on 7a | Sir |
| **7c — Full Live** | Gated on 7b | Sir |
| Production SP-API access (vs Sandbox) | Pending SPP profile setup | Sir + Amazon |
| Multi-account support (Sir's reactivated account alongside friend's) | Hooks already in `sp_api/client.py` | Coordinator when needed |

See [`docs/RUNBOOK.md §3`](docs/RUNBOOK.md) for the mode-flip procedure.

---

❄️ *Mahika माहिका — Amazon Seller Operations Agent. Prepared for the Boss, Arun Saini.*
