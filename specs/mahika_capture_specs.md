# MAHIKA — CAPTURE SPECIFICATIONS & MASTER PLAN

**File name:** `mahika_capture_specs.md`
**Project:** Project Alpha — Amazon Seller Operations Agent (Mahika माहिका)
**Purpose:** Consolidated technical knowledge base for the capture app, evidence pipeline, and SAFE-T automation flow. This file is Mahika's operational reference for everything related to video/image capture, comparison generation, and storage architecture.

---

## 1. Hardware & Capture Stack

### 1.1 Recording Device
- **Primary:** Smartphone (current Android + future Android upgrades)
- **Rationale:** Mid-range Android phones (Xiaomi, Samsung A-series, OnePlus Nord, Pixel A-series) have camera hardware sufficient for 2K product photography and 1080p HEVC video. No dedicated DSLR or webcam needed.
- **Future-proof:** Capture app must be device-agnostic — any Android phone with API 28+ should work.

### 1.2 Storage Stack
- **Local primary:** 2TB Crucial NVMe SSD (via enclosure on Dell Latitude 5501)
- **No cloud storage** for raw videos (cost analysis confirmed local is cheaper over 3 years)
- **Optional DR:** Last 30 days synced to Google Drive 2TB if Arun chooses (₹650/mo)
- **Database:** Postgres on Oracle Cloud Always Free
- **Evidence composites only:** Cloudflare R2 free tier (10GB free) — small PNGs, optional

### 1.3 Sync Architecture
- **App ↔ PC sync:** Local WiFi via Socket.io or REST API
- **Trigger:** Phone app records → bundle saved locally on phone → auto-sync to PC over LAN → PC server picks up → Mahika processes
- **Fallback:** Manual USB transfer if WiFi fails

---

## 2. Video Capture Specifications (LOCKED)

### 2.1 Video Format
| Parameter | Value | Reason |
|---|---|---|
| **Resolution** | 1080p (1920×1080) | Sweet spot — sharp enough for AI analysis, not bloated |
| **Framerate** | 24 FPS | Cinema standard, sufficient for AI frame extraction, half the storage of 60 FPS |
| **Codec** | H.265 (HEVC) | ~50% smaller than H.264 at same quality |
| **Audio** | OFF | Not needed, saves space, removes privacy concerns |
| **Bitrate** | ~5 Mbps | Balanced quality/size |
| **Container** | .mp4 | Universal compatibility |

### 2.2 Image Capture Format
| Parameter | Value | Reason |
|---|---|---|
| **Resolution** | 2K (~2000×2500 pixels) | More than enough for micro-detail (scratches, FPC codes, mfg serials) |
| **Format** | JPEG @ 90% quality | Compressed without visible loss, smaller than PNG |
| **Color profile** | sRGB | Consistent across devices and uploads |

### 2.3 Comparison Composite Format
| Parameter | Value | Reason |
|---|---|---|
| **Layout** | Side-by-side: PK_front + RT_front, PK_back + RT_back | Standard SAFE-T evidence format |
| **Output resolution** | ~4K canvas (2 × 2K images side-by-side) | Preserves detail of both inputs |
| **Format** | JPEG @ 85% quality | Amazon portal handles JPEG better than PNG; size optimized for upload |
| **Watermark** | Order ID printed on canvas | Authenticity + tracking |

---

## 3. File Size Estimates (per Order)

| Asset | Duration / Count | Approx Size |
|---|---|---|
| Packing video (PK) | ~60 seconds | 35–40 MB |
| Unpacking video (RT) | ~80 seconds | 50–55 MB |
| 2K images (4 total: PK_front, PK_back, RT_front, RT_back) | 4 files | 15–20 MB |
| Comparison composite (auto-generated) | 2 files (front + back) | 3–5 MB |
| Metadata JSON | 1 file | <1 KB |
| **TOTAL per order** | — | **~105–120 MB** |

### 3.1 Storage Projections
- **Daily orders (peak):** 30 → ~3.5 GB/day → ~105 GB/month
- **Daily orders (current):** ~15 → ~1.8 GB/day → ~54 GB/month
- **2TB Crucial NVMe capacity:** ~17,000 orders worth of evidence at peak, or ~3 years at peak volume
- **Realistic runway:** 5+ years before any storage decision needs to be revisited

---

## 4. Lighting & Reflection Management

