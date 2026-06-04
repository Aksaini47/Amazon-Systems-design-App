# Amazon India Mobile Screen — Bullet Point Best Practices

## Context

Bulk listing file `PHONE_ACCESSORY_FILLED.xlsm` with 1275 SKUs. Need title format and 5 bullet points for Amazon India mobile screen listings.

**Repaired terminology (2026-05-14):**
- Removed "Original" — use only CareOG
- Tier 1 = LCD only (no TFT, Incell, AMOLED naming)
- Tier 2 = OLED only (no AMOLED, Super AMOLED naming)
- NO screen size in title — device data from `gsmarena_website.json`

---

## Corrected 4-Axis Classification

### Axis 1: Screen Tech (SIMPLIFIED)

| Tier | Tech | Devices | Fingerprint |
|------|------|---------|-------------|
| Tier 1 | LCD | Budget/older | Non Fingerprint |
| Tier 2 | OLED | Premium/newer | Fingerprint Supported |

**Eliminated terms:** TFT, Incell, AMOLED, Super AMOLED, Super Retina

### Axis 2: Quality Grade

**Only ONE term:** CareOG

**Eliminated:** Original, Refurbished, OEM

### Axis 3: Fingerprint Compatibility

| Status | Tech | Frame Requirement |
|--------|------|-------------------|
| Non Fingerprint | LCD | No framing needed, standard install |
| Fingerprint Supported | OLED | Must frame during fitting, 1-2 days to adjust |

### Axis 4: Build Variant

| Variant | Description |
|---------|-------------|
| WF / With Frame | Screen pre-pasted on frame, ready to install, colored rims |
| Without Frame | Screen only, requires frame transfer from old screen |

---

## Device Directory Integration

Source: `D:\GSM_ALL\HANDOFF_DEVICE_DIRECTORY\gsmarena_website.json`

**Required fields for each listing:**
- `brand_name` — e.g., "Samsung", "Apple"
- `model_name` — e.g., "Galaxy S24 Ultra"
- `specifications.Misc.Models` — e.g., "SM-S928B, SM-S928B/DS"

**DO NOT include:** screen size anywhere

---

## Title Format (200 chars max)

### Structure
```
[Brand] [Model] [Model Numbers] [Tech] CareOG [Fingerprint] [Build] Replacement Display
```

### Title Examples

**Tier 1 LCD + Non Fingerprint + WF:**
```
Samsung Galaxy A33 5G SM-A336E SM-A336B LCD CareOG Non Fingerprint With Frame Replacement Display
```

**Tier 1 LCD + Non Fingerprint + Without Frame:**
```
Realme C67 SM-C67 LCD CareOG Non Fingerprint Without Frame Replacement Display
```

**Tier 2 OLED + Fingerprint Supported + WF (iPhone):**
```
iPhone 12 A2172 A2402 A2403 A2404 OLED CareOG Fingerprint Supported With Frame Replacement Display
```

**Tier 2 OLED + Fingerprint Supported + WF (Samsung):**
```
Samsung Galaxy S21 SM-G991B SM-G991U OLED CareOG Fingerprint Supported With Frame Replacement Display
```

---

## 5-Bullet Point Structure

### BULLET 1 — COMPATIBILITY (Model Verification)
**Search:** Model numbers, A-codes, SM-codes
**Purpose:** Repair technician verifies exact model

```
Compatible with [Brand] [Model] [Model Numbers] — Check Settings > About for exact Model Number before ordering
```

---

### BULLET 2 — SCREEN TECH + FINGERPRINT (Critical)
**Search:** LCD, OLED, fingerprint, non fingerprint
**Purpose:** Clear fingerprint compatibility — most confusing spec

**For LCD (Non Fingerprint):**
```
[Brand] [Model] LCD Display — Non Fingerprint. LCD screens have no under-display fingerprint sensor. Standard installation, no fingerprint calibration needed.
```

**For OLED (Fingerprint Supported):**
```
[Brand] [Model] OLED Display — Fingerprint Supported. OLED screens support under-display fingerprint but require framing during fitting. Fingerprint takes 1-2 days to adjust after installation and calibration.
```

---

