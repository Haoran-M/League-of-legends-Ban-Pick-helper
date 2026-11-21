"""Offline analysis UI with debounced background work and stale-result rejection."""

from contextlib import closing
from dataclasses import asdict
from importlib.resources import files
from pathlib import Path
import time

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPlainTextEdit, QPushButton, QSpinBox, QSplitter, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from league_draft.recommendation.engine import Candidate, DEFAULT_WEIGHTS, Settings, composition_gaps, recommend
from league_draft.storage.database import connect
from league_draft.storage.importer import import_bundle, load_bundle
from league_draft.storage.preferences import load_preferences, save_preferences
from league_draft.storage.repository import Filters, Repository

COMPONENT_LABELS = {"lane": "Lane matchup", "other_enemy": "Other enemies", "synergy": "Ally synergy",
                    "composition": "Composition heuristic", "baseline": "Baseline", "robustness": "Blind robustness"}


class TaskSignals(QObject):
    completed = Signal(int, object)
    failed = Signal(int, str)


class Task(QRunnable):
    def __init__(self, token: int, operation):
        super().__init__()
        self.token, self.operation = token, operation
        self.signals = TaskSignals()

    def run(self):
        try:
            self.signals.completed.emit(self.token, self.operation())
        except Exception as exc:
            import logging
            logging.exception("Background task failed")
            self.signals.failed.emit(self.token, str(exc))


def describe(candidate: Candidate) -> str:
    lines = [candidate.name, "Comparative score: " + (f"{candidate.score:.1f}/100" if candidate.score is not None else "insufficient data"),
             f"Evidence coverage: {candidate.coverage:.0%}"]
    if candidate.baseline:
        lines.append(f"Baseline observations: {candidate.baseline.wins} wins / {candidate.baseline.games} appearances")
    lines += ["", "COMPONENTS / score; renormalized weight"]
    for component, title in COMPONENT_LABELS.items():
        if component in candidate.components:
            lines.append(f"{title}: {candidate.components[component]:.1f}; {candidate.effective_weights.get(component, 0):.0%}")
        else:
            lines.append(f"{title}: unavailable / not applicable")
    lines += ["", "PAIR EVIDENCE / overlapping observations; do not sum samples"]
    for evidence in candidate.evidence:
        lines.append(f"{COMPONENT_LABELS[evidence.kind]} · {evidence.counterpart} ({evidence.role}, role weight {evidence.role_weight:.0%}): "
                     f"{evidence.wins}/{evidence.games}, smoothed {evidence.smoothed:.1%}, expected {evidence.expected:.1%}, "
                     f"residual {evidence.effect * 100:+.2f} pp")
    if not candidate.evidence:
        lines.append("No supported pair evidence for the selected draft.")
    lines += ["", "LIMITATIONS", *candidate.warnings]
    return "\n".join(lines)


