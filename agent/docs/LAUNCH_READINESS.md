# Mahika launch readiness gate

**Sir runs this before flipping `MAHIKA_MODE=live`.**

## Pre-flight (automated)

```powershell
cd "C:\Projects\Amazon Systems Design\agent"
scripts\quick_verify.bat
```

Target: doctor all green; smokes 4/4 when DB is wired.

## Checklist

| # | Gate | Required for shadow | Required for live |
|---|------|---------------------|-------------------|
| 1 | `MAHIKA_STORAGE_ROOT` points to `data/mahika` | Yes | Yes |
| 2 | Postgres migrated | Yes | Yes |
| 3 | Seller Central cookies fresh | Yes | Yes |
| 4 | SP-API creds in `.env` | No (polling optional) | Yes |
| 5 | Evidence pipeline | OK | OK — human verdict from app |
| 6 | Chromium | OK | OK |
| 7 | Cockpit token set | Recommended | Yes |
| 8 | Telegram wired | Recommended | Yes (OTP + alerts) |
| 9 | Phase 5 selectors | Partial OK in shadow | All steps verified |
| 10 | Shadow week complete | N/A | Yes (Phase 7) |

## Doctor snapshot (expected after Sir fills `.env`)

| Section | Shadow | Live |
|---------|--------|------|
| Config + `.env` | PASS | PASS |
| Python deps | PASS | PASS |
| Postgres + schema | PASS | PASS |
| NVMe folders | PASS | PASS |
| Evidence pipeline | PASS (no Tesseract) | PASS |
| Chromium | PASS | PASS |
| Cockpit token | PASS when set | PASS |
| SP-API | WARN until filled | PASS |
| Telegram | WARN until filled | PASS |
| Heartbeat | PASS | PASS |

## Phase 5 — wizard selectors

Wizard screenshots live at:

```
data/mahika/screenshots/wizard/step4_postaccount.png … step10_Review.png
```

Wire remaining `TODO(codegen)` in `selectors.py` before live filing.

## Go / no-go

- **Shadow OK:** doctor pass (DB + storage + Chromium), cookies present, `MAHIKA_MODE=shadow`
- **Live NO-GO until:** shadow week done, selectors verified, Telegram + cockpit ready

See also: `docs/SETUP_QUICK.md`, `docs/RUNBOOK.md`
