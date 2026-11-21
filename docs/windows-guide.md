# League Draft Assistant

Native Windows 10/11 x64 desktop application for manual offline draft simulation and historical comparisons. It includes searchable champion portraits, drag-and-drop swaps, undo/reset, optional draft recovery, a local SQLite importer and support-aware recommendations. No Riot account, client integration, overlay, automation, server or runtime network access is used.

## Run the Windows application

Open `dist\LeagueDraftAssistant.exe`. Python installation is not needed for this standalone build. Alternatively, extract `dist\LeagueDraftAssistant-portable.zip` and run the EXE inside its folder; keep its `_internal` directory beside it. These local builds are unsigned and may be identified by Windows SmartScreen as unrecognized. Do not bypass security controls automatically.

An Android version is also available as `dist\LeagueDraftAssistant.apk` for Android 8.0+ on 64-bit ARM64/x86_64 devices. It bundles the same offline data and Python scoring core with a native touch interface. See [Android guide](../android/README.md) for usage, build instructions, signing and executed device-test limits.

See TESTING.md and `local generated test artifacts` for executed checks and their limits. A clean Windows machine without Python and OS-level disabled networking have not been verified in this environment.

## Draft workflow

1. Set **Your team** and **Your role**. Each side has five pick and five ban slots. Blue rows initially have Top/Jungle/Mid/ADC/Support labels; enemy roles initially remain Unknown.
2. Click a slot and search by canonical name or alias (`kaisa`, `j4`, `nunu`, `monkeyking`), then click a tile or press Enter. You can also drag a grid portrait directly onto a slot.
3. Drag a filled pick onto another pick to swap champions, or onto an empty pick to move it. Row roles stay in place. Bans can similarly move/swap between ban slots. Pick-to-ban drags are rejected. Dragging an already picked champion from the grid to a pick moves/swaps its existing draft slot.
4. Drag a **role dropdown label** onto another role dropdown on the same side to swap roles without moving champions. Clicking still opens the role dropdown, and keyboard selection remains available.
5. **Clear slot**, **Undo** and **Reset draft** support ordinary editing; reset is undoable. Invalid edits leave state/history unchanged and explain why in the status bar.

Picked and banned portraits turn grayscale in the champion grid. Filled draft slots remain in color. Names, status text and tooltips preserve identification. Missing portraits fall back to text. At small window sizes, side panels scroll so picks, bans and role labels remain accessible.

Picks must be unique across both sides and cannot be banned. A team cannot repeat its own ban; opposing teams may share a ban. A known role can appear once per side, with any number of Unknown roles. Partial drafts and unknown enemy roles are supported.

Shortcuts: **Ctrl+F** search, **Enter** assign highlighted match, **Escape** clear search, **Ctrl+Z** undo, **Ctrl+R** reset. Tab and arrow keys navigate controls. Window dividers are resizable; minimum size is 1050 × 740 logical pixels.

## Analysis and datasets

Open **Analysis and local data** or **Review recommendations**. Select a supported historical patch, rank/competition and region/league. The table shows eligible candidates, comparative scores, evidence coverage and baseline observations. Click a row for component weights, raw wins/games, pair evidence, unknown-role weights and limitations. Ctrl-select up to three rows and use **Compare selected**. **Scoring settings** changes component weights, smoothing and minimum support.

The bundled historical data contains **1,716 professional games** across patches 16.17, 16.18, 16.20 and 16.22, from the publisher's CC BY 4.0 release. `PRO` is professional competition, not solo-queue rank. `GLOBAL` combines leagues; other region values are source league codes. Patch 16.20 is selected initially; 16.22 has just 32 games. Exact filters never silently mix datasets, leagues or patches.

**Scores are not win probabilities.** Correlated pair samples are not independent evidence. Coverage is a descriptive support measure, not a confidence interval. Insufficient evidence appears explicitly. Historical professional results do not establish current-patch or solo-queue strength. Composition uses documented class heuristics; no measured damage-profile claim is made.

**Import local data** accepts a JSON bundle or a CSV file inside a directory of table CSVs plus `metadata.json`. Imports require provenance/license fields, recognized names/roles, matching baselines, valid integer counts and unique composite-grain rows. Validation and writes are atomic. Reimporting the same content does not add counts. Changed snapshots remain separately selectable. DEMO datasets are prominently marked and never mixed implicitly with historical data, including their composition attributes.

