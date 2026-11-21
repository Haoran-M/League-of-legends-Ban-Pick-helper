"""Source and frozen entry point. Runtime reads only local files."""

import argparse
from contextlib import closing
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sqlite3
import sys
import time
import os

from PySide6.QtCore import QStandardPaths, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from league_draft.domain.roster import load_roster
from league_draft.storage.bootstrap import prepare_database
from league_draft.storage.database import connect
from league_draft.ui.main_window import MainWindow


def main() -> int:
    started = time.perf_counter()
    parser = argparse.ArgumentParser(description="Manual offline League draft assistant")
    parser.add_argument("--state-file", type=Path, help="Override the optional local draft recovery file")
    parser.add_argument("--data-dir", type=Path, help="Override the writable local data directory")
    parser.add_argument("--no-restore", action="store_true", help="Start fresh without reading or changing an existing saved draft")
    parser.add_argument("--self-test", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    app = QApplication([sys.argv[0]])
    app.setApplicationName("LeagueDraftAssistant")
    app.setOrganizationName("LeagueDraftAssistant")
    app.setStyle("Fusion")
    default = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericDataLocation))
    directory = args.data_dir or default / "LeagueDraftAssistant"
    state_path = args.state_file or directory / "draft-state.json"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(directory / "application.log", maxBytes=2_000_000, backupCount=2, encoding="utf-8")
        logging.basicConfig(handlers=[handler], level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", force=True)
        roster, metadata = load_roster()
        database_path = directory / "draft-data.sqlite3"
        notice = prepare_database(database_path, roster)
        if notice:
            logging.warning(notice)
        window = MainWindow(roster, metadata, state_path, restore=not args.no_restore,
                            database_path=database_path, preferences_path=directory / "preferences.json")
        if notice:
            window._message(notice, error=True)
    except (OSError, ValueError, KeyError, sqlite3.Error) as exc:
        logging.exception("Application startup failed")
        if args.self_test:
            args.self_test.parent.mkdir(parents=True, exist_ok=True)
            args.self_test.write_text(json.dumps({"ok": False, "error": str(exc)}), encoding="utf-8")
        else:
            QMessageBox.critical(None, "Cannot start League Draft Assistant",
                                 f"Local files could not be prepared. Check the data directory and application.log.\n\n{exc}")
        return 1

    def unhandled(kind, value, traceback):
        logging.error("Unhandled application error", exc_info=(kind, value, traceback))
        QMessageBox.warning(window, "An operation failed", "The operation could not finish. Your draft remains in memory. Details are in the local application.log.")
    sys.excepthook = unhandled

    if args.self_test:
        def check():
            panel = window.analysis_panel
            if panel.last_elapsed_ms is None and time.perf_counter() - started < 20:
                QTimer.singleShot(50, check)
                return
            try:
                ready_ms = (time.perf_counter() - started) * 1000
                with closing(connect(database_path)) as db:
                    integrity = db.execute("PRAGMA quick_check").fetchone()[0]
                    datasets = db.execute("SELECT count(*) FROM dataset_metadata").fetchone()[0]
                portrait_count = sum(not window.portraits.icon(name).isNull() for name in roster.names)
                # Diagnostic probes use disposable files and never edit the working draft.
                from league_draft.domain.draft import DraftModel, DraftError, Kind, Target, Team
                from league_draft.storage.session import load_session, save_session
                from league_draft.storage.database import initialize
                from league_draft.storage.importer import import_bundle
                from importlib.resources import files
                probe = DraftModel(roster)
                names = iter(roster.names[:20])
                for kind in Kind:
                    for team in Team:
                        for index in range(5):
                            probe.assign(Target(team, kind, index), next(names))
                completed_draft = probe.state
                first = Target(Team.BLUE, Kind.PICK, 0)
                second = Target(Team.BLUE, Kind.PICK, 1)
                try:
                    probe.assign(first, completed_draft.blue_picks[1].champion)
                    raise AssertionError("Duplicate pick was accepted")
                except DraftError:
                    pass
                try:
                    probe.assign(first, completed_draft.blue_bans[0])
                    raise AssertionError("Banned pick was accepted")
                except DraftError:
                    pass
                probe.swap_champions(first, second)
                probe.undo()
                assert probe.state == completed_draft
                probe.reset(); probe.undo()
                assert probe.state == completed_draft
                probe_path = directory / f".self-test-{os.getpid()}.json"
                probe_database = directory / f".self-test-{os.getpid()}.sqlite3"
                try:
                    save_session(probe_path, probe.state, roster)
                    assert load_session(probe_path, roster) == completed_draft
                    initialize(probe_database, roster)
                    demo = json.loads(files("league_draft").joinpath("resources/demo.json").read_text(encoding="utf-8"))
                    with closing(connect(probe_database)) as db:
                        dataset_id, changed = import_bundle(db, demo, roster)
                        assert changed
                        assert import_bundle(db, demo, roster) == (dataset_id, False)
                finally:
                    probe_path.unlink(missing_ok=True)
                    probe_database.unlink(missing_ok=True)
                report = {"ok": integrity == "ok" and portrait_count == len(roster.names) and datasets > 0 and panel.last_elapsed_ms is not None,
                          "frozen": bool(getattr(sys, "frozen", False)), "portraits": portrait_count, "datasets": datasets,
                          "startup_ms": ready_ms, "analysis_ms": panel.last_elapsed_ms,
                          "candidates": len(panel.latest_results), "supported_candidates": sum(c.score is not None for c in panel.latest_results),
                          "top": [{"name": c.name, "score": c.score, "coverage": c.coverage} for c in panel.latest_results[:5]],
                          "database": str(database_path), "integrity": integrity, "notice": notice,
                          "workflow_probe": "full draft, rejection, swap, undo/reset, JSON roundtrip, atomic demo import and reimport passed",
                          "recovered_picks": sum(p.champion is not None for team in Team for p in window.model.state.picks(team)),
                          "recovered_bans": sum(b is not None for team in Team for b in window.model.state.bans(team)),
                          "remember_draft": window.remember.isChecked()}
            except Exception as exc:
                logging.exception("Self-test failed")
                report = {"ok": False, "error": str(exc)}
            args.self_test.parent.mkdir(parents=True, exist_ok=True)
            args.self_test.write_text(json.dumps(report, indent=2), encoding="utf-8")
            window.close()
            app.exit(0 if report["ok"] else 1)
        QTimer.singleShot(0, check)
    else:
        window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
