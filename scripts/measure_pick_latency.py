"""Measure pick-to-rendered-recommendations latency against a 10-second budget.

Synthetic manual draft choices exercise the real Qt UI and historical database.
The stopwatch includes assignment, redraw, debounce, worker and result-table update.
"""

import json
from pathlib import Path
import statistics
import time

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from league_draft.domain.draft import Kind, Target, Team
from league_draft.domain.roster import load_roster
from league_draft.ui.main_window import MainWindow


def main():
    root = Path(__file__).resolve().parents[1]
    app = QApplication([])
    app.setStyle("Fusion")
    roster, metadata = load_roster()
    window = MainWindow(roster, metadata, root / ".tmp/latency-fixture.json", restore=False,
                        database_path=root / "src/league_draft/resources/seed.sqlite3")
    window.show()
    panel = window.analysis_panel
    finished = []
    panel.summaryChanged.connect(lambda _: finished.append((panel.token, time.perf_counter())))

    def wait_for(token):
        deadline = time.perf_counter() + 10
        while not any(t == token for t, _ in finished):
            if time.perf_counter() >= deadline:
                raise RuntimeError(f"Exceeded 10-second budget: {panel.status.text()}")
            app.processEvents()
            time.sleep(.003)
        return next(stamp for t, stamp in reversed(finished) if t == token)

    records = []
    try:
        for dataset_index in range(panel.dataset.count()):
            panel.dataset.setCurrentIndex(dataset_index)
            if panel.last_elapsed_ms is None or "Calculating" in panel.status.text():
                wait_for(panel.token)
            patch = panel.current_filters().patch
            for cache_mode in ("warm", "cold"):
                window._edit(window.model.reset, "Reset latency fixture")
                if "Calculating" in panel.status.text():
                    wait_for(panel.token)
                for number, champion in enumerate(roster.names[:10]):
                    target = Target(Team.BLUE if number < 5 else Team.RED, Kind.PICK, number % 5)
                    QTest.mouseClick(window.slot_buttons[target], Qt.MouseButton.LeftButton)
                    window.search.setText(champion)
                    if cache_mode == "cold":
                        panel.snapshot_cache.clear()
                    started = time.perf_counter()
                    QTest.keyClick(window.search, Qt.Key.Key_Return)
                    token = panel.token
                    ended = wait_for(token)
                    if window.model.state.champion_at(target) != champion:
                        raise RuntimeError(f"Pick fixture failed for {champion}")
                    records.append({"patch": patch, "cache": cache_mode, "pick": number + 1,
                                    "champion": champion, "ui_update_ms": (ended - started) * 1000})
        values = sorted(r["ui_update_ms"] for r in records)
        report = {"budget_ms": 10000, "cases": len(records), "all_within_budget": max(values) < 10000,
                  "median_ui_update_ms": statistics.median(values),
                  "p95_ui_update_ms": values[int((len(values) - 1) * .95)], "max_ui_update_ms": max(values),
                  "scope": "Source Qt UI, same Windows machine; four bundled patches, warm/cold snapshot cache; 10 sequential picks each. Includes debounce and visible table update.",
                  "results": records}
        output = root / "test-artifacts/pick-latency.json"
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({k: v for k, v in report.items() if k != "results"}, indent=2))
    finally:
        window.close()


if __name__ == "__main__":
    main()
