# Demo flavor — google-services.json goes here

`flutter build apk --flavor demo` will fail until `google-services.json` for the
**demo** Android app (`com.repairfully.logger.demo`) is placed in this folder.

## Steps (Firebase console, project `rf-logger`)

1. https://console.firebase.google.com/ → project **rf-logger**.
2. **Build → Firestore Database** → Create database → production mode → region
   `asia-south1` (Mumbai) — pick deliberately, hard to change later.
3. **Build → Remote Config** → add:
   - `demo_trial_days` — Number — default `30`
   - `demo_kill_switch` — Boolean — default `false`
   - Click **Publish changes** (values are not live until published).
4. **Project settings (gear icon) → Add app → Android**:
   - Package name: `com.repairfully.logger.demo`
   - Nickname: `RF Logger (Demo)`
   - No SHA-1 needed (nothing here uses Auth/Dynamic Links).
   - Download the generated `google-services.json`.
5. Save the downloaded file as:
   `app\android\app\src\demo\google-services.json`
   (same folder as this README — replace nothing else).

Once that file is in place, `app\tools\ship_demo.ps1` will build successfully.
See `firestore.rules` at the repo root of `app\` for the security rules to
paste into the Firestore console's Rules tab (Build → Firestore Database →
Rules).