### 4.1 The Challenge
Mobile screens are highly reflective. Ceiling 2x2 grid lights create:
- Direct glare on screen front (washes out details)
- Hard shadows from top angle
- Camera autofocus failures on mirror-finish surfaces
- Protective film reflections amplify the problem

### 4.2 The Fixes (No Hardware Required)

**A. Diffused Lighting (one-time setup)**
- Place butter paper / white parchment / thin white cloth below ceiling lights
- Converts hard light → soft diffused light
- Eliminates sharp shadows and reduces direct glare
- Cost: ₹100 of butter paper

**B. Side Fill Lighting (recommended)**
- Add two cheap LED panel lights at 45° angle to product
- Eliminates camera-lens-reflection problem
- Cost: ₹500–1000 for two panels

**C. AE/AF Lock (no hardware, just discipline)**
- Long-press on screen in camera app to lock auto-exposure and auto-focus
- Locks the brightness so camera doesn't fluctuate as product moves
- Critical for consistent video quality

**D. The Texture Trick (focus aid)**
- Mobile screens are flat mirrors → camera can't focus
- Solution: place finger on corner of screen for 1 second → camera locks focus on the finger → release → product is now in focus
- Or: stick a small piece of tape on the corner during recording (removed in post)

**E. Distance + Optical Zoom**
- Don't get too close → causes shadows from camera + autofocus failures
- Stand 30–40 cm away → use 2x optical zoom on phone
- Maintains 2K detail while improving lighting and reducing reflections

### 4.3 The Hardware Upgrade (optional, big impact)
- **Circular Polarizer (CPL) filter** clip-on for phone — ₹500–1500
- Cuts screen glare dramatically
- Reveals scratches, micro-damages, FPC codes that are otherwise hidden
- Recommended if upgrade budget allows

---

## 5. Capture App Workflow (Spec)

### 5.1 PK Mode (Packing — Forward Dispatch)
1. **Open app → tap PK mode**
2. **Scan barcode** of forward shipping label → auto-fills Order ID (format: 407-1234567-1234567)
3. **AE/AF lock** prompt: "Tap and hold on product corner to lock focus"
4. **Capture front photo** (2K JPEG)
5. **Flip product → capture back photo** (2K JPEG) — captures FPC code + mfg serial
6. **Start video recording** (1080p 24fps HEVC, audio off)
7. **Pack the product on camera** (~60 seconds)
8. **Stop recording**
9. **App saves bundle** to local folder: `/orders/{OrderID}/`
   - `PK_front.jpg`
   - `PK_back.jpg`
   - `PK_video.mp4`
   - `metadata.json` (timestamps, AWB, order ID)
10. **Auto-sync to PC** over WiFi

### 5.2 RT Mode (Return — Receipt)
1. **Open app → tap RT mode**
2. **OCR the numeric Order ID** from return label (no barcode for order ID on return labels — only AWB)
3. **Fallback:** if OCR confidence low, scan AWB barcode → SP-API lookup → Order ID
4. **AE/AF lock** prompt
5. **Start video recording** — unbox the return
6. **Stop recording**
7. **Capture front photo** (2K JPEG) — received product front
8. **Capture back photo** (2K JPEG) — received product back, FPC visible
9. **QC verdict prompt:** 3 buttons
   - ✅ **OK** (matches sent product)
   - ⚠️ **Damaged**
   - ❌ **Different** (fraud — swap detected)
10. **App saves bundle** to existing folder `/orders/{OrderID}/`
    - `RT_front.jpg`
    - `RT_back.jpg`
    - `RT_video.mp4`
    - `metadata.json` (updated with verdict)
11. **If Damaged or Different:**
    - Auto-trigger comparison composite generation (see Section 6)
    - Add to Mahika's claim queue in Postgres
12. **Auto-sync to PC** over WiFi

### 5.3 Folder Structure (per Order)
```
/orders/407-1234567-1234567/
├── PK_front.jpg          (2K, packing front)
├── PK_back.jpg           (2K, packing back — FPC visible)
├── PK_video.mp4          (1080p HEVC, ~60s, audio off)
├── RT_front.jpg          (2K, return front)
├── RT_back.jpg           (2K, return back — FPC visible)
├── RT_video.mp4          (1080p HEVC, ~80s, audio off)
├── comparison_front.jpg  (auto-generated 4K side-by-side)
├── comparison_back.jpg   (auto-generated 4K side-by-side)
└── metadata.json         (all order data + verdict + claim status)
```

---

