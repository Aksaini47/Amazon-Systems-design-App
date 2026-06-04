# Mahika changelog

All notable build-side changes to the Mahika agent. Operational events
(scheduler runs, claim filings, mode flips) live in the `audit_log` table
in Postgres, not here. This file tracks the code itself.

Versioning is per-commit; no semver until Phase 7c (full live) lands.

---

## [unreleased]

### Added
- `mahika.cli doctor` — 10-check self-diagnostic Sir runs before launch. Reports
  config gaps, missing deps, DB connectivity, NVMe folders, Tesseract status,
  Chromium availability, cockpit token, SP-API credentials, Telegram bot,
  heartbeat round-trip. Returns exit 0 only when all critical checks pass.
- `mahika.cli mode <shadow|manual|live|paused>` — ergonomic mode flip with
  audit_log entry. Writes the new mode to `.env`, instructs Sir to restart the
  scheduler. Live-mode flip prints an extra warning about autonomous filing.
- `tests/run_all.py` — single-command runner for all four phase smoke tests
  with structured pass/fail summary + duration.

### Changed
- `file_queued_batch()` now skips claim IDs already attempted in the current
  scheduler tick — prevents a single transient failure (e.g. NoSessionAvailable)
  from burning through `max_claims=5` retries against the same claim in seconds.
  Retry now waits for the next 30-minute scheduler tick.

---

## a037068 — 2026-05-18

### Added
- **`docs/RUNBOOK.md`** — 220-line operational guide for Sir. Phase 7a launch
  checklist, day-to-day ops, mode flip, 8 named failure modes with first-check
  responses, weekly Insights review workflow, manual quarterly backup discipline.
- **`mahika.cli process <order_id>`** subcommand — manual Phase 3 evidence
  pipeline trigger with `--no-db` dry-run flag. Useful for backfill + debug.
- **`scripts/codegen_helper.bat`** — one-click Playwright codegen launcher
  pre-pointed at Seller Central for selector capture.
- `pipeline.processed` audit_log event emitted at end of Phase 3 processing
  with full payload (verdict, scores, FPC codes, OCR availability). Insights
  Engine queries depend on this event existing.

### Changed
- `README.md` full refresh — Phase-1-only status table replaced with 6-phase
  status board, full directory layout, commands cheatsheet, locked storage
  policy ("all evidence on NVMe forever, no cloud backup").
- `pyproject.toml`:
  - `opencv-python` → `opencv-python-headless` (matches installed wheel)
  - Added `numpy>=1.26`, `python-multipart>=0.0.9`, `itsdangerous>=2.0,<3.0`

### Fixed
- **[BUG]** Phase 5 `safe_t_filer` opened a HEADED Chromium during smoke tests
  + first-boot because `session.get_authenticated_context()` had no guard
  against missing cookies in non-live modes. The headed-browser flow was meant
  to fire ONLY when cookies had expired in live mode. Added `NoSessionAvailable`
  exception path: scheduler skips with `claim.filing_skipped` audit event when
  no cookies AND mode != 'live'. Smoke tests + first-boot no longer block.

### Verified
- Phase 3 smoke: 3/3 verdict scenarios pass
- Phase 4 smoke: 5/5 state transitions pass (was hanging before fix)
- Phase 5 smoke: 6/6 templates + Chromium wiring pass
- Phase 6 smoke: 17/17 cockpit auth + pages + suggestion approval pass

---

## 02b4885 — 2026-05-18 (initial)

### Added — Phases 1, 3, 4, 5, 6 (full build)

**Phase 1 — Foundation**
- Postgres schema (9 tables, court-grade audit_log + state ENUMs)
- SQLAlchemy engine + idempotent SQL migration runner
- `pydantic-settings` config layer (`.env` loaded once at boot)
- Heartbeat service (single-active-runner enforcement)
- Oracle VM runbook (`scripts/setup_oracle_vm.md`)
- SP-API registration checklist (`scripts/sp_api_registration_checklist.md`)
- NVMe folder bootstrap (`scripts/setup_nvme_folders.py`)
- Verified end-to-end against Oracle Mumbai Postgres 16.14

**Phase 3 — Evidence Processing**
- OCR (Tesseract with graceful binary-missing fallback)
- 4-layer diff detector (SSIM + ORB + HSV histogram + OCR FPC compare)
- Verdict suggestion engine with FPC-mismatch override (spec §8.3)
- Single-composite generator (2400×3000 px, 2×2 grid + header + footer +
  Mahika watermark, JPEG 85%)
- `pipeline.process_order()` orchestrator + meta.json + DB persistence

**Phase 4 — Mahika Core**
- Court-grade audit helper (raises `AuditFailure` → hard stop)
- Telegram notifier (4 priorities + anti-spam with escalation bypass +
  MarkdownV2 + stderr fallback)
- Claim queue with SAFE-T window enforcement + FIFO + attempt backoff
- SP-API refund-event watcher (graceful library-missing fallback + dedup)
- Returns scanner with unmatched-return alarms
- Weekly Insights Engine (4 pattern queries + suggestion synthesis with
  Sir-approval gate)
- APScheduler wiring with mode + heartbeat guards + crash audit

**Phase 5 — Playwright SAFE-T**
- English claim message templates (spec §9.4 v1)
- Centralized Seller Central selectors with `TODO(codegen)` markers
- Session manager with cookie persistence + headed-browser OTP fallback
- Claim filer with 3-step screenshot audit trail
- Status checker with state-aware Telegram routing
- Mode-aware filing: shadow runs form-fill without submit, live submits

**Phase 6 — Cockpit**
- FastAPI + Jinja2 dashboard
- Single-user token auth with HMAC-signed session cookies (`itsdangerous`)
- 127.0.0.1-only safety check in CLI
- Urgency-coloured worklist with SAFE-T countdown
- Audit log browser with type/order filters
- Insights review with Sir approve/reject flow

**Smoke tests** (verified end-to-end):
- Phase 3: 3/3 verdict scenarios
- Phase 4: 5/5 state transitions
- Phase 5: 6/6 templates + Chromium
- Phase 6: 17/17 auth + pages

### Forbidden behaviors enforced at code level (per `mahika.md` §9)
- SP-API client is read-only (no refund creation, no listing edits)
- `claim_queue.enqueue()` refuses without composite + open SAFE-T window
- `audit()` raises `AuditFailure` (hard stop, never proceed un-audited)
- Insights suggestions land in 'pending' status; cockpit decision is the only
  path to 'approved'
- Cockpit refuses `0.0.0.0` bind without explicit `--force-public`
