"""Exact-grain reads. A snapshot is immutable input to the scoring worker."""

from contextlib import closing
from dataclasses import dataclass, field
import json
from pathlib import Path

from .database import connect


@dataclass(frozen=True)
class Filters:
    dataset_id: str
    patch: str
    rank: str
    region: str


@dataclass(frozen=True)
class Counts:
    wins: int
    games: int


@dataclass
class Snapshot:
    metadata: dict = field(default_factory=dict)
    baselines: dict[tuple[str, str], Counts] = field(default_factory=dict)
    matchups: dict[tuple[str, str, str, str], Counts] = field(default_factory=dict)
    synergies: dict[tuple[str, str, str, str], Counts] = field(default_factory=dict)
    roles: dict[str, set[str]] = field(default_factory=dict)
    attributes: dict[str, dict] = field(default_factory=dict)
    classes: dict[str, str] = field(default_factory=dict)


class Repository:
    def __init__(self, path: Path):
        self.path = path

    def datasets(self) -> list[dict]:
        with closing(connect(self.path)) as db:
            return [dict(row) for row in db.execute("SELECT * FROM dataset_metadata ORDER BY is_demo,patch DESC,id")]

    def filter_options(self, dataset_id: str) -> list[tuple[str, str, str]]:
        with closing(connect(self.path)) as db:
            return [tuple(row) for row in db.execute(
                "SELECT DISTINCT patch,rank,region FROM champion_stats WHERE dataset_id=? ORDER BY patch,rank,region", (dataset_id,))]

    def load(self, filters: Filters) -> Snapshot:
        snapshot = Snapshot()
        values = (filters.dataset_id, filters.patch, filters.rank, filters.region)
        where = "dataset_id=? AND patch=? AND rank=? AND region=?"
        with closing(connect(self.path)) as db:
            row = db.execute("SELECT * FROM dataset_metadata WHERE id=?", (filters.dataset_id,)).fetchone()
            snapshot.metadata = dict(row) if row else {}
            for row in db.execute(f"SELECT * FROM champion_stats WHERE {where}", values):
                snapshot.baselines[row["name"], row["role"]] = Counts(row["wins"], row["games"])
            for table, counterpart, role, destination in (
                ("matchup_stats", "opponent", "opponent_role", snapshot.matchups),
                ("synergy_stats", "ally", "ally_role", snapshot.synergies),
            ):
                for row in db.execute(f"SELECT * FROM {table} WHERE {where}", values):
                    destination[row["name"], row["role"], row[counterpart], row[role]] = Counts(row["wins"], row["games"])
            for row in db.execute("SELECT name,role FROM champion_roles WHERE dataset_id=?", (filters.dataset_id,)):
                snapshot.roles.setdefault(row["name"], set()).add(row["role"])
            for row in db.execute("SELECT name,class,attributes FROM champions"):
                snapshot.attributes[row["name"]] = json.loads(row["attributes"])
                snapshot.classes[row["name"]] = row["class"]
            for row in db.execute("SELECT name,class,attributes FROM dataset_champions WHERE dataset_id=?", (filters.dataset_id,)):
                snapshot.attributes[row["name"]] = json.loads(row["attributes"])
                snapshot.classes[row["name"]] = row["class"]
        return snapshot
