# Validation and limits

Recorded implementation checks from the development workspace on 2026-11-21; these are not GitHub Actions results or guarantees for other hardware. Raw generated reports and private workspace paths are excluded from source control.

| Check | Recorded result | Scope |
| --- | --- | --- |
| Shared Python suite | 72 passed | Model, persistence, importer, scoring, Qt and mobile bridge |
| Android instrumentation | 2 passed; no failures/errors/skips | Android 15 x86_64 emulator, airplane mode |
| Android lint | 0 errors, 19 warnings | Release lint; inline strings/update suggestions among warnings |
| Android pick updates | 10 updates, 156–230 ms, median 177.5 ms | Action through refreshed analysis on that emulator |
| Windows pick updates | 80 updates, median 154.86 ms, p95 381.54 ms, max 415.80 ms | Source Qt UI, four cohorts, warm/cleared caches |
| Scoring benchmark | 60 cases, median 4.03 ms, max 14.41 ms | Engine only, excluding end-to-end UI costs |
| Packaged Windows diagnostics | 6 checks passed | Launch, restart/import and corruption recovery on development host |
| Aggregate integrity | Reimports unchanged; no FK violations | Four bundled historical cohorts |

Android tests exercise actual UI Automator champion/role drag gestures, rejection, sequential picks, undo/reset, restart recovery and a ten-second response budget. NumPy/stdlib percentile paths are parity-tested. APK signature and ZIP alignment were checked; inspected ARM64 ELF segments supported 16 KB alignment. Release-mode selection and analysis were inspected separately.

## Remaining gaps

Physical phones, older Android versions, broad accessibility/tablet behavior, clean Windows 10/11 without development Python, and broader DPI combinations remain unverified. Invalid-proxy Windows smoke checks are not equivalent to disabling OS networking. Performance with arbitrary large imported datasets is unknown.

Recommendation accuracy, causal counter effects, calibrated probabilities and benefit for ordinary ranked players have not been established. Average-player data, difficulty controls and personal champion pools are not implemented yet.

## Reproduce

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe .\scripts\benchmark.py
.\.venv\Scripts\python.exe .\scripts\measure_pick_latency.py
.\scripts\build.ps1
.\.venv\Scripts\python.exe .\scripts\verify_build.py
```

After Android setup, `scripts/build-android.ps1 -DeviceTests` runs device tests. Use a dedicated emulator/device: instrumentation can install/uninstall the app and erase its saved data. Normal builds do not install onto a device.

The ten-second target is a maximum response budget, not an intentional wait. End-to-end latency includes the command, debounce, loading, calculation and rendering; engine benchmarks do not. Functional checks do not establish statistical suitability for a new population.