### BULLET 3 — QUALITY GRADE
**Search:** CareOG, quality
**Purpose:** Set expectations, one clear term

```
CareOG Quality — Premium tested display with original chip IC, 100% checked for dead pixels, colour calibration, and touch response before dispatch.
```

---

### BULLET 4 — BUILD VARIANT + INSTALLATION
**Search:** With Frame, WF, Without Frame, adhesive

**With Frame (WF):**
```
With Frame (WF) — Screen pre-pasted on frame, ready to install. Original adhesive pre-applied. Colored frame rims shipped based on availability.
```

**With Frame + Fingerprint:**
```
With Frame (WF) — Pre-framed assembly for fingerprint calibration. Frame transfer not needed. Adhesive included. Professional install recommended for fingerprint setup.
```

**Without Frame:**
```
Without Frame — Screen only. Requires frame transfer from your old screen. Adhesive sheet included. Professional installation recommended.
```

---

### BULLET 5 — WARRANTY + GST + BULK
**Search:** warranty, replacement, GST, bulk, WhatsApp, dispatch

```
Warranty: 30 days replacement — GST invoice available on request — Bulk order pricing on WhatsApp — Order before 2 PM for same day dispatch
```

---

## Title Templates

| Category | Title Template |
|----------|----------------|
| Tier 1 LCD + WF | `[Brand] [Model] [Codes] LCD CareOG Non Fingerprint With Frame Replacement Display` |
| Tier 1 LCD + No Frame | `[Brand] [Model] [Codes] LCD CareOG Non Fingerprint Without Frame Replacement Display` |
| Tier 2 OLED + WF | `[Brand] [Model] [Codes] OLED CareOG Fingerprint Supported With Frame Replacement Display` |

---

## Hinglish Integration

Primary = English. ONE Hinglish term per bullet MAX.

| English | Hinglish |
|---------|----------|
| Display | "sceen" / "dispaly" |
| Broken | "kharab" / "tutta" |
| Repair | "marammat" |
| Replacement | "badli" |
| Verify | "verify karein" |

---

## Compliance Checklist

| Rule | Status |
|------|--------|
| Title max 200 chars | Track manually |
| 5 bullets | ✓ |
| ~200 chars per bullet | ✓ |
| No ALL CAPS | ✓ |
| No Emojis | ✓ |
| No "best" / "number1" / "top-rated" | ✓ |
| No refund language | ✓ |
| Only CareOG quality | ✓ |
| Only LCD + OLED tech | ✓ |
| No screen size in title | ✓ |
| Model numbers in title | ✓ |
| Non Fingerprint clarity | ✓ Bullet 2 |
| Fingerprint framing note | ✓ Bullet 2 + 4 |
| GST mention | ✓ Bullet 5 |

---

## Backend Keywords (200 bytes India MAX)

**STRICT LIMIT:** 1 byte over = Amazon silently de-indexes ALL backend.

### Tier 1 LCD
```
sceen replacement display kharab tutta marammat lcd oem asali mobile repair folder non fingerprint
```

### Tier 2 OLED
```
sceen replacement display kharab tutta marammat oled oem asali mobile repair folder fingerprint support
```

### iPhone
```
apple iphone display sceen replacement a-code lcd oled fingerprint folder marammat mobile repair
```

### Samsung
```
samsung galaxy display sceen replacement sm-code oled lcd fingerprint folder marammat mobile repair
```

---

## Files Created

1. ✓ `amazon-reports/bullet_point_best_practices.md` — This document
2. ✓ `amazon-reports/bullet_point_templates.md` — Ready-to-use templates

---

## Verification

1. Open PHONE_ACCESSORY_FILLED.xlsm
2. Select sample SKUs from each category
3. Check title length (max 200)
4. Check each bullet (max 255)
5. Verify compliance: grep for `BEST|top-rated|Original|Refurbished|OEM|AMOLED|TFT|Incell`
6. Confirm fingerprint in Bullet 2
7. Confirm model numbers from device directory
8. Verify backend keywords < 200 bytes

---

*Terminology corrected per user input — 2026-05-14*
*Device data: D:\GSM_ALL\HANDOFF_DEVICE_DIRECTORY\gsmarena_website.json*
*Domain: amazon-india-mobile-parts skill*