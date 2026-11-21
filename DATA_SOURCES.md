# Data sources and attribution

## Historical match observations

**ChainCC. League of Legends esports match dataset.**

- Publisher/download page: https://chaincc.lol/free/data
- Publication license: **Creative Commons Attribution 4.0 International (CC BY 4.0)**, as declared by the publisher on that page.
- License: https://creativecommons.org/licenses/by/4.0/
- Source: https://chaincc.lol/data/chaincc-players-2026.csv.gz
- Downloaded: 2026-11-21.
- Source SHA-256: `a79b5434e047311b235d04fd5d38b2bb087f575b59349d62ae6b2c49336d586c`.
- Publisher methodology: https://chaincc.lol/about/methodology

Changes: selected four patch cohorts; normalized canonical champion names and role labels; validated complete games; aggregated directed champion-role baseline, matchup and synergy wins/games separately by patch and league; removed player, team and game identifiers. The resulting aggregates retain **CC BY 4.0**. The underlying download contains 99,430 player rows from 9,943 games. The bundled subset contains **1,716 games**, partitioned as follows:

| Patch | Complete games | Earliest game | Latest game |
| --- | ---: | --- | --- |
| 16.17 | 797 | 2026-08-27 | 2026-10-13 |
| 16.18 | 571 | 2026-09-19 | 2026-10-17 |
| 16.20 | 316 | 2026-10-09 | 2026-11-19 |
| 16.22 | 32 | 2026-11-06 | 2026-11-15 |

The source publisher identifies Oracle's Elixir as a historical scoreboard/draft input and Leaguepedia as an additional esports metadata source. The application uses the publisher's downloadable licensed release; it does not scrape those sites or use their live APIs. No player performance features are used in scoring.

`PRO` means professional competition, **not a solo-queue rank**. `GLOBAL` is a union of professional leagues; other values in the Region / league selector are source league codes, not inferred geographic regions. GLOBAL rows and individual leagues are alternative exact filters and are never summed together. Patches are also never combined implicitly. Patch 16.20 is the initial selection; 16.22 has only 32 source games and very limited support. Nothing here establishes current-patch or solo-queue performance.

Audit output: `data/chaincc/PROVENANCE.json`. Reproduce from the same downloaded CSV and Riot metadata using `scripts/prepare_history.py`. The compressed source is development input under ignored `.tmp/sources`; the application bundles only aggregate SQLite tables. The CSV is not needed at runtime.

## Roster, portraits and class metadata

Riot Games Data Dragon **16.23.1** supplies the 173 canonical names, champion square portraits and class tags. Exact portrait URLs, sizes and hashes are in `resources/portraits.json`. Roster provenance is in `resources/champions.json`.

- Documentation: https://developer.riotgames.com/docs/lol#data-dragon
- Metadata: https://ddragon.leagueoflegends.com/cdn/16.23.1/data/en_US/champion.json
- Terms: https://www.riotgames.com/en/legal

Portraits and Riot metadata are not relicensed as CC BY. Composition values are this application's explicit heuristics derived from class tags, not measured player statistics. Tank: frontline 1, engage 0.7. Fighter without Tank: frontline 0.4, engage 0.3. Support: utility 1. Other listed attributes are 0. Damage profile is Unknown; the app does not infer physical/magic damage from class tags. The pinned class snapshot may differ from the historical match patch.

League Draft Assistant is not endorsed by Riot Games and does not reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games and all associated properties are trademarks or registered trademarks of Riot Games, Inc.

Initial use is offline simulation and comparative analysis. Review current Riot policies before public distribution or live-draft use.

## Synthetic examples

`resources/demo.json` and `data/demo/*.csv` are clearly marked **DEMO**. Their counts are generated workflow fixtures, not observations. They are kept separate from historical datasets and marked prominently if imported. The synthetic examples are offered under CC0-1.0; that declaration does not apply to Riot assets or ChainCC data.