## 6. Comparison & Difference Detection Logic

### 6.1 Keyframe Extraction (if needed beyond explicit photos)
- Use **Laplacian Variance** method to find sharpest frame in a video segment
- Helpful as fallback if explicit photos are blurry
- Library: OpenCV (Python) — `cv2.Laplacian(image, cv2.CV_64F).var()`
- Higher variance = sharper frame

### 6.2 Comparison Techniques (Multi-Layered Detection)

**Layer 1 — SSIM (Structural Similarity Index)**
- Measures overall structural similarity between two images
- Range: 0 (no similarity) to 1 (identical)
- Threshold: <0.85 = likely different product
- Library: scikit-image — `skimage.metrics.structural_similarity()`

**Layer 2 — Feature Matching (ORB / SIFT)**
- Detects keypoints (corners, edges, distinctive marks) in both images
- Matches keypoints between PK and RT images
- Low match count = different product, scratches, or component swap
- Library: OpenCV — `cv2.ORB_create()` + `cv2.BFMatcher()`

**Layer 3 — Color Histogram Comparison**
- Compares color distribution between PK and RT
- Catches fake products that have subtle color tone differences
- Library: OpenCV — `cv2.calcHist()` + `cv2.compareHist()`

**Layer 4 — OCR on FPC Code / Mfg Serial (THE KILLER)**
- Extract text from PK_back and RT_back images using Tesseract OCR
- If FPC codes or mfg serials don't match → **definitive proof of swap**
- This single layer is worth more than all the others combined for SAFE-T claims
- Library: pytesseract (Python wrapper for Tesseract)

### 6.3 Composite Generation
- Use OpenCV / Pillow to stitch:
  - `PK_front.jpg` + `RT_front.jpg` → `comparison_front.jpg`
  - `PK_back.jpg` + `RT_back.jpg` → `comparison_back.jpg`
- Add text overlays:
  - "SENT" / "RECEIVED" labels
  - Order ID watermark
  - Date stamps
  - FPC code text (if extracted via OCR)
- Output: JPEG @ 85% quality, ready for SAFE-T upload

### 6.4 Verdict Logic (Auto-Suggest)
When the user marks RT in the app, Mahika's processor runs all 4 layers in background and pre-computes a verdict suggestion:
- **High match (SSIM >0.95, FPC match):** Suggest "OK"
- **Medium match (SSIM 0.85–0.95):** Suggest "Damaged" — possible same product with damage
- **Low match (SSIM <0.85, FPC mismatch):** Suggest "Different" — likely fraud
- User has final say — Mahika is decision support, not autonomous on this gate

---

## 7. SAFE-T Claim Filing Pipeline

### 7.1 The Trigger
- User marks RT verdict as "Damaged" or "Different" in the app
- App syncs to PC
- Mahika's queue picks up the order and adds to "claim ready" state
- BUT — claim cannot be filed until refund event is detected (the Catch-22)

### 7.2 The Refund Event Watcher
- Mahika polls SP-API Financial Events / Returns / Refund reports every 2 hours
- The instant a refund event is detected for a queued order:
  1. Verify it was processed by Amazon (not seller-initiated)
  2. Mark order as "claim eligible"
  3. Trigger Playwright claim filing automation

### 7.3 The Playwright Claim Filing Flow
1. Open Chrome (headless or headed in dev mode)
2. Load saved Seller Central session cookies
3. If session expired → send Telegram/WhatsApp alert to Arun: *"Sir, OTP chahiye, Seller Central pe login kar do"* → wait for human
4. Navigate: Performance → SAFE-T Claims → File New Claim
5. Enter Order ID
6. Select reason code based on verdict:
   - "Damaged" → "Item received damaged"
   - "Different" → "Materially different item received"
7. Paste templated message (see Section 7.4)
8. Upload `comparison_front.jpg` and `comparison_back.jpg` from order folder
9. Submit claim
10. Capture confirmation screenshot → save to order folder as `claim_submitted.png`
11. Update Postgres: claim status = "Submitted", claim ID logged
12. Move to follow-up watcher

### 7.4 Templated Claim Messages (per Verdict)

**For "Different" (fraud / swap):**
> Sir/Madam,
>
> The buyer has returned a materially different item from what was shipped. Attached comparison images clearly demonstrate the discrepancy:
>
> 1. The shipped product (front and back) matches the dispatched packing video and contains the original FPC code/manufacturing serial.
> 2. The received product is a different unit with different identifying marks and does not match the original.
>
> Please find the side-by-side comparison images attached as evidence. Packing and unpacking videos are available upon request.
>
> Requesting reimbursement under SAFE-T as this constitutes buyer fraud.
>
> Order ID: {order_id}
> Claim type: Materially different item returned

