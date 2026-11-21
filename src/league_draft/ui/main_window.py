from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QColor, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListView, QListWidget, QListWidgetItem, QMainWindow,
    QPushButton, QScrollArea, QSplitter, QTabWidget, QVBoxLayout, QWidget,
)

from league_draft.domain.draft import DraftError, DraftModel, Kind, Role, Target, Team
from league_draft.domain.roster import Roster
from league_draft.storage.session import SessionError, load_session, save_session
from .portraits import Portraits
from .drag_drop import ChampionGrid, RoleComboBox, SlotButton
from .analysis_panel import AnalysisPanel
from .theme import STYLE


def label(text: str, name: str | None = None, wrap: bool = False) -> QLabel:
    result = QLabel(text)
    if name:
        result.setObjectName(name)
    result.setWordWrap(wrap)
    return result


class MainWindow(QMainWindow):
    def __init__(self, roster: Roster, metadata: dict, state_path: Path, *, restore: bool = True,
                 database_path: Path | None = None, preferences_path: Path | None = None):
        super().__init__()
        self.roster, self.metadata, self.state_path = roster, metadata, state_path
        self.model = DraftModel(roster)
        self.portraits = Portraits()
        self.target = Target(Team.BLUE, Kind.PICK, 0)
        self.slot_buttons: dict[Target, QPushButton] = {}
        self.role_boxes: dict[tuple[Team, int], QComboBox] = {}
        self.team_panels: list[QFrame] = []
        self.persistence_error = ""
        self._rendering = False
        restored = False
        startup_message = "Select a pick or ban slot, then choose a champion. All input stays local."
        if restore and state_path.exists():
            try:
                self.model = DraftModel(roster, load_session(state_path, roster))
                restored = True
                startup_message = "Recovered your saved draft. Undo history begins with this session."
            except (SessionError, OSError) as exc:
                startup_message = f"Recovery failed: {exc}"
        self.setWindowTitle("League Draft Assistant • Offline workspace")
        self.resize(1280, 860)
        self.setMinimumSize(1050, 740)
        self.setStyleSheet(STYLE)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(22, 18, 22, 10)
        layout.setSpacing(14)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(label("LEAGUE / DRAFT ASSISTANT", "title"))
        titles.addWidget(label("Manual draft workspace  •  Local input  •  Offline simulation", "subtitle"))
        header.addLayout(titles)
        header.addStretch()
        header.addWidget(label("OFFLINE · MANUAL INPUT", "badge"))
        layout.addLayout(header)

        toolbar = QHBoxLayout()
        self.user_team = QComboBox()
        self.user_team.setAccessibleName("Your team")
        for team in Team:
            self.user_team.addItem(team.value.title(), team)
        self.user_team.currentIndexChanged.connect(self._user_changed)
        toolbar.addWidget(label("Your team"))
        toolbar.addWidget(self.user_team)
        self.user_role = QComboBox()
        self.user_role.setAccessibleName("Your role")
        for role in Role:
            self.user_role.addItem(role.value, role)
        self.user_role.currentIndexChanged.connect(self._user_changed)
        toolbar.addWidget(label("Your role"))
        toolbar.addWidget(self.user_role)
        toolbar.addStretch()
        self.remember = QCheckBox("Remember draft")
        self.remember.setAccessibleName("Remember draft between app launches")
        self.remember.setToolTip(f"Opt-in local recovery file:\n{state_path}\nUncheck to remove the saved copy.")
        self.remember.setChecked(restored)
        self.remember.toggled.connect(self._toggle_remember)
        toolbar.addWidget(self.remember)
        self.undo_button = QPushButton("Undo")
        self.undo_button.setToolTip("Undo the last edit (Ctrl+Z), including reset")
        self.undo_button.clicked.connect(self._undo)
        toolbar.addWidget(self.undo_button)
        self.reset_button = QPushButton("Reset draft")
        self.reset_button.setToolTip("Clear the draft and restore default roles (Ctrl+R). Undo restores it.")
        self.reset_button.clicked.connect(lambda: self._edit(self.model.reset, "Draft reset. Undo restores the previous draft."))
        toolbar.addWidget(self.reset_button)
        layout.addLayout(toolbar)

        self.tabs = QTabWidget()
        self.tabs.setAccessibleName("Draft and analysis views")
        draft_page = QWidget()
        draft_layout = QVBoxLayout(draft_page)
        draft_layout.setContentsMargins(0, 8, 0, 0)
        draft_layout.setSpacing(12)
        self.tabs.addTab(draft_page, "Draft workspace")
        layout.addWidget(self.tabs, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._team_panel(Team.BLUE))
        splitter.addWidget(self._champion_panel())
        splitter.addWidget(self._team_panel(Team.RED))
        splitter.setSizes([290, 600, 290])
        splitter.setStretchFactor(1, 1)
        draft_layout.addWidget(splitter, 1)

        analysis = QFrame()
        analysis.setObjectName("panel")
        analysis_layout = QVBoxLayout(analysis)
        analysis_layout.setContentsMargins(16, 12, 16, 12)
        notes_header = QHBoxLayout()
        notes_header.addWidget(label("DRAFT NOTES", "section"))
        notes_header.addStretch()
        review = QPushButton("Review recommendations →")
        review.clicked.connect(lambda: self.tabs.setCurrentIndex(1))
        notes_header.addWidget(review)
        analysis_layout.addLayout(notes_header)
        self.summary = label("", wrap=True)
        self.summary.setAccessibleName("Draft completeness")
        analysis_layout.addWidget(self.summary)
        self.analysis_summary = label("Insufficient data for recommendations. No performance dataset is loaded.", "muted", True)
        analysis_layout.addWidget(self.analysis_summary)
        analysis_layout.addWidget(label(
            f"Roster & portraits: Data Dragon {metadata['version']} · Bundled offline · "
            "Historical evidence in Analysis · Scope: offline simulation", "muted", True))
        draft_layout.addWidget(analysis)
        self.analysis_panel = AnalysisPanel(roster, database_path, preferences_path, self)
        self.analysis_panel.summaryChanged.connect(self.analysis_summary.setText)
        self.tabs.addTab(self.analysis_panel, "Analysis and local data")

        for shortcut, callback in (("Ctrl+Z", self._undo), ("Ctrl+R", self.reset_button.click),
                                   ("Ctrl+F", self.search.setFocus), ("Escape", self.search.clear)):
            action = QAction(self)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(callback)
            self.addAction(action)
        self._render()
        self._message(startup_message)

    def _team_panel(self, team: Team) -> QScrollArea:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setMinimumWidth(258)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 14, 12, 14)
        layout.setSpacing(10)
        layout.addWidget(label(f"{team.value.upper()} SIDE", f"{team.value}Title"))
        layout.addWidget(label("PICKS / assign a role or leave unknown", "muted", True))
        for index in range(5):
            row = QHBoxLayout()
            target = Target(team, Kind.PICK, index)
            button = SlotButton(target)
            button.setObjectName("pickSlot")
            button.setMinimumWidth(118)
            button.setIconSize(QSize(32, 32))
            button.setAccessibleName(f"{team.value.title()} pick {index + 1}")
            button.clicked.connect(lambda checked=False, t=target: self._select_target(t))
            button.dropped.connect(lambda payload, t=target: self._drop_champion(payload, t))
            self.slot_buttons[target] = button
            row.addWidget(button, 1)
            roles = RoleComboBox(team, index)
            roles.setAccessibleName(f"{team.value.title()} pick {index + 1} role")
            roles.addItem("Unknown", None)
            for role in Role:
                roles.addItem(role.value, role)
            roles.setMinimumWidth(97)
            roles.currentIndexChanged.connect(lambda _, t=team, i=index: self._pick_role_changed(t, i))
            roles.dropped.connect(lambda payload, t=team, i=index: self._drop_role(payload, t, i))
            self.role_boxes[team, index] = roles
            row.addWidget(roles)
            layout.addLayout(row)
        layout.addSpacing(10)
        layout.addWidget(label("BANS / five per side", "muted"))
        bans = QHBoxLayout()
        bans.setSpacing(4)
        for index in range(5):
            target = Target(team, Kind.BAN, index)
            button = SlotButton(target)
            button.setObjectName("banSlot")
            button.setMinimumWidth(40)
            button.setIconSize(QSize(32, 32))
            button.setAccessibleName(f"{team.value.title()} ban {index + 1}")
            button.clicked.connect(lambda checked=False, t=target: self._select_target(t))
            button.dropped.connect(lambda payload, t=target: self._drop_champion(payload, t))
            self.slot_buttons[target] = button
            bans.addWidget(button, 1)
        layout.addLayout(bans)
        layout.addWidget(label("Drag portraits to move or swap.\nDrag role labels to swap roles.", "muted", True))
        layout.addStretch()
        self.team_panels.append(panel)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(272)
        scroll.setWidget(panel)
        return scroll

    def _champion_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(320)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(2, 0, 2, 0)
        target_row = QHBoxLayout()
        self.target_label = label("", "section")
        self.target_label.setAccessibleName("Active draft slot")
        target_row.addWidget(self.target_label, 1)
        self.clear_button = QPushButton("Clear slot")
        self.clear_button.clicked.connect(lambda: self._edit(
            lambda: self.model.assign(self.target, None), "Slot cleared. Role retained."))
        target_row.addWidget(self.clear_button)
        layout.addLayout(target_row)
        self.search = QLineEdit()
        self.search.setAccessibleName("Search champions by name or alias")
        self.search.setPlaceholderText("Search champion or alias…  Ctrl+F")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._populate_grid)
        self.search.returnPressed.connect(self._assign_current)
        layout.addWidget(self.search)
        self.result_count = label("", "muted", True)
        layout.addWidget(self.result_count)
        self.grid = ChampionGrid()
        self.grid.setAccessibleName("Champion grid; select a champion to assign to the active slot")
        self.grid.setViewMode(QListView.ViewMode.IconMode)
        self.grid.setResizeMode(QListView.ResizeMode.Adjust)
        self.grid.setMovement(QListView.Movement.Static)
        self.grid.setSpacing(2)
        self.grid.setWordWrap(True)
        self.grid.setUniformItemSizes(True)
        self.grid.setIconSize(QSize(58, 58))
        self.grid.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.grid.itemClicked.connect(self._assign_item)
        self.grid.itemActivated.connect(self._assign_item)
        layout.addWidget(self.grid, 1)
        layout.addWidget(label("Click, press Enter, or drag a portrait into a slot.\n"
                               "Grayscale = picked or banned. Draft portraits stay in color.", "muted", True))
        return panel

    def _select_target(self, target: Target):
        self.target = target
        self._render()
        self.search.setFocus()
        self._message(f"Editing {target.team.value} {target.kind.value} {target.index + 1}. Choose a champion.")

    def _user_changed(self):
        if not self._rendering:
            self._edit(lambda: self.model.set_user(role=Role(self.user_role.currentData()), team=Team(self.user_team.currentData())),
                       "Your team and role were updated.")

    def _pick_role_changed(self, team: Team, index: int):
        if not self._rendering:
            value = self.role_boxes[team, index].currentData()
            self._edit(lambda: self.model.set_pick_role(team, index, Role(value) if value is not None else None),
                       "Pick role updated. Unknown roles remain unassigned.")

    def _assign_current(self):
        if self.grid.currentItem() is not None:
            self._assign_item(self.grid.currentItem())

    def _drop_champion(self, payload: dict, destination: Target):
        def apply():
            if payload.get("type") == "slot":
                source = Target(Team(payload["team"]), Kind(payload["kind"]), payload["index"])
                if self.model.state.champion_at(source) != payload.get("name"):
                    raise DraftError("That source slot changed. Drag its current portrait again.")
                return self.model.swap_champions(source, destination)
            name = self.roster.resolve(payload["name"])
            if destination.kind == Kind.PICK:
                for team in Team:
                    for index, pick in enumerate(self.model.state.picks(team)):
                        if pick.champion == name:
                            return self.model.swap_champions(Target(team, Kind.PICK, index), destination)
            return self.model.assign(destination, name)
        self._edit(apply, "Champion moved or swapped. Row roles were retained.")

    def _drop_role(self, payload: dict, team: Team, index: int):
        def apply():
            if Team(payload["team"]) != team:
                raise DraftError("Swap roles within the same side.")
            return self.model.swap_roles(team, payload["index"], index)
        self._edit(apply, "Roles swapped; champions stayed in their slots.")

    def _assign_item(self, item: QListWidgetItem):
        name = item.data(Qt.ItemDataRole.UserRole)
        self._edit(lambda: self.model.assign(self.target, name),
                   f"{name} assigned to {self.target.team.value} {self.target.kind.value} {self.target.index + 1}.")

    def _edit(self, operation, success: str):
        try:
            changed = operation()
        except (DraftError, ValueError, KeyError, TypeError) as exc:
            self._render()
            self._message(f"Cannot apply edit: {exc}", error=True)
            return
        self._render()
        if changed:
            self._persist()
        self._message(success if changed else "No change to the draft.")

    def _undo(self):
        self._edit(self.model.undo, "Last draft edit undone.")

    def _render(self):
        self._rendering = True
        state = self.model.state
        try:
            self.user_team.setCurrentIndex(self.user_team.findData(state.user_team))
            self.user_role.setCurrentIndex(self.user_role.findData(state.user_role))
            for target, button in self.slot_buttons.items():
                name = state.champion_at(target)
                button.champion = name
                icon = self.portraits.icon(name)
                button.setIcon(icon)
                if target.kind == Kind.PICK:
                    text = f"{target.index + 1}  {name or 'Choose champion'}"
                    if name and len(name) > 12:
                        text = f"{target.index + 1}\n{name}"
                    button.setText(text.replace("&", "&&"))
                else:
                    short = name if name and len(name) <= 8 else (name[:6] + "…" if name else "—")
                    button.setText("" if not icon.isNull() else f"{target.index + 1}\n{short}")
                button.setToolTip(f"{target.team.value.title()} {target.kind.value} {target.index + 1}: {name or 'empty'}")
                button.setProperty("active", target == self.target)
                button.style().unpolish(button)
                button.style().polish(button)
            for (team, index), box in self.role_boxes.items():
                box.setCurrentIndex(box.findData(state.picks(team)[index].role))
            for panel in self.team_panels:
                panel.setMinimumHeight(panel.layout().sizeHint().height())
            self.target_label.setText(f"{self.target.team.value.title()} {self.target.kind.value} {self.target.index + 1}")
            self.clear_button.setEnabled(state.champion_at(self.target) is not None)
            self.undo_button.setEnabled(self.model.can_undo)
            picks = sum(p.champion is not None for t in Team for p in state.picks(t))
            bans = sum(b is not None for t in Team for b in state.bans(t))
            enemies = Team.RED if state.user_team == Team.BLUE else Team.BLUE
            unknown = sum(p.champion is not None and p.role is None for p in state.picks(enemies))
            self.summary.setText(f"{picks}/10 picks · {bans}/10 bans · Playing {state.user_role.value} on "
                                 f"{state.user_team.value.title()} · {unknown} selected enemy roles unknown")
            self._populate_grid()
            if self.analysis_panel.draft != state:
                self.analysis_panel.set_draft(state)
        finally:
            self._rendering = False

    def _populate_grid(self):
        previous = self.grid.currentItem()
        previous_name = previous.data(Qt.ItemDataRole.UserRole) if previous else None
        self.grid.clear()
        state = self.model.state
        picked = {p.champion for t in Team for p in state.picks(t) if p.champion}
        banned = {b for t in Team for b in state.bans(t) if b}
        names = self.roster.search(self.search.text())
        active = state.champion_at(self.target)
        for name in names:
            status = "SELECTED" if name == active else "PICKED" if name in picked else "BANNED" if name in banned else "CHAMPION"
            item = QListWidgetItem(f"{name}\n{status}")
            item.setIcon(self.portraits.icon(name, grayscale=name in picked or name in banned))
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setData(Qt.ItemDataRole.AccessibleTextRole, f"{name}, {status.lower()}")
            item.setSizeHint(QSize(104, 112))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setToolTip(f"{name} · {status.lower()}\nAssign to {self.target.team.value} {self.target.kind.value} {self.target.index + 1}")
            if status in {"PICKED", "BANNED"}:
                item.setForeground(QColor("#a3b0c3"))
            self.grid.addItem(item)
            if name == previous_name:
                self.grid.setCurrentItem(item)
        if self.grid.currentItem() is None and self.grid.count():
            self.grid.setCurrentRow(0)
        self.result_count.setText(f"{len(names)} / {len(self.roster.names)} champions · Enter assigns highlighted match"
                                  if names else "No matching champions. Try a canonical name or alias.")

    def _persist(self):
        if not self.remember.isChecked():
            return
        try:
            save_session(self.state_path, self.model.state, self.roster)
            self.persistence_error = ""
        except OSError as exc:
            self.persistence_error = f"Draft is in memory; saving failed: {exc}"

    def _toggle_remember(self, enabled: bool):
        if enabled:
            self._persist()
            self._message("Draft recovery enabled. Changes save locally after every edit.")
        else:
            try:
                self.state_path.unlink(missing_ok=True)
                self.persistence_error = ""
                self._message("Draft recovery disabled; saved copy removed.")
            except OSError as exc:
                self.remember.blockSignals(True)
                self.remember.setChecked(True)
                self.remember.blockSignals(False)
                self.persistence_error = f"Could not remove saved draft: {exc}"
                self._message("", error=True)

    def _message(self, message: str, *, error: bool = False):
        text = self.persistence_error or message
        self.statusBar().setStyleSheet("color: #ffb8aa;" if error or self.persistence_error else "color: #b9cee2;")
        self.statusBar().showMessage(text)

    def closeEvent(self, event):
        self.analysis_panel.shutdown()
        super().closeEvent(event)
