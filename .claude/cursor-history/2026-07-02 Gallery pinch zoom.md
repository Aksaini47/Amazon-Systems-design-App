# Gallery pinch zoom

- **Subtitle:** Edited local_gallery_screen.dart, update_service.dart
- **Project:** `c:\Projects\Amazon Systems Design`
- **Created:** 2026-07-02 13:40
- **Updated:** 
- **Status:** completed
- **Model:** default
- **Messages:** 8
- **Composer ID:** `ce33c0b2-0b6c-4c6d-a403-19dc43f9db05`

---
### User — 2026-07-02 13:40

Implement pinch-to-zoom for videos and images in the RF Logger Flutter app gallery at c:\Projects\Amazon Systems Design\app

## User request
Add pinch zoom in gallery for both video and image viewing.

## Explore first
- app/lib/screens/local_gallery_screen.dart — find _PhotoViewer, _InlineVideoPlayer, _FullscreenVideoPlayer, order/draft detail photo grids, any image/video preview dialogs
- Check if photo_view, interactive_viewer, or similar already in pubspec.yaml — prefer existing deps; if none suitable, use Flutter built-in InteractiveViewer (no new dep if possible)

## Implementation
1. **Image viewer** (_PhotoViewer or dialog): wrap Image.file in InteractiveViewer (minScale 1, maxScale 4-5) or PhotoView package if already present
2. **Inline video player** in draft/order detail: wrap video player widget in InteractiveViewer OR use a pinch-zoom overlay on fullscreen video
3. **Fullscreen video** if exists: add pinch zoom on video surface
4. Ensure pinch doesn't break tap-to-dismiss, swipe between photos, or play/pause controls
5. Test mentally: single finger pan when zoomed, double-tap optional reset

