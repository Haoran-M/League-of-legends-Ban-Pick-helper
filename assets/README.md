Champion square portraits are bundled in `src/league_draft/resources/icons/`.
`src/league_draft/resources/portraits.json` records each canonical name, Riot
Data Dragon source URL, byte count and SHA-256 hash for snapshot 16.23.1.

Refresh explicitly during development with:

```powershell
.\.venv\Scripts\python.exe .\scripts\fetch_portraits.py
```

This command needs network access; the application only reads the local PNGs.
Missing/unreadable portraits fall back to visible canonical-name text.
Champion portraits © Riot Games. Assets are not relicensed by this project.
See the README for Riot attribution and source/terms links.