**For "Damaged":**
> Sir/Madam,
>
> The buyer has returned the item in a damaged condition not consistent with the dispatched product. The shipped product was in pristine condition as evidenced by the packing video and front/back photographs.
>
> Attached comparison images show the damage incurred between dispatch and return.
>
> Requesting reimbursement under SAFE-T as the return is not in resellable condition due to buyer-side damage.
>
> Order ID: {order_id}
> Claim type: Item received damaged in return

### 7.5 The Follow-Up Loop
- Every 12 hours, Mahika checks all "Submitted" claims
- Status states tracked:
  - Submitted → Under Review → Info Requested → Approved → Amount Credited → Closed
  - OR: Submitted → Under Review → Rejected → Auto-Appeal → Re-reviewed
- **Info Requested:** Mahika alerts Arun via Telegram with the specific question
- **Rejected:** Auto-appeal once with second-round evidence (additional video frames, OCR text overlay, expanded composite)
- **Approved:** Track until "Amount Credited" status appears in financial reports
- **Closed only when amount actually reflects in Amazon balance**

---

## 8. Master Plan — Phased Build Roadmap

### Phase 1 — Foundation (Week 1–2)
- Set up Oracle Cloud Always Free VM
- Install Postgres + Python + FastAPI
- Design and migrate database schema (orders, returns, claims, evidence, audit_log)
- Set up SP-API access (private developer registration on friend's Amazon account)
- Establish Seller Central session cookie capture flow

### Phase 2 — Capture App Improvements (Week 2–3)
- Modify existing capture app to add:
  - 2K front + back photo capture (PK + RT modes)
  - QC verdict prompt (OK / Damaged / Different)
  - Order ID OCR for return labels
  - Folder structure auto-creation
  - WiFi auto-sync to PC

### Phase 3 — Evidence Processing (Week 3–4)
- Build comparison composite generator (OpenCV + Pillow)
- Build OCR extractor for FPC codes / mfg serials (Tesseract)
- Build multi-layer difference detector (SSIM + ORB + histogram + OCR)
- Build auto-verdict suggestion engine

### Phase 4 — Mahika Core (Week 4–5)
- Build Smart Polling scheduler (different frequencies per task)
- Build refund event watcher (SP-API Financial Events polling)
- Build claim queue manager (Postgres-backed)
- Build alert system (Telegram bot for OTP, info requests, escalations)

### Phase 5 — Playwright Automation (Week 5–6)
- Record claim filing flow with `npx playwright codegen`
- Parameterize the script (order ID, reason, message, evidence paths)
- Add session cookie management
- Add screenshot audit trail
- Build follow-up status checker

### Phase 6 — Monitoring & Audit (Week 6–7)
- Build solo-operator triage cockpit (FastAPI web dashboard)
- Color-coded urgency view (refund-pending alerts, SAFE-T window countdown)
- Daily/weekly reports
- Audit log of all Mahika actions

### Phase 7 — Soft Launch & Iteration (Week 7+)
- Run Mahika in shadow mode (logs decisions but doesn't submit claims) for 1 week
- Manually verify Mahika's decisions
- Once confidence is high → enable autonomous claim filing
- Iterate based on real claim outcomes

---

## 9. Open Decisions & Parked Items

1. **Filename convention:** Order ID vs AWB as primary filename — **leaning Order ID** (stable across PK+RT, matches SP-API primary key, required for SAFE-T). AWB stored as metadata sidecar. **Awaiting Arun's final research and confirmation.**

2. **App framework:** React Native (Arun has experience from GharKhata) vs Flutter vs native Android. **Pending decision.**

3. **CPL filter:** Optional hardware upgrade for ₹500–1500. **Pending budget approval.**

4. **Side fill lighting:** Optional ₹500–1000 LED panels. **Pending budget approval.**

---

## 10. Authority & Scope

This is the technical specification document for Mahika's capture, evidence, and SAFE-T automation pipeline. Mahika operates under this spec for all evidence-related tasks. Any deviation requires Arun's approval.

> Prepared for the Boss, Arun Saini. RepairFully internal. Project Alpha — Amazon Seller Operations Agent.