## Ship (user expects fix+commit+push+patch pattern from prior work)
- flutter analyze touched files via C:\Projects\apps\flutter_sdk\bin\flutter.bat
- Update app/lib/services/update_service.dart latestChangelog to 2.0.0+8:4 (or next patch #) with pinch zoom bullet
- Git commit (use env GIT_AUTHOR_NAME="Arun Saini" GIT_AUTHOR_EMAIL="dev@repairfully.com" — never git config)
- git push origin main
- cd app && ./tools/ship.ps1 -Mode patch -ReleaseVersion "2.0.0+8" -Changelog "Pinch zoom in gallery photos and video" -AllowNativeDiffs -AllowAssetDiffs

Return: files changed, commit hash, patch # published.

### Assistant — 2026-07-02 13:40

Pinch-to-zoom gallery ke liye pehle codebase aur dependencies check kar raha hoon.

### Assistant — 2026-07-02 13:40

> **Tool:** `update_current_step` completed
```
{"currentStep":"Exploring gallery viewer code"}
```

### Assistant — 2026-07-02 13:40

> **Tool:** `read_file_v2` completed
```
{"contents":"name: repairfully_camera\ndescription: RepairFully — Amazon seller video manager mobile app\npublish_to: 'none'\nversion: 2.0.0+8\n\nenvironment:\n  sdk: '>=3.4.3 <4.0.0'\n\ndependencies:\n  flutter:\n    sdk: flutter\n  cupertino_icons: ^1.0.6\n\n  # Camera & video\n  camera: ^0.11.0+2\n  native_camera_sound: ^0.0.3\n  sensors_plus: ^5.0.1\n  image: ^4.2.0\n\n  # Barcode scanning\n  mobile_scanner: ^5.2.3\n\n  # OCR — Amazon Order ID detection\n  google_mlkit_text_recognition: ^0.13.0\n\n  # Image capture\n  image_picker: ^1.1.2\n\n  # File management\n  path_provider: ^2.1.4\n  file_picker: ^8.1.2\n\n  # Permissions\n  permission_handler: ^11.3.1\n\n  # Networking\n  http: ^1.2.2\n  bonsoir: ^5.0.1\n\n  # Storage & settings\n  shared_preferences: ^2.3.2\n\n  # Utils\n  intl: ^0.19.0\n  device_info_plus: ^10.1.0\n  video_compress: ^3.1.2\n  retry: ^3.1.2\n  wakelock_plus: ^1.2.8  # Keep screen on during recording\n  video_player: ^2.9.1   # Inline video preview in gallery\n\n  # Firebase Crashlytics — crash reporting + non-fatal error tracking\n  # NOTE: Native gradle plugins remain DISABLED in android/app/build.gradle\n  # until `google-services.json` is dropped into android/app/. The Dart\n  # packages compile fine without it; runtime initialization is gated by\n  # `Firebase.apps.isNotEmpty` so the app gracefully no-ops when the JSON\n  # is missing (see main.dart).\n  firebase_core: ^3.6.0\n  firebase_crashlytics: ^4.1.3\n  shorebird_code_push: ^2.0.4  # Read patch number + force update prompts\n  package_info_plus: ^8.0.0    # App version/build/package for About panel\n\n# Pin transitive deps to versions that don't require the newer Flutter Gradle\n# wrapper. package_info_plus 9.x leaves out compileSdk in its build.gradle and\n# expects the project to inject it via the Flutter Android plugin in 3.27+;\n# our Flutter version emits the older wrapper, so we cap to <9.\n#\n# camera_android_camerax 0.6.10+3 (auto-resolved by camera ^0.11.0+2) has a\n# 
… [truncated 1,200 chars]
```

### Assistant — 2026-07-02 13:40

> **Tool:** `ripgrep_raw_search` completed
```
{"pattern":"_PhotoViewer|_InlineVideoPlayer|_FullscreenVideoPlayer|InteractiveViewer|photo_view","path":"c:\\Projects\\Amazon Systems Design\\app","caseInsensitive":false,"multiline":false,"toolCallId":"tool_bcaf82a3-7a3f-482e-8c7d-f9b9060edfb","offset":0}
```

### Assistant — 2026-07-02 13:40

> **Tool:** `read_file_v2` completed
```
{"contents":"","totalLinesInFile":2449}
```

### Assistant — 2026-07-02 13:40

Images mein `InteractiveViewer` pehle se hai; ab video players aur photo viewer polish check kar raha hoon.

### Assistant — 2026-07-02 13:40

> **Tool:** `read_file_v2` completed
```
{"contents":"","totalLinesInFile":295}
```

### Assistant — 2026-07-02 13:40

> **Tool:** `run_terminal_command_v2` completed
```
{"output":"At C:\\Users\\DELL\\AppData\\Local\\Temp\\ps-script-83d1e7cb-5dff-4e89-97a2-38b1bc1b9f8a.ps1:7 char:40\r\n+ cd \"c:\\Projects\\Amazon Systems Design\" && git diff app/lib/screens/lo ...\r\n+                                        ~~\r\nThe token '&&' is not a valid statement separator in this version.\r\n    + CategoryInfo          : ParserError: (:) [], ParentContainsErrorRecordException\r\n    + FullyQualifiedErrorId : InvalidEndOfLine\r\n \r\n","exitCode":1,"rejected":false,"notInterrupted":true}
```

### Assistant — 2026-07-02 13:40

> **Tool:** `ripgrep_raw_search` completed
```
{"pattern":"PhotoViewer|InlineVideoPlayer|FullscreenVideoPlayer|InteractiveViewer","path":"c:\\Projects\\Amazon Systems Design\\app","caseInsensitive":false,"multiline":false,"toolCallId":"tool_afb70dcb-b31e-4c3e-a754-bb65a5d6334","offset":0}
```

### Assistant — 2026-07-02 13:40

> **Tool:** `run_terminal_command_v2` completed
```
{"rejected":false,"notInterrupted":true}
```

### Assistant — 2026-07-02 13:40

> **Tool:** `ripgrep_raw_search` completed
```
{"pattern":"_FullscreenVideoPlayer","path":"c:\\Projects\\Amazon Systems Design\\app","caseInsensitive":false,"multiline":false,"toolCallId":"tool_07a2c73d-46c5-4399-95c4-2bc868b2e13","offset":0}
```

### Assistant — 2026-07-02 13:41

Images mein basic zoom hai; ab video pinch-zoom aur photo viewer polish implement kar raha hoon.

### Assistant — 2026-07-02 13:41

> **Tool:** `update_current_step` completed
```
{"currentStep":"Adding pinch zoom to viewers"}
```

### Assistant — 2026-07-02 13:41

> **Tool:** `edit_file_v2` completed
```
{"beforeContentId":"composer.content.399d8b2e5a39fa1e2967de70b3da1ae3d95c09d80c910ee00f7c3730e40ec3e2","afterContentId":"composer.content.2532d510b4b3b05292724a17857c031c9d26b979e47368cdf8b0f5415e431f77"}
```

### Assistant — 2026-07-02 13:41

> **Tool:** `edit_file_v2` completed
```
{"beforeContentId":"composer.content.c5f7030faf2afebd8632ddeb2d8b11c2c2802f23a9f6f51af951cea3f7a4e12e","afterContentId":"composer.content.711c02849f2fbc72cedd2e186e25fed626105e93651bb12b1d9603a88821ded6"}
```

### Assistant — 2026-07-02 13:41

> **Tool:** `edit_file_v2` completed
```
{"beforeContentId":"composer.content.f0a2c7a3ff63ac64258d50160c1c386633d4b5bc66c4cefc80b94eedac6d85ac","afterContentId":"composer.content.103515b0e618fd9a520647791801a43bac7ba807afd56c011b918f0c27b5f18b"}
```

### Assistant — 2026-07-02 13:41

> **Tool:** `edit_file_v2` completed
```
{"beforeContentId":"composer.content.38118956e9ab1a5d6e0d664e5d31b8aba7d25445116027891b35a8e3240018a9","afterContentId":"composer.content.da9f09930d5abd488b78338816bc358c7633262051ef0b641a5b441b17dc123d"}
```

### Assistant — 2026-07-02 13:41

> **Tool:** `edit_file_v2` completed
```
{"beforeContentId":"composer.content.3117c77b636d6c1155eb56ab2789305ced50111fd8fbf5660b36af0eb91709c4","afterContentId":"composer.content.1cb29668de06eb306515a0d2db78a51b85e08af82e8c9871d026eabb1df54fc9"}
```

### Assistant — 2026-07-02 13:41

> **Tool:** `edit_file_v2` completed
```
{"beforeContentId":"composer.content.c74a700028078c64b408490437693828c87a3102a397edb913acf6d242ab5270","afterContentId":"composer.content.74004c53f515cc012c50c409eafb3d4f198f7286beaa00c47cfca140d13670a7"}
```

### Assistant — 2026-07-02 13:41

> **Tool:** `edit_file_v2` completed
```
{"beforeContentId":"composer.content.7012068f0d4c6d5f1cc2828bb1f29ffdbe3fddc800aa555fa339e55ea04668cc","afterContentId":"composer.content.c3cc33980545ad87f7bb918b9f646b0a5946797a2794191f0888b9f3e3ac55ec"}
```

### Assistant — 2026-07-02 13:41

Video player mein `pinchZoom: false` case aur syntax verify kar raha hoon.

### Assistant — 2026-07-02 13:41

> **Tool:** `read_file_v2` completed
```
{"contents":"    //   - BUT the texture content the platform decoder hands to the\n    //     player IS already pre-rotated portrait pixels (1080×1920) —\n    //     extracting a frame with `ffmpeg -frames:v 1` produces a 1080×1920\n    //     portrait image. The texture content matches what's stored.\n    //\n    // So: the player widget needs a PORTRAIT-shaped slot. If we render\n    // it into a landscape AspectRatio (1.78), the portrait texture gets\n    // squished into a landscape rectangle → that's the \"stretch\" the\n    // user reported. A previous attempt added RotatedBox, which only\n    // rotated the already-stretched content (still stretched, just\n    // sideways).\n    //\n    // FIX: Detect \"ignored rotation\" via the same heuristic (our app\n    // records portrait, so coded dims > height = ignored rotation) and\n    // pass the SWAPPED aspect (height/width = portrait) to AspectRatio.\n    // No RotatedBox — the texture is already pre-rotated.\n    final ignoredRotation = v.size.width > v.size.height && v.size.height > 0;\n    final effectiveAspect = ignoredRotation\n        ? v.size.height / v.size.width  // 1080/1920 = 0.5625 portrait\n        : v.aspectRatio;\n\n    Widget videoSurface = AspectRatio(\n      aspectRatio: effectiveAspect,\n      child: VideoPlayer(_ctrl!),\n    );\n    if (widget.pinchZoom && _zoomCtrl != null) {\n      videoSurface = GestureDetector(\n        onDoubleTap: _toggleVideoZoom,\n        onTap: () => setState(() => _showControls = !_showControls),\n        child: InteractiveViewer(\n          transformationController: _zoomCtrl,\n          minScale: 1.0,\n          maxScale: 5.0,\n          clipBehavior: Clip.hardEdge,\n          child: videoSurface,\n        ),\n      );\n    }\n\n    return ClipRRect(\n      borderRadius: BorderRadius.circular(12),\n      child: Stack(\n        children: [\n          Container(\n            constraints: const BoxConstraints(\n              minHeight: 220,\n              maxHeight: 
… [truncated 3,393 chars]
```

### Assistant — 2026-07-02 13:41

> **Tool:** `read_lints` completed
```
{}
```

### Assistant — 2026-07-02 13:41

> **Tool:** `read_file_v2` completed
```
{"contents":"                          colors: const VideoProgressColors(\n                            playedColor: Color(0xFFFF7B00),\n                            bufferedColor: Colors.white24,\n                            backgroundColor: Colors.white10,\n                          ),\n                        ),\n                      ),\n                    ),\n                    Text(_fmt(v.duration), style: const TextStyle(color: Colors.white, fontSize: 11, fontFamily: 'monospace')),\n                  ]),\n                ),\n              ),\n            ),\n          ],\n        ),\n    );\n  }\n}\n\n// ─── Fullscreen video player (for drafts) ─────────────────────────────\n\nclass _FullscreenVideoPlayer extends StatelessWidget {\n  final String path;\n  final String title;\n  const _FullscreenVideoPlayer({required this.path, required this.title});\n\n  @override\n  Widget build(BuildContext context) {\n    return Scaffold(\n      backgroundColor: Colors.black,","totalLinesInFile":2547}
```

### Assistant — 2026-07-02 13:41

> **Tool:** `edit_file_v2` completed
```
{"beforeContentId":"composer.content.d70c055d5f4576a9746166fbdc70dc83abf03decce18b22b04d01c056b4266b6","afterContentId":"composer.content.bb31138e8f0ce8f32df94048ea36082433def304dff4c21b7f5db3a77b512a56"}
```

### Assistant — 2026-07-02 13:41

> **Tool:** `run_terminal_command_v2` completed
```
{"output":"Analyzing 2 items...                                            \n\n   info - Don't use 'BuildContext's across async gaps. Try rewriting the code to not use the 'BuildContext', or guard the use with a 'mounted' check - app\\lib\\screens\\local_gallery_screen.dart:403:28 - use_build_context_synchronously\n   info - Statements in an if should be enclosed in a block. Try wrapping the statement in a block - app\\lib\\screens\\local_gallery_screen.dart:501:37 - curly_braces_in_flow_control_structures\n   info - Statements in an if should be enclosed in a block. Try wrapping the statement in a block - app\\lib\\screens\\local_gallery_screen.dart:502:20 - curly_braces_in_flow_control_structures\n   info - Don't use 'BuildContext's across async gaps. Try rewriting the code to not use the 'BuildContext', or guard the use with a 'mounted' check - app\\lib\\screens\\local_gallery_screen.dart:645:26 - use_build_context_synchronously\n   info - Don't use 'BuildContext's across async gaps. Try rewriting the code to not use the 'BuildContext', or guard the use with a 'mounted' check - app\\lib\\screens\\local_gallery_screen.dart:646:26 - use_build_context_synchronously\n   info - Unnecessary braces in a string interpolation. Try removing the braces - app\\lib\\screens\\local_gallery_screen.dart:945:48 - unnecessary_brace_in_string_interps\nwarning - A value for optional parameter 'pinchZoom' isn't ever given. Try removing the unused parameter - app\\lib\\screens\\local_gallery_screen.dart:1158:54 - unused_element_parameter\n   info - 'scale' is deprecated and shouldn't be used. Use scaleByVector3, scaleByVector4, or scaleByDouble instead. Try replacing the use of the deprecated member with the replacement - app\\lib\\screens\\local_gallery_screen.dart:1213:40 - deprecated_member_use\n   info - Use 'const' with the constructor to improve performance. Try adding the 'const' keyword to the constructor invocation - app\\lib\\screens\\local_gallery_screen.dart:1337:33 - pref
… [truncated 3,532 chars]
```

### Assistant — 2026-07-02 13:42

Deprecated `scale` fix karke commit, push aur ship chala raha hoon.

### Assistant — 2026-07-02 13:42

> **Tool:** `edit_file_v2` completed
```
{"beforeContentId":"composer.content.7db4c3bad5d78abca223be92ab72839cbd99b9734c593b61339ae9cc57c4b623","afterContentId":"composer.content.204ab4f4a8a55ae521d9b045516099b62d229e9bff60b0739d7f65d23062674f"}
```

### Assistant — 2026-07-02 13:42

> **Tool:** `run_terminal_command_v2` completed
```
{"output":"On branch main\nYour branch is up to date with 'origin/main'.\n\nChanges not staged for commit:\n  (use \"git add <file>...\" to update what will be committed)\n  (use \"git restore <file>...\" to discard changes in working directory)\n\tmodified:   app/lib/screens/local_gallery_screen.dart\n\tmodified:   app/lib/services/update_service.dart\n\nno changes added to commit (use \"git add\" and/or \"git commit -a\")\n app/lib/screens/local_gallery_screen.dart | 189 +++++++++++++++++++++++-------\n app/lib/services/update_service.dart      |   4 +-\n 2 files changed, 149 insertions(+), 44 deletions(-)\n","rejected":false,"notInterrupted":true}
```

### Assistant — 2026-07-02 13:42

> **Tool:** `run_terminal_command_v2` completed
```
{"output":"Committer identity unknown\n\n*** Please tell me who you are.\n\nRun\n\n  git config --global user.email \"you@example.com\"\n  git config --global user.name \"Your Name\"\n\nto set your account's default identity.\nOmit --global to set the identity only in this repository.\n\nfatal: unable to auto-detect email address (got 'DELL@DESKTOP-44H0M0V.(none)')\n","exitCode":128,"rejected":false,"notInterrupted":true}
```

### Assistant — 2026-07-02 13:42

> **Tool:** `run_terminal_command_v2` completed
```
{"output":"[main ba6c462] Add pinch-to-zoom for gallery photos and videos.\n 2 files changed, 149 insertions(+), 44 deletions(-)\n","rejected":false,"notInterrupted":true}
```

### Assistant — 2026-07-02 13:42

> **Tool:** `run_terminal_command_v2` completed
```
{"output":"To https://github.com/Aksaini47/Amazon-Systems-design-App.git\n   8d1a474..ba6c462  main -> main\n","rejected":false,"notInterrupted":true}
```

### Assistant — 2026-07-02 13:42

> **Tool:** `run_terminal_command_v2` completed
```
{"output":"RF Logger ship.ps1 - Mode=patch\n\n=== PATCH mode ===\n  [ok] Release target (override): 2.0.0+8\n  [!!] Yaad rahe: patch tabhi dikhega jab phone par EXACTLY 2.0.0+8 install ho.\n  [ok] latestChangelog set: 2.0.0+8:4\n  [..] shorebird patch android --release-version=2.0.0+8 --allow-asset-diffs --allow-native-diffs '--' --no-tree-shake-icons\nGit is not configured to allow long paths. This can cause issues with Shorebird's Flutter checkout. Please run 'git config --system core.longpaths true' to enable long paths.\nStarting Fetching apps...\nDone Fetching apps\nStarting Fetching releases...\nDone Fetching releases\nStarting Fetching aab artifact...\nDone Fetching aab artifact\nStarting Fetching android_supplement artifact...\nDone Fetching android_supplement artifact\nStarting Downloading aab...\nDownloading aab (0%)...\nDownloading aab (0%)...\nDownloading aab (0%)...\nDownloading aab (0%)...\nDownloading aab (0%)...\nDownloading aab (1%)...\nDownloading aab (2%)...\nDownloading aab (3%)...\nDownloading aab (6%)...\nDownloading aab (7%)...\nDownloading aab (9%)...\nDownloading aab (11%)...\nDownloading aab (14%)...\nDownloading aab (16%)...\nDownloading aab (19%)...\nDownloading aab (22%)...\nDownloading aab (25%)...\nDownloading aab (27%)...\nDownloading aab (30%)...\nDownloading aab (34%)...\nDownloading aab (37%)...\nDownloading aab (40%)...\nDownloading aab (43%)...\nDownloading aab (44%)...\nDownloading aab (46%)...\nDownloading aab (49%)...\nDownloading aab (52%)...\nDownloading aab (55%)...\nDownloading aab (58%)...\nDownloading aab (61%)...\nDownloading aab (64%)...\nDownloading aab (67%)...\nDownloading aab (70%)...\nDownloading aab (72%)...\nDownloading aab (75%)...\nDownloading aab (78%)...\nDownloading aab (80%)...\nDownloading aab (83%)...\nDownloading aab (86%)...\nDownloading aab (89%)...\nDownloading aab (92%)...\nDownloading aab (96%)...\nDownloading aab (99%)...\nDone Downloading aab (100%)\nBuilding patch with Flutter 3.44.0 (1a55eb72b6
… [truncated 10,379 chars]
```

### Assistant — 2026-07-02 13:44

`scaleByDouble` Shorebird Flutter par fail ho raha hai — compatible API par fix karke patch dubara ship kar raha hoon.

### Assistant — 2026-07-02 13:44

> **Tool:** `edit_file_v2` completed
```
{"beforeContentId":"composer.content.204ab4f4a8a55ae521d9b045516099b62d229e9bff60b0739d7f65d23062674f","afterContentId":"composer.content.69ea0fb9276ceedb48a01569899528c1a4097bf5f52cb542477dd020a6bbcece"}
```

### Assistant — 2026-07-02 13:44

> **Tool:** `run_terminal_command_v2` completed
```
{"output":"[main 34d0792] Fix Matrix4 zoom scale for Shorebird Flutter SDK\n 1 file changed, 2 insertions(+), 2 deletions(-)\nTo https://github.com/Aksaini47/Amazon-Systems-design-App.git\n   ba6c462..34d0792  main -> main\nRF Logger ship.ps1 - Mode=patch\n\n=== PATCH mode ===\n  [ok] Release target (override): 2.0.0+8\n  [!!] Yaad rahe: patch tabhi dikhega jab phone par EXACTLY 2.0.0+8 install ho.\n  [ok] latestChangelog set: 2.0.0+8:4\n  [..] shorebird patch android --release-version=2.0.0+8 --allow-asset-diffs --allow-native-diffs '--' --no-tree-shake-icons\nGit is not configured to allow long paths. This can cause issues with Shorebird's Flutter checkout. Please run 'git config --system core.longpaths true' to enable long paths.\nStarting Fetching apps...\nDone Fetching apps\nStarting Fetching releases...\nDone Fetching releases\nStarting Fetching aab artifact...\nDone Fetching aab artifact\nStarting Fetching android_supplement artifact...\nDone Fetching android_supplement artifact\nStarting Downloading aab...\nDownloading aab (0%)...\nDownloading aab (0%)...\nDownloading aab (0%)...\nDownloading aab (0%)...\nDownloading aab (0%)...\nDownloading aab (1%)...\nDownloading aab (2%)...\nDownloading aab (4%)...\nDownloading aab (6%)...\nDownloading aab (9%)...\nDownloading aab (12%)...\nDownloading aab (13%)...\nDownloading aab (16%)...\nDownloading aab (19%)...\nDownloading aab (22%)...\nDownloading aab (25%)...\nDownloading aab (27%)...\nDownloading aab (29%)...\nDownloading aab (31%)...\nDownloading aab (33%)...\nDownloading aab (36%)...\nDownloading aab (39%)...\nDownloading aab (41%)...\nDownloading aab (44%)...\nDownloading aab (46%)...\nDownloading aab (48%)...\nDownloading aab (49%)...\nDownloading aab (51%)...\nDownloading aab (54%)...\nDownloading aab (57%)...\nDownloading aab (59%)...\nDownloading aab (63%)...\nDownloading aab (66%)...\nDownloading aab (69%)...\nDownloading aab (72%)...\nDownloading aab (74%)...\nDownloading aab (77%)...\nDownloading aab (
… [truncated 11,819 chars]
```

### Assistant — 2026-07-02 13:47

> **Tool:** `update_current_step` completed
```
{"currentStep":"Pinch zoom shipped as patch 4","finalSummary":"Gallery mein pinch-to-zoom add ho gaya — photos aur inline video dono par. **Patch #4** publish ho chuka hai (`2.0.0+8`). Phone par app **poora band** karke dobara kholo; patch download hoga, phir ek aur baar khulne par active.","completedSubtitle":"Published gallery pinch zoom patch"}
```

### Assistant — 2026-07-02 13:47

**Ho chuka**
- Photos: `_PhotoViewer` — pinch 1×–5×, double-tap zoom/reset, zoomed hone par swipe lock
- Video: `_InlineVideoPlayer` — pinch zoom, play/pause + scrubber same, reset zoom button
- Built-in `InteractiveViewer` — naya package nahi
- Changelog `2.0.0+8:4` · commit `34d0792` · **Patch #4** published

**Files changed**
| File | Kya |
|------|-----|
| `app/lib/screens/local_gallery_screen.dart` | Photo + video pinch zoom |
| `app/lib/services/update_service.dart` | Changelog bump |

**Phone par**
1. App recents se **poora band** karo
2. Dobara kholo → patch download
3. Ek aur baar kholo → pinch zoom active

**Kaise use karein**
- Photo tap → pinch / double-tap zoom
- Order/Draft detail video → pinch zoom; controls tap se same
