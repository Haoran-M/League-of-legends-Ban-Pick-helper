"""Strict local CSV/JSON bundle validation and idempotent transactional import."""

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from league_draft.domain.draft import Role
from league_draft.domain.roster import Roster

TABLE_COLUMNS = {
    "champions": ("name", "class", "damage_profile", "attributes"),
    "champion_roles": ("name", "role"),
    "champion_stats": ("name", "role", "patch", "rank", "region", "wins", "games"),
    "matchup_stats": ("name", "opponent", "role", "opponent_role", "patch", "rank", "region", "wins", "games"),
    "synergy_stats": ("name", "ally", "role", "ally_role", "patch", "rank", "region", "wins", "games"),
}


class ImportError(ValueError):
    pass


def load_bundle(path: Path) -> dict:
    if path.is_dir() or path.suffix.lower() == ".csv":
        directory = path if path.is_dir() else path.parent
        metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8-sig"))
        bundle = {"metadata": metadata}
        for table in TABLE_COLUMNS:
            csv_path = directory / f"{table}.csv"
            if csv_path.exists():
                with csv_path.open(encoding="utf-8-sig", newline="") as stream:
                    reader = csv.DictReader(stream)
                    if reader.fieldnames != list(TABLE_COLUMNS[table]):
                        raise ImportError(f"{table}.csv: expected columns {TABLE_COLUMNS[table]}")
                    bundle[table] = list(reader)
        return bundle
    if path.suffix.lower() != ".json":
        raise ImportError("Choose a JSON bundle or a CSV directory with metadata.json.")
    if path.stat().st_size > 150_000_000:
        raise ImportError("Dataset bundle exceeds 150 MB.")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _text(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 10_000:
        raise ImportError(f"{field}: nonempty text is required.")
    return value.strip()


def _count(value, field: str) -> int:
    if type(value) is int:
        result = value
    elif isinstance(value, str) and value.isdecimal():
        result = int(value)
    else:
        raise ImportError(f"{field}: integer required.")
    if not 0 <= result <= 2_000_000_000:
        raise ImportError(f"{field}: count is outside the supported range.")
    return result


def validate_bundle(bundle: dict, roster: Roster) -> tuple[dict, dict[str, list[dict]]]:
    if not isinstance(bundle, dict) or set(bundle) - ({"metadata"} | set(TABLE_COLUMNS)):
        raise ImportError("Unexpected bundle fields.")
    raw = bundle.get("metadata")
    if not isinstance(raw, dict):
        raise ImportError("Dataset metadata is required.")
    if set(raw) - {"source", "license", "patch", "is_demo", "notes"}:
        raise ImportError("Unexpected metadata fields.")
    metadata = {key: _text(raw.get(key), key) for key in ("source", "license", "patch")}
    if type(raw.get("is_demo")) is not bool:
        raise ImportError("is_demo must explicitly be true or false.")
    metadata["is_demo"] = raw["is_demo"]
    metadata["notes"] = raw.get("notes", "")
    if not isinstance(metadata["notes"], str):
        raise ImportError("Metadata notes must be text.")
    if not metadata["is_demo"] and not metadata["source"].startswith(("https://", "http://")):
        raise ImportError("A historical dataset requires a source URL and license.")
    rows = {}
    for table, columns in TABLE_COLUMNS.items():
        source_rows = bundle.get(table, [])
        if not isinstance(source_rows, list):
            raise ImportError(f"{table}: rows must be a list.")
        normalized, seen = [], set()
        for index, row in enumerate(source_rows, 1):
            try:
                if not isinstance(row, dict) or set(row) != set(columns):
                    raise ImportError(f"Expected fields: {columns}")
                item = {}
                for field in columns:
                    value = row[field]
                    if field in {"name", "opponent", "ally"}:
                        item[field] = roster.resolve(_text(value, field))
                    elif field in {"role", "opponent_role", "ally_role"}:
                        item[field] = Role(_text(value, field)).value
                    elif field in {"wins", "games"}:
                        item[field] = _count(value, field)
                    elif field == "attributes":
                        attrs = json.loads(value) if isinstance(value, str) else value
                        if not isinstance(attrs, dict) or set(attrs) - {"frontline", "engage", "utility", "physical", "magic"}:
                            raise ImportError("Unrecognized composition attributes.")
                        if any(type(v) not in (int, float) or not 0 <= v <= 1 for v in attrs.values()):
                            raise ImportError("Composition attributes must be finite numbers from 0 to 1.")
                        item[field] = json.dumps(attrs, sort_keys=True)
                    else:
                        item[field] = _text(value, field)
                if "wins" in item and not 0 <= item["wins"] <= item["games"] or item.get("games") == 0:
                    raise ImportError("Require 0 <= wins <= games and games > 0.")
                if "patch" in item and item["patch"] != metadata["patch"]:
                    raise ImportError("Row patch does not match metadata patch.")
                if item.get("opponent") == item["name"] or item.get("ally") == item["name"]:
                    raise ImportError("A champion cannot be its own opponent or ally.")
                if table == "synergy_stats" and item["role"] == item["ally_role"]:
                    raise ImportError("Allies must occupy different roles.")
                key = tuple(item[field] for field in columns if field not in {"wins", "games", "class", "damage_profile", "attributes"})
                if key in seen:
                    raise ImportError("Duplicate row at this table's grain.")
                seen.add(key)
                normalized.append(item)
            except (ValueError, TypeError) as exc:
                raise ImportError(f"{table} row {index}: {exc}") from exc
        rows[table] = sorted(normalized, key=lambda row: tuple(str(row[c]) for c in columns))
    if not rows["champion_stats"]:
        raise ImportError("At least one champion_stats row is required.")
    declared = {(row["name"], row["role"]) for row in rows["champion_roles"]}
    baselines = {(r["name"], r["role"], r["patch"], r["rank"], r["region"]) for r in rows["champion_stats"]}
    baseline_rows = {(r["name"], r["role"], r["patch"], r["rank"], r["region"]): r for r in rows["champion_stats"]}
    for table in ("champion_stats", "matchup_stats", "synergy_stats"):
        for row in rows[table]:
            if (row["name"], row["role"]) not in declared:
                raise ImportError(f"{table}: champion-role is missing from champion_roles.")
            if table != "champion_stats":
                other, role = ("opponent", "opponent_role") if table == "matchup_stats" else ("ally", "ally_role")
                if (row[other], row[role]) not in declared:
                    raise ImportError(f"{table}: counterpart champion-role is undeclared.")
                for name, role_name in ((row["name"], row["role"]), (row[other], row[role])):
                    if (name, role_name, row["patch"], row["rank"], row["region"]) not in baselines:
                        raise ImportError(f"{table}: matching baseline is missing.")
                own = baseline_rows[row["name"], row["role"], row["patch"], row["rank"], row["region"]]
                counterpart = baseline_rows[row[other], row[role], row["patch"], row["rank"], row["region"]]
                other_wins = row["games"] - row["wins"] if table == "matchup_stats" else row["wins"]
                if (row["wins"] > own["wins"] or row["games"] - row["wins"] > own["games"] - own["wins"]
                        or other_wins > counterpart["wins"] or row["games"] - other_wins > counterpart["games"] - counterpart["wins"]):
                    raise ImportError(f"{table}: pair counts exceed corresponding baseline outcomes.")
    return metadata, rows


def import_bundle(connection: sqlite3.Connection, bundle: dict, roster: Roster) -> tuple[str, bool]:
    metadata, tables = validate_bundle(bundle, roster)
    content = json.dumps({"metadata": metadata, **tables}, sort_keys=True, ensure_ascii=False).encode("utf-8")
    digest = hashlib.sha256(content).hexdigest()
    dataset_id = digest[:24]
    # Reimports never add counts; a changed snapshot becomes a separately selectable dataset.
    with connection:
        existing = connection.execute("SELECT id FROM dataset_metadata WHERE id=?", (dataset_id,)).fetchone()
        if existing:
            return dataset_id, False
        connection.execute("INSERT INTO dataset_metadata VALUES (?,?,?,?,?,?,?,?)",
                           (dataset_id, metadata["source"], metadata["license"], metadata["patch"],
                            datetime.now(timezone.utc).isoformat(), int(metadata["is_demo"]), metadata["notes"], digest))
        for row in tables["champions"]:
            connection.execute("INSERT INTO dataset_champions(dataset_id,name,class,damage_profile,attributes) VALUES (?,?,?,?,?)",
                               (dataset_id, row["name"], row["class"], row["damage_profile"], row["attributes"]))
        for table in ("champion_roles", "champion_stats", "matchup_stats", "synergy_stats"):
            columns = ("dataset_id",) + TABLE_COLUMNS[table]
            placeholders = ",".join("?" for _ in columns)
            connection.executemany(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})",
                                   [(dataset_id,) + tuple(row[column] for column in TABLE_COLUMNS[table]) for row in tables[table]])
    return dataset_id, True