See [import schema](../data/SCHEMA.md), [scoring method](SCORING.md) and [data sources](../DATA_SOURCES.md). The in-app **Sources and method** dialog includes attribution, method and notices. No dataset updates occur automatically.

## Local files and recovery

Data normally lives under `%LOCALAPPDATA%\LeagueDraftAssistant`:

- `draft-data.sqlite3`: writable copy of the bundled seed; later imports stay here.
- `preferences.json`: filters and scoring settings.
- `draft-state.json`: created only after enabling **Remember draft**.
- `application.log`: local rotating error log; no uploads or telemetry.

Sandboxed launches may redirect the Windows local data directory. Hover over Remember draft to see its exact recovery path. Enabling it saves immediately and after edits; unchecking removes the saved copy. On restart, valid saved state returns. Undo history/search are session-only. Invalid saved drafts are preserved with a visible warning. Corrupt databases are preserved under a timestamped `.corrupt-...` name, then replaced with the bundled seed. A newer unsupported database schema is left intact and reported as an error. All mutable files stay outside one-file extraction directories.

CLI overrides (also accepted by the EXE):

```powershell
.\.venv\Scripts\python.exe -m league_draft --data-dir '.\local app data'
.\.venv\Scripts\python.exe -m league_draft --state-file '.\draft-state.json'
.\.venv\Scripts\python.exe -m league_draft --no-restore
```

`--no-restore` starts with draft recovery disabled and does not change an existing saved draft unless Remember draft is explicitly enabled. Settings and the statistical database are separate from draft reset.

## Windows source setup

Requires **Python 3.12 x64** with pip/venv. Install it from [python.org](https://www.python.org/downloads/windows/) if needed. Setup downloads pinned dependencies; runtime is offline.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
.\.venv\Scripts\python.exe -m league_draft
```

Or use the helper, which handles sandbox temporary paths containing braces:

```powershell
.\scripts\setup.ps1
.\scripts\run.ps1
```

If `py` is absent: `.\scripts\setup.ps1 -Python 'C:\path\to\Python312\python.exe'`. Activation is optional; explicit venv paths avoid activation-policy issues. After activation, the equivalent launch command is `python -m league_draft`.

From Command Prompt:

```bat
cd /d "C:\path\to\League-of-legends-Ban-Pick-helper"
.venv\Scripts\python.exe -m league_draft
```

## Build and verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe .\scripts\benchmark.py
.\scripts\build.ps1
```

The build script produces a portable folder/ZIP first, then the single EXE, plus `dist\SHA256SUMS.txt`. The checked-in PyInstaller spec bundles Qt plugins, all portraits, migration SQL, source notices and the seed database. `-Mode OneDir` or `-Mode OneFile` builds one variant. It runs tests unless `-SkipTests` is explicitly supplied.

The spec deliberately excludes developer tools and pandas (only used for preparation). It also avoids a conflicting development-runtime ICU DLL: Qt uses the unversioned ICU API supplied by supported Windows versions. No Windows system DLL is copied into the product for that purpose. A debug console build is available through `LEAGUE_DEBUG_BUILD=1`; normal builds are windowed.

Tests cover model invariants, atomic swaps, Qt drop events, grayscale rendering, persistence/corruption, migrations, CSV/JSON import/reimport, exact filters, missing data, flex-role uncertainty, scoring bounds, zero weights, asynchronous analysis and local preferences. See TESTING.md for actual results and packaged-launch checks.

## Reproduce assets and historical aggregates

Network access is used only by these explicit development downloads. Runtime imports are local CSV/JSON only.

```powershell
.\.venv\Scripts\python.exe .\scripts\fetch_portraits.py
.\.venv\Scripts\python.exe .\scripts\prepare_history.py '.\chaincc-players-2026.csv.gz' --champion-metadata '.\champion-metadata.json' --database '.\rebuilt-seed.sqlite3'
.\.venv\Scripts\python.exe .\scripts\import_dataset.py .\data\demo --database '.\demo.sqlite3'
```

Source URLs, checksums, selected cohorts and transformations are in DATA_SOURCES.md and `data/chaincc/PROVENANCE.json`. The local source download is not required to run the app.

League Draft Assistant is not endorsed by Riot Games and does not reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games and all associated properties are trademarks or registered trademarks of Riot Games, Inc. Initial scope is offline simulation and comparative analysis; review current policies before public distribution or live-draft use. See THIRD_PARTY_NOTICES.md for bundled software and data notices.
