# RF Logger

Android app for Amazon-seller shipment evidence: record packing (PK) and
return-unpacking (RT) video + QC photos per order, named and foldered so a
SAFE-T claim can be filed from the media alone. **Local-only** — media stays
on the phone (backend sync was removed in 2.0.0 patch 8).

## Flow

- **PK** — scan the order label (barcode/OCR) → record packing video →
  front/back photos → saved to `{orderId}-PK/`.
- **RT** — record unpacking → QC verdict (OK / DAMAGED / DIFFERENT /
  DAMAGED + DIFFERENT) → claim photos when the verdict is not OK → saved to
  `{orderId}-RT/` with `claim_trigger` in `meta.json`.
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
