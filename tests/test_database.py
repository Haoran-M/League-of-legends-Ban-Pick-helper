from copy import deepcopy
import json
from pathlib import Path
import sqlite3

import pytest

from league_draft.storage.database import connect, initialize
from league_draft.storage.importer import ImportError, import_bundle, load_bundle
from league_draft.storage.repository import Filters, Repository
from league_draft.storage.bootstrap import prepare_database


@pytest.fixture
def bundle():
    return json.loads((Path(__file__).resolve().parents[1] / "src/league_draft/resources/demo.json").read_text(encoding="utf-8"))


def test_idempotent_import_and_exact_filters(roster, tmp_path, bundle):
    path = tmp_path / "test.sqlite3"
    initialize(path, roster)
    with connect(path) as db:
        dataset_id, changed = import_bundle(db, bundle, roster)
        assert changed
        counts = [db.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("champion_stats", "matchup_stats", "synergy_stats")]
        assert import_bundle(db, bundle, roster) == (dataset_id, False)
        assert counts == [db.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("champion_stats", "matchup_stats", "synergy_stats")]
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    repository = Repository(path)
    snapshot = repository.load(Filters(dataset_id, "DEMO", "DEMO", "DEMO"))
    assert snapshot.baselines["Ahri", "Mid"].games == 200
    for field, bad in (("patch", "different"), ("rank", "different"), ("region", "different"), ("dataset_id", "different")):
        values = dict(dataset_id=dataset_id, patch="DEMO", rank="DEMO", region="DEMO")
        values[field] = bad
        assert not repository.load(Filters(**values)).baselines


@pytest.mark.parametrize("issue", ["wins", "negative", "float", "zero", "unknown", "role", "duplicate", "alias_duplicate", "missing", "provenance", "patch", "nan", "pair_baseline", "pair_support"])
def test_reject_invalid_atomically(roster, tmp_path, bundle, issue):
    broken = deepcopy(bundle)
    row = broken["champion_stats"][0]
    if issue == "wins": row["wins"] = row["games"] + 1
    if issue == "negative": row["wins"] = -1
    if issue == "float": row["games"] = 100.5
    if issue == "zero": row["games"] = row["wins"] = 0
    if issue == "unknown": row["name"] = "not a champion"
    if issue == "role": row["role"] = "Carry"
    if issue == "duplicate": broken["champion_stats"].append(deepcopy(row))
    if issue == "alias_duplicate":
        copy = deepcopy(row); copy["name"] = copy["name"].lower()
        broken["champion_stats"].append(copy)
    if issue == "missing": del row["games"]
    if issue == "provenance": broken["metadata"]["license"] = ""
    if issue == "patch": row["patch"] = "different"
    if issue == "nan": broken["champions"][0]["attributes"]["frontline"] = float("nan")
    if issue == "pair_baseline": broken["champion_stats"] = broken["champion_stats"][1:]
    if issue == "pair_support": broken["matchup_stats"][0]["games"] = 1000
    path = tmp_path / "test.sqlite3"
    initialize(path, roster)
    with connect(path) as db:
        with pytest.raises(ImportError): import_bundle(db, broken, roster)
        assert db.execute("SELECT count(*) FROM dataset_metadata").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM champion_stats").fetchone()[0] == 0


def test_sql_constraints_and_recovery(roster, tmp_path, bundle):
    path = tmp_path / "test.sqlite3"
    initialize(path, roster)
    with connect(path) as db:
        dataset_id, _ = import_bundle(db, bundle, roster)
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO champion_roles VALUES (?,?,?)", (dataset_id, "unknown", "Mid"))
        db.rollback()
    db.close()
    path.write_bytes(b"corrupt sqlite fixture")
    notice = prepare_database(path, roster)
    assert "preserved" in notice
    assert len(list(tmp_path.glob("*.corrupt-*"))) == 1
    with connect(path) as db:
        assert db.execute("PRAGMA quick_check").fetchone()[0] == "ok"


def test_csv_directory_matches_json(roster, tmp_path, bundle):
    source = Path(__file__).resolve().parents[1] / "data/demo"
    path = tmp_path / "test.sqlite3"
    initialize(path, roster)
    with connect(path) as db:
        first, _ = import_bundle(db, bundle, roster)
        assert import_bundle(db, load_bundle(source), roster) == (first, False)


def test_demo_attributes_do_not_change_historical_snapshot(roster, tmp_path, bundle):
    path = tmp_path / "db.sqlite3"
    prepare_database(path, roster)
    repository = Repository(path)
    row = next(d for d in repository.datasets() if d["patch"] == "16.20")
    filters = Filters(row["id"], "16.20", "PRO", "GLOBAL")
    before = repository.load(filters).attributes
    with connect(path) as db:
        import_bundle(db, bundle, roster)
    assert repository.load(filters).attributes == before
