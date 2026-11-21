"""Local Android-to-Python adapter. Shared domain, storage and scoring are reused.

Every call is serialized on the Android app's single background executor. This
module imports no Android/Qt APIs and can be tested against the desktop core.
"""

from collections import OrderedDict
from contextlib import closing
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
import time

from league_draft.domain.draft import DraftModel, Kind, Role, Target, Team
from league_draft.domain.roster import load_roster, normalize
from league_draft.recommendation.engine import Settings, composition_gaps, recommend
from league_draft.storage.bootstrap import prepare_database
from league_draft.storage.database import connect
from league_draft.storage.importer import import_bundle, load_bundle
from league_draft.storage.preferences import load_preferences, save_preferences
from league_draft.storage.repository import Filters, Repository
from league_draft.storage.session import load_session, save_session

LABELS = {"lane": "Lane matchup", "other_enemy": "Other enemies", "synergy": "Ally synergy",
          "composition": "Composition heuristic", "baseline": "Baseline", "robustness": "Blind robustness"}


def details(candidate) -> str:
    lines = [candidate.name, "Comparative score: " + (f"{candidate.score:.1f}/100" if candidate.score is not None else "insufficient evidence"),
             f"Coverage: {candidate.coverage:.0%}"]
    if candidate.baseline:
        lines.append(f"Baseline: {candidate.baseline.wins} wins / {candidate.baseline.games} appearances")
    lines.extend(["", "COMPONENTS / score and renormalized weight"])
    for key, title in LABELS.items():
        if key in candidate.components:
            lines.append(f"{title}: {candidate.components[key]:.1f}; {candidate.effective_weights.get(key, 0):.0%}")
        else:
            lines.append(f"{title}: unavailable / not applicable")
    lines.extend(["", "PAIR EVIDENCE / samples overlap; do not sum them"])
    for item in candidate.evidence:
        lines.append(f"{LABELS[item.kind]}: {item.counterpart} ({item.role}, role weight {item.role_weight:.0%})\n"
                     f"  {item.wins}/{item.games}; smoothed {item.smoothed:.1%}; expected {item.expected:.1%}; residual {item.effect * 100:+.2f} pp")
    if not candidate.evidence:
        lines.append("No supported pairs in this draft and filter.")
    lines.extend(["", "LIMITATIONS", *candidate.warnings])
    return "\n".join(lines)


