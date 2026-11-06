# RF Logger

Android app for Amazon-seller shipment evidence: record packing (PK) and
return-unpacking (RT) video + QC photos per order, named and foldered so a
SAFE-T claim can be filed from the media alone. **Local-only** — media stays
on the phone (backend sync was removed in 2.0.0 patch 8).

## Flow

- **PK** — scan the order label (barcode/OCR) → record packing video →
  front/back photos → saved to `{orderId}-PK/`.
- **RT** — record unpacking → QC verdict (OK / DAMAGED / DIFFERENT /
  DAMAGED + DIFFERENT / EMPTY BOX) → claim photos when the verdict is not OK
  (return label first, as the parcel is unpacked) → scan the return label
  (Order ID — Amazon `407-1234567-1234567` or the website's `RF-YYMMDD-NNNN`, e.g. `RF-261104-0004`, typed with the RF- shortcut; the tracking ID may be left blank, but a typed one needs 12+ digits or the exact format of India Post / DTDC / Shadowfax / Ekart / Xpressbees) →
  saved to `{orderId}-RT/` with `claim_trigger` in `meta.json`.
  Sub-reasons (Amazon's SAFE-T wording) exist only inside DAMAGED (heavily
  damaged / minor damage / mildly used / heavily used) and DIFFERENT
  (different item / counterfeit); DAMAGED + DIFFERENT, OK and EMPTY BOX ask
  none. The main reason and its sub-reason are written together — `qc=` +
  `qc_sub=` on every activity-log line, `verdict` + `qc_sub_reasons` in
  `meta.json`.
- Label screen (PK + RT): opens on the live BARCODE reader (a short strip frame, one barcode at a time); a floating BARCODE | TEXT switcher moves to OCR (3:4 frame) for torn/faded labels. The reader analyses every frame for Code128 / Code39 / QR only; "Camera not starting" + Retry appears only when the camera itself fails (no barcode in view just changes the hint), and Retry rebuilds the scanner from scratch. OCR AWBs are repaired by position (0/O, 1/I, 5/S ...) against the courier format, and a lettered or repaired OCR read waits for a SAVE tap instead of auto-saving. Both fields use the English keyboard, capitals only.
- Gallery: browse, edit, re-tag, pinch-zoom; drafts auto-recovered after a
  crash.

## Stack

Flutter (Shorebird-pinned SDK), CameraX, ML Kit OCR, mobile_scanner,
Firebase Crashlytics. Design tokens live in `lib/theme/` (RfColors / RfGlass).

## Develop

```powershell
flutter pub get
flutter analyze   # must stay at 0 issues (CI enforces)
flutter test      # 35+ tests, CI enforces
```

## Ship

OTA patches and releases go through **Shorebird** — never bare
`flutter build`. Rules live in `.claude/skills/shorebird-release/SKILL.md`;
the automation is [tools/ship.ps1](tools/ship.ps1):

```powershell
./tools/ship.ps1                      # auto: Dart-only → patch, native → release
./tools/ship.ps1 -Mode release        # full release (bumps pubspec build number)
./tools/ship.ps1 -Mode patch -ReleaseVersion 2.1.0+9
```

Key rules: `--no-tree-shake-icons` always (baked into ship.ps1); a patch's
`--release-version` must exactly match the release installed on the phone;
native/dependency changes require a full release + reinstall.

Release builds are **deliberately debug-signed** (see the note in
`android/app/build.gradle`) — the keystore is backed up at
`C:\RF-Logger-Backups\`. Changing the signature would force an uninstall and
wipe captured evidence.