class AnalysisPanel(QWidget):
    summaryChanged = Signal(str)

    def __init__(self, roster, database_path: Path | None, preferences_path: Path | None, parent=None):
        super().__init__(parent)
        self.roster = roster
        self.repository = Repository(database_path) if database_path else None
        self.preferences_path = preferences_path
        self.preferences = load_preferences(preferences_path) if preferences_path else {}
        try:
            self.settings = Settings(**self.preferences.get("settings", {}))
        except (TypeError, ValueError):
            self.settings = Settings()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(120)
        self.timer.timeout.connect(self._start_analysis)
        self.token = 0
        self.draft = None
        self.latest_results: list[Candidate] = []
        self.last_elapsed_ms = None
        self.snapshot_cache = {}
        self._populating = False
        self._tasks = set()
        self._closing = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 10, 4, 0)
        filters = QHBoxLayout()
        self.dataset = QComboBox()
        self.dataset.setAccessibleName("Historical patch and dataset")
        filters.addWidget(QLabel("Patch / dataset"))
        filters.addWidget(self.dataset, 2)
        self.rank = QComboBox()
        self.rank.setAccessibleName("Dataset rank or competition level")
        filters.addWidget(QLabel("Rank / level"))
        filters.addWidget(self.rank)
        self.region = QComboBox()
        self.region.setAccessibleName("Dataset region or professional league")
        filters.addWidget(QLabel("Region / league"))
        filters.addWidget(self.region, 1)
        self.settings_button = QPushButton("Scoring settings")
        self.settings_button.clicked.connect(self._show_settings)
        filters.addWidget(self.settings_button)
        self.import_button = QPushButton("Import local data")
        self.import_button.clicked.connect(self._choose_import)
        self.import_button.setEnabled(self.repository is not None)
        filters.addWidget(self.import_button)
        layout.addLayout(filters)
        self.source_label = QLabel("No performance dataset is loaded. Import a licensed local dataset to compare candidates.")
        self.source_label.setTextFormat(Qt.TextFormat.PlainText)
        self.source_label.setWordWrap(True)
        self.source_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.source_label)
        self.status = QLabel("Insufficient data for recommendations.")
        self.status.setWordWrap(True)
        self.status.setAccessibleName("Analysis status and limitations")
        layout.addWidget(self.status)
        split = QSplitter(Qt.Orientation.Horizontal)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Candidate", "Score /100", "Coverage", "Base n"])
        self.table.setAccessibleName("Eligible candidate comparisons; scores are not win probabilities")
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().hide()
        self.table.itemSelectionChanged.connect(self._show_candidate)
        split.addWidget(self.table)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setAccessibleName("Candidate evidence and score explanation")
        self.details.setPlainText("Select a candidate to inspect the components, observed counts and limitations.")
        split.addWidget(self.details)
        split.setSizes([430, 660])
        layout.addWidget(split, 1)
        footer = QHBoxLayout()
        self.compare_button = QPushButton("Compare selected (up to 3)")
        self.compare_button.clicked.connect(self._compare)
        footer.addWidget(self.compare_button)
        sources = QPushButton("Sources and method")
        sources.clicked.connect(self._show_sources)
        footer.addWidget(sources)
        footer.addStretch()
        notice = QLabel("Historical observations · Class-based composition heuristics · No score is a win probability")
        notice.setWordWrap(True)
        footer.addWidget(notice)
        layout.addLayout(footer)
        self.dataset.currentIndexChanged.connect(self._dataset_changed)
        self.rank.currentIndexChanged.connect(self._rank_changed)
        self.region.currentIndexChanged.connect(self._filters_changed)
        self.refresh_datasets()

    def refresh_datasets(self, preferred_id: str | None = None):
        self._populating = True
        self.dataset.clear()
        self.datasets = self.repository.datasets() if self.repository else []
        def order(row):
            try:
                patch = tuple(-int(p) for p in row["patch"].split("."))
            except ValueError:
                patch = (0,)
            return row["is_demo"], patch, row["id"]
        self.datasets.sort(key=order)
        for row in self.datasets:
            title = f"DEMO · {row['patch']}" if row["is_demo"] else f"{row['patch']} · historical"
            self.dataset.addItem(title, row["id"])
        selected = preferred_id or self.preferences.get("dataset_id")
        index = self.dataset.findData(selected)
        if index < 0:
            index = next((i for i, row in enumerate(self.datasets) if row["patch"] == "16.20" and not row["is_demo"]), 0)
        if self.dataset.count():
            self.dataset.setCurrentIndex(index)
        self._populating = False
        self._dataset_changed()

    def _dataset_changed(self):
        if self._populating:
            return
        self._populating = True
        self.rank.clear()
        self.options = self.repository.filter_options(self.dataset.currentData()) if self.repository and self.dataset.currentData() else []
        for rank in sorted({option[1] for option in self.options}):
            self.rank.addItem(rank)
        preferred = self.rank.findText(self.preferences.get("rank", "PRO"))
        if preferred >= 0:
            self.rank.setCurrentIndex(preferred)
        self._populating = False
        self._rank_changed()

    def _rank_changed(self):
        if self._populating:
            return
        self._populating = True
        self.region.clear()
        for region in sorted({o[2] for o in self.options if o[1] == self.rank.currentText()}, key=lambda x: (x != "GLOBAL", x)):
            self.region.addItem(region)
        preferred = self.region.findText(self.preferences.get("region", "GLOBAL"))
        if preferred >= 0:
            self.region.setCurrentIndex(preferred)
        self._populating = False
        self._filters_changed()

    def current_filters(self) -> Filters | None:
        index = self.dataset.currentIndex()
        if index < 0 or index >= len(self.datasets) or not self.region.currentText():
            return None
        row = self.datasets[index]
        return Filters(row["id"], row["patch"], self.rank.currentText(), self.region.currentText())

    def _save(self):
        if self.preferences_path:
            self.preferences.update(dataset_id=self.dataset.currentData(), rank=self.rank.currentText(), region=self.region.currentText(), settings=asdict(self.settings))
            try:
                save_preferences(self.preferences_path, self.preferences)
            except OSError as exc:
                self.status.setText(f"Preferences could not be saved: {exc}")

    def _filters_changed(self):
        if self._populating:
            return
        self._save()
        self.schedule()

    def set_draft(self, draft):
        self.draft = draft
        self.schedule()

    def schedule(self):
        self.token += 1
        if self.repository and self.current_filters() and self.draft is not None:
            self.status.setText("Calculating from the selected local dataset…")
            self.timer.start()
        else:
            self.latest_results = []
            self.table.setRowCount(0)
            self.summaryChanged.emit("Insufficient data for recommendations. No statistical evidence is loaded.")

    def _submit(self, token, operation, completed):
        task = Task(token, operation)
        self._tasks.add(task)
        def done(t, result):
            self._tasks.discard(task)
            if self._closing:
                return
            completed(t, result)
        def failed(t, message):
            self._tasks.discard(task)
            if self._closing:
                return
            if t == self.token:
                self.status.setText(f"Analysis failed: {message}. See the local log.")
                self.summaryChanged.emit("Analysis is unavailable; your draft remains editable.")
            self.import_button.setEnabled(self.repository is not None)
        task.signals.completed.connect(done)
        task.signals.failed.connect(failed)
        self.pool.start(task)

    def _start_analysis(self):
        filters, draft, settings, token = self.current_filters(), self.draft, self.settings, self.token
        if not filters or draft is None:
            return
        def calculate():
            started = time.perf_counter()
            snapshot = self.snapshot_cache.get(filters)
            if snapshot is None:
                snapshot = self.repository.load(filters)
                self.snapshot_cache[filters] = snapshot
            return recommend(draft, snapshot, settings), snapshot.metadata, composition_gaps(draft, snapshot), (time.perf_counter() - started) * 1000
        self._submit(token, calculate, self._apply_results)

    def _apply_results(self, token, payload):
        if token != self.token:
            return
        results, metadata, gaps, elapsed = payload
        self.latest_results = results
        self.last_elapsed_ms = elapsed
        prefix = "DEMO / SYNTHETIC — NOT HISTORICAL" if metadata.get("is_demo") else "HISTORICAL PROFESSIONAL PLAY — not solo-queue statistics"
        self.source_label.setText(f"{prefix}\n{metadata.get('source', '')} · {metadata.get('license', '')} · "
                                  f"Local import: {metadata.get('imported_at', '')[:10]}\n{metadata.get('notes', '')}")
        scored = [r for r in results if r.score is not None]
        self.status.setText((f"{len(scored)} supported candidates / {len(results)} eligible for your role. " if scored else "Insufficient statistical evidence under the selected filters and minimum support. ")
                            + " · ".join(gaps))
        previous = self.table.item(self.table.currentRow(), 0)
        previous_name = previous.text() if previous else None
        self.table.blockSignals(True)
        self.table.setRowCount(len(results))
        selected = 0
        for index, result in enumerate(results):
            values = (result.name, f"{result.score:.1f}" if result.score is not None else "—", f"{result.coverage:.0%}", str(result.baseline.games) if result.baseline else "—")
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                if column == 0:
                    from .portraits import Portraits
                    if not hasattr(self, "portraits"):
                        self.portraits = Portraits()
                    item.setIcon(self.portraits.icon(result.name))
                self.table.setItem(index, column, item)
            if result.name == previous_name:
                selected = index
        self.table.blockSignals(False)
        if results:
            self.table.selectRow(selected)
            self._show_candidate()
        else:
            self.details.setPlainText("No eligible champions are available in this dataset for the selected role and draft.")
        if scored:
            self.summaryChanged.emit("Top comparisons: " + " · ".join(f"{r.name} {r.score:.1f}" for r in scored[:4]) + " — comparative scores, not win probabilities.")
        else:
            self.summaryChanged.emit("Insufficient statistical evidence at these filters. Open Analysis to inspect coverage or change the historical patch.")

    def _show_candidate(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.latest_results):
            self.details.setPlainText(describe(self.latest_results[row]))

    def _compare(self):
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})[:3]
        if not rows:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Candidate comparison — not win probabilities")
        dialog.resize(900, 700)
        layout = QVBoxLayout(dialog)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText("\n\n" + ("\n\n" + "─" * 60 + "\n\n").join(describe(self.latest_results[row]) for row in rows))
        layout.addWidget(text)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def _show_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Scoring settings")
        form = QFormLayout(dialog)
        spins = {}
        for key in DEFAULT_WEIGHTS:
            box = QDoubleSpinBox()
            box.setRange(0, 1000)
            box.setValue(self.settings.weights[key])
            form.addRow(COMPONENT_LABELS[key], box)
            spins[key] = box
        alpha = QDoubleSpinBox()
        alpha.setRange(1, 10000)
        alpha.setValue(self.settings.alpha)
        form.addRow("Smoothing prior strength", alpha)
        minimum = QSpinBox()
        minimum.setRange(1, 100000)
        minimum.setValue(self.settings.minimum_games)
        form.addRow("Minimum observations per statistic", minimum)
        note = QLabel("Missing components are dropped. Unknown roles shift lane weight toward robustness. All-zero weights produce no scores.")
        note.setWordWrap(True)
        form.addRow(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings = Settings({key: spin.value() for key, spin in spins.items()}, alpha.value(), minimum.value())
            self._save()
            self.schedule()

    def _show_sources(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Sources, scoring and notices")
        dialog.resize(900, 700)
        layout = QVBoxLayout(dialog)
        tabs = QTabWidget()
        for title, filename in (("Data sources", "DATA_SOURCES.md"), ("Scoring method", "SCORING.md"), ("Licenses & notices", "THIRD_PARTY_NOTICES.md")):
            text = QPlainTextEdit()
            text.setReadOnly(True)
            try:
                text.setPlainText(files("league_draft").joinpath("resources", filename).read_text(encoding="utf-8"))
            except OSError:
                text.setPlainText("The bundled document is unavailable. See the source README.")
            tabs.addTab(text, title)
        layout.addWidget(tabs)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def _choose_import(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Import a local licensed dataset", "", "Dataset JSON or CSV (*.json *.csv)")
        if filename:
            self.import_path(Path(filename))

    def import_path(self, path: Path):
        if not self.repository:
            return
        self.token += 1
        token = self.token
        self.timer.stop()
        self.import_button.setEnabled(False)
        self.status.setText("Validating and importing the local dataset…")
        def perform():
            bundle = load_bundle(path)
            with closing(connect(self.repository.path)) as db:
                return import_bundle(db, bundle, self.roster)
        def completed(_, payload):
            dataset_id, changed = payload
            self.import_button.setEnabled(True)
            self.snapshot_cache.clear()
            self.refresh_datasets(dataset_id)
            self.status.setText("Dataset imported." if changed else "This exact snapshot was already imported; counts were unchanged.")
        self._submit(token, perform, completed)

    def shutdown(self):
        self._closing = True
        self.timer.stop()
        self.token += 1
        self.pool.clear()
        self.pool.waitForDone(15000)