class MobileSession:
    def __init__(self, directory: str, seed_path: str):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.roster, self.roster_metadata = load_roster()
        self.state_path = self.directory / "draft-state.json"
        self.preferences_path = self.directory / "preferences.json"
        self.database_path = self.directory / "draft-data.sqlite3"
        self.notice = prepare_database(self.database_path, self.roster, seed_path=Path(seed_path))
        self.repository = Repository(self.database_path)
        self.preferences = load_preferences(self.preferences_path)
        self.remember = self.preferences.get("remember", True) is True
        try:
            self.settings = Settings(**self.preferences.get("settings", {}))
        except (ValueError, TypeError):
            self.settings = Settings()
        self.model = DraftModel(self.roster)
        if self.remember and self.state_path.exists():
            try:
                self.model = DraftModel(self.roster, load_session(self.state_path, self.roster))
            except (OSError, ValueError) as exc:
                backup = self.state_path.with_name(f"draft-state.json.corrupt-{time.time_ns()}")
                self.state_path.replace(backup)
                self.notice = f"Saved draft could not be recovered; kept {backup.name}. {exc}"
        self.cache = OrderedDict()
        self.datasets = []
        self.filters = None
        self._select_dataset(self.preferences.get("dataset_id"),
                             self.preferences.get("rank", "PRO"), self.preferences.get("region", "GLOBAL"))

    def _select_dataset(self, dataset_id, rank="PRO", region="GLOBAL"):
        self.datasets = self.repository.datasets()
        def order(row):
            try:
                return row["is_demo"], tuple(-int(p) for p in row["patch"].split("."))
            except ValueError:
                return row["is_demo"], (0,)
        self.datasets.sort(key=order)
        selected = next((d for d in self.datasets if d["id"] == dataset_id), None)
        selected = selected or next((d for d in self.datasets if d["patch"] == "16.20" and not d["is_demo"]), None)
        selected = selected or (self.datasets[0] if self.datasets else None)
        if selected is None:
            self.filters = None
            return
        options = self.repository.filter_options(selected["id"])
        if not options:
            self.filters = None
            return
        ranks = sorted({o[1] for o in options})
        rank = rank if rank in ranks else ranks[0]
        regions = sorted({o[2] for o in options if o[1] == rank}, key=lambda r: (r != "GLOBAL", r))
        region = region if region in regions else regions[0]
        self.filters = Filters(selected["id"], selected["patch"], rank, region)

    def _save_preferences(self):
        self.preferences.update(remember=self.remember, settings=asdict(self.settings))
        if self.filters:
            self.preferences.update(dataset_id=self.filters.dataset_id, rank=self.filters.rank, region=self.filters.region)
        save_preferences(self.preferences_path, self.preferences)

    def view(self) -> dict:
        options = self.repository.filter_options(self.filters.dataset_id) if self.filters else []
        metadata = next((d for d in self.datasets if self.filters and d["id"] == self.filters.dataset_id), {})
        return {"ok": True, "state": asdict(self.model.state), "can_undo": self.model.can_undo,
                "remember": self.remember, "notice": self.notice, "settings": asdict(self.settings),
                "filters": asdict(self.filters) if self.filters else None,
                "datasets": self.datasets, "metadata": metadata,
                "ranks": sorted({o[1] for o in options}),
                "regions": sorted({o[2] for o in options if self.filters and o[1] == self.filters.rank}, key=lambda r: (r != "GLOBAL", r)),
                "champions": [{"name": name, "file": f"icons/{normalize(name)}.png"} for name in self.roster.names],
                "roles": [r.value for r in Role]}

    @staticmethod
    def _target(value):
        return Target(Team(value["team"]), Kind(value["kind"]), value["index"])

    def dispatch(self, action: str, arguments: dict) -> dict:
        self.notice = ""
        try:
            changed = False
            if action == "assign":
                changed = self.model.assign(self._target(arguments), arguments.get("champion"))
            elif action == "swap":
                changed = self.model.swap_champions(self._target(arguments["source"]), self._target(arguments["destination"]))
            elif action == "swap_roles":
                if arguments["source_team"] != arguments["team"]:
                    raise ValueError("Swap roles within the same side.")
                changed = self.model.swap_roles(Team(arguments["team"]), arguments["source"], arguments["destination"])
            elif action == "set_role":
                team, index = Team(arguments["team"]), arguments["index"]
                role = Role(arguments["role"]) if arguments.get("role") is not None else None
                existing = next((i for i, pick in enumerate(self.model.state.picks(team)) if role is not None and pick.role == role and i != index), None)
                changed = self.model.swap_roles(team, index, existing) if existing is not None else self.model.set_pick_role(team, index, role)
            elif action == "set_user":
                changed = self.model.set_user(role=Role(arguments.get("role", self.model.state.user_role)), team=Team(arguments.get("team", self.model.state.user_team)))
            elif action == "undo":
                changed = self.model.undo()
            elif action == "reset":
                changed = self.model.reset()
            elif action == "remember":
                if type(arguments.get("enabled")) is not bool:
                    raise ValueError("Save-draft setting must be true or false.")
                if not arguments["enabled"]:
                    self.state_path.unlink(missing_ok=True)
                self.remember = arguments["enabled"]
                changed = self.remember
            elif action == "set_settings":
                self.settings = Settings(**arguments)
            elif action == "set_filters":
                dataset_id = arguments.get("dataset_id")
                if dataset_id not in {d["id"] for d in self.datasets}:
                    raise ValueError("Dataset is unavailable.")
                self._select_dataset(dataset_id, arguments.get("rank", "PRO"), arguments.get("region", "GLOBAL"))
            elif action == "import_json":
                path = Path(arguments["path"]).resolve()
                if not path.is_relative_to(self.directory):
                    raise ValueError("Import must come from the app's local file picker cache.")
                with closing(connect(self.database_path)) as connection:
                    dataset_id, imported = import_bundle(connection, load_bundle(path), self.roster)
                self.cache.clear()
                self._select_dataset(dataset_id)
                self.notice = "Dataset imported." if imported else "Already imported; counts were unchanged."
            elif action == "export":
                return {"ok": True, "json": json.dumps({"schema_version": 1, **asdict(self.model.state)}, ensure_ascii=False, indent=2)}
            elif action != "view":
                raise ValueError("Unrecognized draft command.")
            self._save_preferences()
            if changed and self.remember:
                save_session(self.state_path, self.model.state, self.roster)
            return self.view()
        except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as exc:
            result = self.view()
            result.update(ok=False, error=str(exc))
            return result

    def analyze(self) -> dict:
        started = time.perf_counter()
        if self.filters is None:
            return {"ok": True, "results": [], "gaps": [], "elapsed_ms": 0, "message": "Insufficient data. Import a licensed local dataset."}
        snapshot = self.cache.get(self.filters)
        if snapshot is None:
            snapshot = self.repository.load(self.filters)
            self.cache[self.filters] = snapshot
            if len(self.cache) > 2:
                self.cache.popitem(last=False)
        else:
            self.cache.move_to_end(self.filters)
        candidates = recommend(self.model.state, snapshot, self.settings)
        output = []
        for candidate in candidates:
            row = asdict(candidate)
            row["details"] = details(candidate)
            row["file"] = f"icons/{normalize(candidate.name)}.png"
            output.append(row)
        return {"ok": True, "results": output, "gaps": composition_gaps(self.model.state, snapshot),
                "metadata": snapshot.metadata, "filters": asdict(self.filters),
                "elapsed_ms": (time.perf_counter() - started) * 1000,
                "message": "Comparative scores, not win probabilities. Professional historical results are not solo-queue statistics."}


_session = None


def initialize(directory: str, seed_path: str) -> str:
    global _session
    _session = MobileSession(directory, seed_path)
    return json.dumps(_session.view(), ensure_ascii=False)


def dispatch(action: str, arguments_json: str = "{}") -> str:
    if _session is None:
        raise RuntimeError("Local data is still initializing.")
    return json.dumps(_session.dispatch(action, json.loads(arguments_json)), ensure_ascii=False)


def analyze() -> str:
    if _session is None:
        raise RuntimeError("Local data is still initializing.")
    return json.dumps(_session.analyze(), ensure_ascii=False)
