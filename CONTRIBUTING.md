# Contributing

Start with the [idea](docs/IDEA.md), [roadmap](docs/ROADMAP.md), [architecture](docs/ARCHITECTURE.md) and [scoring specification](docs/SCORING.md). Licensed average-player evidence and honest lane counters are the next priority.

## Workflow

1. Set up Python 3.12 x64 using `scripts/setup.ps1`; Android setup is in [android/README.md](android/README.md).
2. Describe a concrete player problem and resulting behavior.
3. Keep shared rules in the Python domain/storage/engine layers, avoiding platform-specific scoring formulas.
4. Add meaningful validation for model/import/recovery/scoring changes; describe manual checks for interface changes.
5. Run `.\.venv\Scripts\python.exe -m pytest -q` and relevant platform checks. Report actual results and remaining limits.
6. Update documentation when behavior, defaults, data or builds change.

Do not commit environments, caches, builds, user drafts, logs, keys, credentials or machine-local Android properties. The packaged seed database is intentional; private user databases are not.

## Data and scoring

Data proposals need a source URL, redistribution license, collection period, queue/rank definitions, patch/region, observed roles/opponents, outcome grain and sampling limitations. Follow [data/SCHEMA.md](data/SCHEMA.md), retain attribution and record transformations/checksums.

Do not scrape restricted sources, publish raw player identifiers, relabel pro data as solo queue, derive counters from unrelated baselines or invent missing observations. Synthetic data must remain DEMO and isolated. Keep exact filters, visible support and bounded scores. Difficulty metadata is not personal proficiency; a comparative score is not a win probability.

## Releases

Build outputs belong in release assets with checksums, source revision, dataset/signing descriptions and validation limits. Preserve upstream notices. Never publish private signing keys. Current local Android development signing is not a production-store process.
