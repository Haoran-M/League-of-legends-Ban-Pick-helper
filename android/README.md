# League Draft — Android

The Android version reuses the desktop Python draft model, validation, undo history, local SQLite schema/importer and recommendation engine. Its interface is native Android/Java, with Chaquopy embedding Python 3.12 in the app process. It has no server, login, live game integration, overlay, game automation or Internet permission.

## Install and use

Use `dist/LeagueDraftAssistant.apk` on **Android 8.0 or newer, 64-bit ARM64 or x86_64**. This is an installable release-mode APK signed with a local development certificate, not a Google Play release. Python is included; the phone does not need a separate Python installation or a network connection.

The APK bundles all 173 portraits, the same roster/aliases, and the four historical professional-play cohorts described in the root DATA_SOURCES.md. Scores are comparisons, not win probabilities or solo-queue claims.

- Set your team and role in the top selectors.
- Tap a pick/ban slot to open the searchable champion grid. Search accepts canonical names and aliases; used champions appear grayscale.
- Hold a filled portrait and drag it onto another pick to move/swap champions while preserving row roles. Bans similarly move/swap between ban slots.
- Hold a role label and drag it onto another role on the same side to swap roles without moving champions. Tapping a role opens its selector; selecting a role already present on that side swaps it atomically.
- Undo and reset are reversible. Duplicate or banned picks are rejected without partial changes.
- Save draft is initially enabled on Android. It can be disabled, which removes the saved draft; preferences and imported data remain separate. Saved drafts are validated on restart. Corrupt files are preserved before recovery.
- Analysis shows supported candidates, coverage and baseline appearances. Tap a candidate for component weights, pair wins/games, residuals and limitations. Settings changes weights, smoothing and minimum observations.
- Import JSON uses Android's file picker to read a local schema-compliant dataset bundle. CSV-directory import is available in the desktop/CLI workflow; convert it to a JSON bundle before importing on Android. Export draft creates the same versioned JSON format used by desktop recovery.

All mutable files remain in app-private storage. No broad storage permission is requested. Sources and method notices are available in the Analysis view. The UI handles phone/tablet sizes and orientation changes without rebuilding draft state.

## Build on Windows

Set up the source Python virtual environment using the root README, then:

```powershell
.\scripts\setup-android.ps1 -AcceptSdkLicense
.\scripts\build-android.ps1
```

Setup downloads checksum-verified, pinned portable tools under ignored `.tmp` paths; it does not change global Java/Android settings. `-AcceptSdkLicense` accepts the Android SDK development license during package installation. Omit it to review/respond interactively.

Pinned tools: Temurin JDK 21.0.13.1+2, Gradle 8.11.1, Android Gradle plugin 8.9.2, Chaquopy 17.2.0, compile/target API 35 and build-tools 35.0.0. See toolchain.json for URLs and hashes. Gradle wrapper files are included. The Python build interpreter must be Python 3.12; its micro version may differ from the embedded runtime.

The helper runs the shared-core pytest suite, assembles the release APK, runs release lint, verifies the APK signature and 16 KB ZIP alignment, then writes:

- `dist/LeagueDraftAssistant.apk`
- `dist/APK_SHA256SUMS.txt`

The local signing key is generated under `.tmp/android-signing`, ignored by source control. Retain that key privately if you need compatible updates to an installed test APK. Store publication requires a separately managed production signing/release process.

`build-android.ps1 -DeviceTests` additionally runs instrumentation tests on a connected **dedicated test emulator/device**. The test task installs/uninstalls this app package; do not use it on a device holding a draft you want to keep. The regular build does not install onto any device. Native on-device tests use AndroidX Test and UI Automator, including real long-press drag gestures, rejection, undo/reset, disk recovery and the 10-second pick-update budget.

## Validation and limits

See docs/TESTING.md for actual results. Android 15 x86_64 emulator tests ran in airplane mode. Physical ARM64 phones and older Android versions have not been run in this workspace. Release lint warnings about English inline strings, available dependency upgrades and backup rules are recorded; no lint errors were accepted. The app explicitly disables backup and makes no network requests.

The shared engine uses NumPy when available on desktop, and an equivalent standard-library linear percentile implementation in the APK. Parity tests compare both paths. Android caches at most two exact-filter snapshots, calculates on a background executor, debounces by 120 ms and ignores stale results. The response target is under 10 seconds after a pick, with the observed emulator measurements reported separately from physical-device guarantees.
