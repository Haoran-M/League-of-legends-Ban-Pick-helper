from contextlib import closing
import json
from pathlib import Path
import time

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from league_draft.domain.draft import Kind, Target, Team
from league_draft.domain.roster import load_roster
from league_draft.storage.bootstrap import prepare_database
from league_draft.storage.database import connect, initialize
from league_draft.storage.importer import import_bundle
from league_draft.ui.main_window import MainWindow

ROOT = Path(__file__).resolve().parents[1]


def until(predicate, timeout=8000):
    started = time.perf_counter()
    while not predicate():
        assert (time.perf_counter() - started) * 1000 < timeout, "UI worker did not finish"
        QApplication.processEvents()
        # Let Python QRunnable work acquire the GIL as well as pumping Qt events.
        time.sleep(0.01)


def test_real_data_recalculation_filters_and_preferences(app, tmp_path):
    roster, metadata = load_roster()
    path = tmp_path / "db.sqlite3"
    prepare_database(path, roster)
    preferences = tmp_path / "preferences.json"
    window = MainWindow(roster, metadata, tmp_path / "draft.json", database_path=path, preferences_path=preferences)
    window.show()
    panel = window.analysis_panel
    until(lambda: panel.last_elapsed_ms is not None)
    assert panel.current_filters().patch == "16.20"
    assert panel.current_filters().region == "GLOBAL"
    assert "HISTORICAL PROFESSIONAL" in panel.source_label.text()
    assert panel.table.rowCount() > 0
    window._edit(lambda: window.model.assign(Target(Team.BLUE, Kind.PICK, 2), "Ahri"), "test edit")
    until(lambda: all(c.name != "Ahri" for c in panel.latest_results))
    panel.region.setCurrentIndex(1)
    expected_region = panel.region.currentText()
    until(lambda: "Calculating" not in panel.status.text())
    saved = json.loads(preferences.read_text(encoding="utf-8"))
    assert saved["region"] == expected_region
    window.close()
    recovered = MainWindow(roster, metadata, tmp_path / "draft.json", database_path=path, preferences_path=preferences)
    assert recovered.analysis_panel.region.currentText() == expected_region
    recovered.close()


def test_import_demo_twice_and_reject_bad_import(app, tmp_path):
    roster, metadata = load_roster()
    path = tmp_path / "db.sqlite3"
    initialize(path, roster)
    window = MainWindow(roster, metadata, tmp_path / "draft.json", database_path=path)
    panel = window.analysis_panel
    panel.import_path(ROOT / "src/league_draft/resources/demo.json")
    until(lambda: panel.last_elapsed_ms is not None)
    assert "DEMO / SYNTHETIC" in panel.source_label.text()
    with closing(connect(path)) as db:
        before = db.execute("SELECT count(*) FROM champion_stats").fetchone()[0]
    panel.import_path(ROOT / "src/league_draft/resources/demo.json")
    until(lambda: panel.import_button.isEnabled())
    with closing(connect(path)) as db:
        assert db.execute("SELECT count(*) FROM champion_stats").fetchone()[0] == before
        assert db.execute("SELECT count(*) FROM dataset_metadata").fetchone()[0] == 1
    broken = tmp_path / "broken.json"
    broken.write_text('{"metadata":{}}', encoding="utf-8")
    until(lambda: "Calculating" not in panel.status.text())
    panel.import_path(broken)
    until(lambda: "failed" in panel.status.text().lower())
    with closing(connect(path)) as db:
        assert db.execute("SELECT count(*) FROM dataset_metadata").fetchone()[0] == 1
    window.close()
