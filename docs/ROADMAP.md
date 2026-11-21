# Roadmap

Status: 2026-11-21. These are implementation checkpoints, not delivery-date promises.

## Completed foundation

- [x] Stage 1: manual offline draft, search, roles, validation and undo/reset.
- [x] Portraits, used-champion grayscale and champion/role drag swaps.
- [x] Stage 2: SQLite, migrations, strict imports and licensed historical preparation.
- [x] Stage 3: baseline, matchup, synergy, composition and robustness scoring.
- [x] Stage 4: background analysis, filters, evidence, settings and Windows comparisons.
- [x] Stage 5: Windows packaging, recovery, checksums and local checks.
- [x] Android extension: native touch interface, shared core, development-signed APK and emulator tests.

These stages do not establish predictive accuracy or universal device compatibility.

## Next: average-player data and counters

- [ ] Select a licensed ranked solo-queue source with suitable skill cohorts.
- [ ] Validate queue/rank definitions, patch, region, observed roles and opponents.
- [ ] Build champion-role baselines and lane counters with supported sample sizes.
- [ ] Replace default professional filters and labels on both platforms, with no silent pro fallback.
- [ ] Add a seed-data upgrade path preserving existing imports, preferences and drafts.
- [ ] Present clear counter evidence and explicitly unsupported matchups.
- [ ] Repeat integrity, filter and pick-latency checks.

No average-player dataset or rank band is yet approved as the new default. Current builds retain professional data.

## Practical champion choice

- [ ] Personal champion pool/familiarity controls.
- [ ] Attributed difficulty indicators, separate from observed outcome statistics.
- [ ] Clearer counter explanations for partial drafts and uncertain enemy roles.

## Release quality

- [ ] Physical ARM64 phone and older Android testing.
- [ ] Clean Windows 10/11 tests without development Python.
- [ ] Broader DPI, screen-size and accessibility checks.
- [ ] Production signing, maintainable updates and repeatable release validation.
- [ ] Held-out statistical evaluation before any accuracy claims.

Live-client access, automated picks, overlays, accounts, remote services and a trained predictive model are outside the current plan.
