# App scratch files — archived 17 Jul 2026

Dead tooling and stale artifacts from the app's early era (pre-rename, when
`app/` was `mobile/`). Archived during the 2.1.0 revamp; git history preserved.

| File | Why archived |
|---|---|
| `analyze_errors.txt`, `analyze_output.txt`, `analyze_results.txt` | May-2026 analyzer dumps referencing files that no longer exist (`fba_screen.dart`, `record_screen.dart`, `api_service.dart`). Were already stale when committed. |
| `devices.txt`, `devices_list.txt` | Old `adb devices` dumps. |
| `hot_reload.sh`, `quick_fix.sh`, `quick_flow.sh` | Referenced dead paths from day one; never worked in this workspace. |
| `build_and_install.bat` | Hazard, not tool: its `cd` target no longer exists and there is no errorlevel check — it would run `flutter create` in whatever directory it was launched from. |

The live toolchain is `app/tools/ship.ps1` (Shorebird release/patch + install).
