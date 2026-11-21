"""Offline importer for a JSON bundle or a directory of schema-compliant CSVs."""

import argparse
from contextlib import closing
from pathlib import Path

from league_draft.domain.roster import load_roster
from league_draft.storage.database import connect, initialize
from league_draft.storage.importer import import_bundle, load_bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args()
    roster, _ = load_roster()
    initialize(args.database, roster)
    with closing(connect(args.database)) as db:
        dataset_id, changed = import_bundle(db, load_bundle(args.dataset), roster)
    print(f"{'Imported' if changed else 'Already imported'}: {dataset_id}")


if __name__ == "__main__":
    main()
