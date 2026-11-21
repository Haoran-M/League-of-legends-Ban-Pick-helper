import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication

from league_draft.domain.draft import DraftError, DraftModel, Kind, Role, Target, Team
from league_draft.domain.roster import load_roster
from league_draft.ui.drag_drop import mime_data
from league_draft.ui.main_window import MainWindow


def test_atomic_champion_and_role_swap(roster):
    model = DraftModel(roster)
    top, mid = Target(Team.BLUE, Kind.PICK, 0), Target(Team.BLUE, Kind.PICK, 2)
    model.assign(top, "Garen")
    model.assign(mid, "Ahri")
    before = model.state
    model.swap_champions(top, mid)
    assert model.state.blue_picks[0].champion == "Ahri"
    assert model.state.blue_picks[0].role == Role.TOP
    assert model.state.blue_picks[2].champion == "Garen"
    model.undo()
    assert model.state == before
    model.swap_roles(Team.BLUE, 0, 2)
    assert model.state.blue_picks[0].role == Role.MID
    assert model.state.blue_picks[0].champion == "Garen"
    model.undo()
    assert model.state == before
    empty = Target(Team.RED, Kind.PICK, 0)
    model.swap_champions(top, empty)
    assert model.state.blue_picks[0].champion is None
    assert model.state.red_picks[0].champion == "Garen"
    with pytest.raises(DraftError):
        model.swap_champions(empty, Target(Team.BLUE, Kind.BAN, 0))


def test_drop_events_swap_and_grayscale(app, tmp_path):
    roster, metadata = load_roster()
    window = MainWindow(roster, metadata, tmp_path / "draft.json")
    window.show()
    source, destination = Target(Team.BLUE, Kind.PICK, 0), Target(Team.BLUE, Kind.PICK, 2)
    window.model.assign(source, "Garen")
    window.model.assign(destination, "Ahri")
    window._render()
    button = window.slot_buttons[destination]
    mime = mime_data({"type": "slot", "team": "blue", "kind": "pick", "index": 0, "name": "Garen"})
    enter = QDragEnterEvent(button.rect().center(), Qt.DropAction.MoveAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(button, enter)
    assert enter.isAccepted()
    drop = QDropEvent(QPointF(button.rect().center()), Qt.DropAction.MoveAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(button, drop)
    assert window.model.state.blue_picks[2].champion == "Garen"
    box = window.role_boxes[Team.BLUE, 2]
    role_mime = mime_data({"type": "role", "team": "blue", "index": 0})
    enter = QDragEnterEvent(box.rect().center(), Qt.DropAction.MoveAction, role_mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(box, enter)
    drop = QDropEvent(QPointF(box.rect().center()), Qt.DropAction.MoveAction, role_mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(box, drop)
    assert window.model.state.blue_picks[2].role == Role.TOP
    for i in range(window.grid.count()):
        item = window.grid.item(i)
        if item.data(Qt.ItemDataRole.UserRole) == "Garen":
            image = item.icon().pixmap(32, 32).toImage()
            for y in range(image.height()):
                for x in range(image.width()):
                    color = image.pixelColor(x, y)
                    assert color.red() == color.green() == color.blue()
    window.close()
