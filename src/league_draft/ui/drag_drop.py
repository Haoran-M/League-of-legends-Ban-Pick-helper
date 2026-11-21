"""Native Qt drag/drop. Click, keyboard and dropdown editing remain available."""

import json

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QApplication, QComboBox, QListWidget, QPushButton

MIME = "application/x-league-draft-slot"


def mime_data(payload: dict) -> QMimeData:
    mime = QMimeData()
    mime.setData(MIME, json.dumps(payload).encode("utf-8"))
    return mime


def read_payload(mime: QMimeData) -> dict | None:
    if not mime.hasFormat(MIME):
        return None
    raw = bytes(mime.data(MIME))
    if len(raw) > 1024:
        return None
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict) and payload.get("type") in {"champion", "slot", "role"}:
            return payload
    except (ValueError, TypeError):
        pass
    return None


class SlotButton(QPushButton):
    dropped = Signal(dict)

    def __init__(self, target):
        super().__init__()
        self.target = target
        self.champion = None
        self._press = None
        self.setAcceptDrops(True)

    def mousePressEvent(self, event):
        self._press = event.position().toPoint() if event.button() == Qt.MouseButton.LeftButton else None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self.champion and self._press is not None and event.buttons() & Qt.MouseButton.LeftButton
                and (event.position().toPoint() - self._press).manhattanLength() >= QApplication.startDragDistance()):
            self._press = None
            self.setDown(False)
            drag = QDrag(self)
            drag.setMimeData(mime_data({"type": "slot", "team": self.target.team.value,
                                       "kind": self.target.kind.value, "index": self.target.index,
                                       "name": self.champion}))
            drag.setPixmap(self.icon().pixmap(48, 48))
            drag.exec(Qt.DropAction.MoveAction)
            return
        super().mouseMoveEvent(event)

    def dragEnterEvent(self, event):
        payload = read_payload(event.mimeData())
        if payload and payload["type"] in {"champion", "slot"}:
            event.acceptProposedAction()

    def dropEvent(self, event):
        payload = read_payload(event.mimeData())
        if payload and payload["type"] in {"champion", "slot"}:
            self.dropped.emit(payload)
            event.acceptProposedAction()


class RoleComboBox(QComboBox):
    dropped = Signal(dict)

    def __init__(self, team, index):
        super().__init__()
        self.team, self.index = team, index
        self._press = None
        self._dragged = False
        self.setAcceptDrops(True)
        self.setToolTip("Click to choose a role, or drag onto another role on this side to swap.")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.position().toPoint()
            self._dragged = False
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self._press is not None and event.buttons() & Qt.MouseButton.LeftButton
                and (event.position().toPoint() - self._press).manhattanLength() >= QApplication.startDragDistance()):
            self._press = None
            self._dragged = True
            drag = QDrag(self)
            drag.setMimeData(mime_data({"type": "role", "team": self.team.value, "index": self.index}))
            drag.setPixmap(self.grab())
            drag.exec(Qt.DropAction.MoveAction)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = None
            if not self._dragged:
                self.showPopup()
            self._dragged = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        payload = read_payload(event.mimeData())
        if payload and payload["type"] == "role":
            event.acceptProposedAction()

    def dropEvent(self, event):
        payload = read_payload(event.mimeData())
        if payload and payload["type"] == "role":
            self.dropped.emit(payload)
            event.acceptProposedAction()


class ChampionGrid(QListWidget):
    def __init__(self):
        super().__init__()
        self.setDragEnabled(True)

    def startDrag(self, supported_actions):
        item = self.currentItem()
        if item is None:
            return
        drag = QDrag(self)
        drag.setMimeData(mime_data({"type": "champion", "name": item.data(Qt.ItemDataRole.UserRole)}))
        drag.setPixmap(item.icon().pixmap(58, 58))
        drag.exec(Qt.DropAction.CopyAction)
