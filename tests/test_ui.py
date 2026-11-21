import os
from pathlib import Path
import subprocess
import sys

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from league_draft.domain.draft import DraftState, Kind, Role, Target, Team
from league_draft.domain.roster import load_roster
from league_draft.ui.main_window import MainWindow


@pytest.fixture
def window(app, tmp_path):
    roster, metadata = load_roster()
    result = MainWindow(roster, metadata, tmp_path / "draft.json")
    result.show()
    app.processEvents()
    yield result
    result.close()
    result.deleteLater()
    app.processEvents()


def select_and_search(window, target, name):
    QTest.mouseClick(window.slot_buttons[target], Qt.MouseButton.LeftButton)
    window.search.setFocus()
    window.search.selectAll()
    QTest.keyClicks(window.search, name)
    QTest.keyClick(window.search, Qt.Key.Key_Return)


def test_complete_draft_through_widgets_and_restart(window, app):
    # Synthetic draft choices only, not match observations or recommendations.
    names = iter(window.roster.names[:20])
    for kind in Kind:
        for team in Team:
            for index in range(5):
                target = Target(team, kind, index)
                champion = next(names)
                select_and_search(window, target, champion)
                assert window.model.state.champion_at(target) == champion
    assert "10/10 picks · 10/10 bans" in window.summary.text()
    snapshot = window.model.state
    window.remember.click()
    assert window.state_path.exists()
    # Start a separate interpreter and Qt application to verify on-disk recovery.
    code = """
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from league_draft.domain.roster import load_roster
from league_draft.ui.main_window import MainWindow
app = QApplication([])
roster, metadata = load_roster()
window = MainWindow(roster, metadata, Path(sys.argv[1]))
assert window.remember.isChecked()
assert '10/10 picks · 10/10 bans' in window.summary.text()
assert not window.model.can_undo
print('Recovered full draft in fresh process')
"""
    completed = subprocess.run([sys.executable, "-c", code, str(window.state_path)],
                               capture_output=True, text=True, timeout=20)
    assert completed.returncode == 0, completed.stderr
    select_and_search(window, Target(Team.BLUE, Kind.PICK, 0), window.roster.names[20])
    assert window.model.state != snapshot
    QTest.mouseClick(window.undo_button, Qt.MouseButton.LeftButton)
    assert window.model.state == snapshot
    QTest.mouseClick(window.reset_button, Qt.MouseButton.LeftButton)
    assert window.model.state == DraftState()
    QTest.mouseClick(window.undo_button, Qt.MouseButton.LeftButton)
    assert window.model.state == snapshot
    window.remember.click()
    assert not window.state_path.exists()


def test_rejections_visible_and_clear_slot(window):
    select_and_search(window, Target(Team.BLUE, Kind.PICK, 0), "Ahri")
    select_and_search(window, Target(Team.RED, Kind.PICK, 0), "Ahri")
    assert "already picked" in window.statusBar().currentMessage()
    assert window.model.state.red_picks[0].champion is None
    select_and_search(window, Target(Team.RED, Kind.BAN, 0), "Garen")
    select_and_search(window, Target(Team.BLUE, Kind.PICK, 1), "Garen")
    assert "banned champion" in window.statusBar().currentMessage()
    assert window.model.state.blue_picks[1].champion is None
    select_and_search(window, Target(Team.BLUE, Kind.PICK, 0), "Akali")
    assert window.model.state.blue_picks[0].champion == "Akali"
    QTest.mouseClick(window.clear_button, Qt.MouseButton.LeftButton)
    assert window.model.state.blue_picks[0].champion is None


def test_roles_controls_and_empty_search(window):
    window.user_role.setCurrentIndex(window.user_role.findData(Role.SUPPORT))
    window.user_team.setCurrentIndex(window.user_team.findData(Team.RED))
    assert window.model.state.user_role == Role.SUPPORT
    assert window.model.state.user_team == Team.RED
    box = window.role_boxes[Team.RED, 0]
    box.setCurrentIndex(box.findData(Role.MID))
    duplicate = window.role_boxes[Team.RED, 1]
    duplicate.setCurrentIndex(duplicate.findData(Role.MID))
    assert duplicate.currentData() is None
    assert "already has that role" in window.statusBar().currentMessage()
    window.search.setText("zzzznomatch")
    assert window.grid.count() == 0
    assert "No matching" in window.result_count.text()
    QTest.keyClick(window.search, Qt.Key.Key_Return)


def test_bad_recovery_and_no_restore(window, tmp_path):
    path = tmp_path / "corrupt.json"
    path.write_text("not json", encoding="utf-8")
    other = MainWindow(window.roster, window.metadata, path)
    assert "Recovery failed" in other.statusBar().currentMessage()
    assert not other.remember.isChecked()
    assert path.read_text(encoding="utf-8") == "not json"
    other.close()
    clean = MainWindow(window.roster, window.metadata, path, restore=False)
    assert clean.model.state == DraftState()
    assert "Recovery failed" not in clean.statusBar().currentMessage()
    clean.close()


def test_save_failure_is_visible(window, tmp_path):
    parent = tmp_path / "file-not-directory"
    parent.write_text("fixture", encoding="utf-8")
    window.state_path = parent / "draft.json"
    window.remember.click()
    assert "saving failed" in window.statusBar().currentMessage()
    select_and_search(window, Target(Team.BLUE, Kind.PICK, 0), "Ahri")
    assert window.model.state.blue_picks[0].champion == "Ahri"
    assert "saving failed" in window.statusBar().currentMessage()


def test_module_launch_stays_running_offline(tmp_path):
    environment = os.environ.copy()
    environment.update({"HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9"})
    process = subprocess.Popen([sys.executable, "-m", "league_draft", "--no-restore",
                                "--data-dir", str(tmp_path / "app-data"),
                                "--state-file", str(tmp_path / "draft.json")],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment)
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            process.wait(timeout=2)
    finally:
        process.terminate()
        _, stderr = process.communicate(timeout=10)
    assert b"Traceback" not in stderr
    assert not (tmp_path / "draft.json").exists()
