# Offline import contract

Import a JSON object with `metadata` and any of the five table arrays below. `champion_stats` must contain at least one row, and `champion_roles` must declare each observed champion-role. See `src/league_draft/resources/demo.json` for a complete synthetic example.

Alternatively, select a CSV file inside a directory containing `metadata.json` plus CSVs named after the tables. CSV headers must follow the listed order exactly. Missing optional table files mean no rows. UTF-8 and UTF-8 BOM are accepted. See `data/demo`.

| Table | Columns in order |
| --- | --- |
| champions | name, class, damage_profile, attributes |
| champion_roles | name, role |
| champion_stats | name, role, patch, rank, region, wins, games |
| matchup_stats | name, opponent, role, opponent_role, patch, rank, region, wins, games |
| synergy_stats | name, ally, role, ally_role, patch, rank, region, wins, games |

Metadata requires nonempty `source`, `license`, `patch`, and a Boolean `is_demo`. Optional `notes` is text. Historical sources require an HTTP(S) provenance URL. Importing a license label does not independently verify the importer's permission to use the file. The bundled historical source was separately inspected for an explicit publisher license.

Champion names/aliases resolve against the local roster; stored keys are canonical names. Roles are exactly `Top`, `Jungle`, `Mid`, `ADC`, `Support`. Unknown roles are allowed in manual drafts, but aggregate input must have a recognized role. Counts are integers with `0 <= wins <= games`, `games > 0`. Nulls, unexpected fields, unknown champions/roles and duplicate composite-grain rows are rejected. Pair statistics require corresponding baselines and declared roles in the same filters. Row patches must match metadata. Opponent/ally must differ from candidate; ally roles must differ.

`attributes` is a JSON object, including when encoded in CSV. Allowed keys are `frontline`, `engage`, `utility`, `physical`, `magic`; finite numeric values range 0–1. Missing attributes remain unknown. These are documented heuristics, not observed statistics.

SQLite adds a dataset foreign key to the complete grain of every role/stat table. Composite primary keys include dataset + every dimension except wins/games. Dataset metadata uses a deterministic normalized-content identity. Reimporting the same JSON/CSV content does nothing; changed content is a separately selectable snapshot rather than added to previous counts. SQLite foreign keys, integer/count checks and an atomic transaction enforce integrity. Queries use exact filters and bound parameters. No patch fallback or implicit cross-source merge occurs.

CLI example:

```powershell
.\.venv\Scripts\python.exe .\scripts\import_dataset.py .\src\league_draft\resources\demo.json --database '.\demo.sqlite3'
.\.venv\Scripts\python.exe .\scripts\import_dataset.py .\data\demo --database '.\demo.sqlite3'
```
