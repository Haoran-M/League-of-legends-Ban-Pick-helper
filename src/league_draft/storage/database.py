"""SQLite connections and versioned atomic migrations."""

from datetime import datetime, timezone
from contextlib import closing
from importlib.resources import files
from pathlib import Path
import sqlite3

from league_draft.domain.roster import Roster


def connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=15000")
    return connection


def migrate(connection: sqlite3.Connection, roster: Roster) -> None:
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version > 2:
        raise ValueError("Database was created by a newer application version.")
    if version == 0:
        sql = files("league_draft").joinpath("storage/migrations/001_initial.sql").read_text(encoding="utf-8")
        try:
            connection.executescript("BEGIN IMMEDIATE;\n" + sql)
            connection.executemany("INSERT INTO champions(name) VALUES (?)", [(name,) for name in roster.names])
            connection.execute("INSERT INTO schema_migrations VALUES (?,?)", (1, datetime.now(timezone.utc).isoformat()))
            connection.execute("PRAGMA user_version=1")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    if version < 2:
        sql = files("league_draft").joinpath("storage/migrations/002_dataset_attributes.sql").read_text(encoding="utf-8")
        try:
            connection.executescript("BEGIN IMMEDIATE;\n" + sql)
            connection.execute("INSERT INTO schema_migrations VALUES (?,?)", (2, datetime.now(timezone.utc).isoformat()))
            connection.execute("PRAGMA user_version=2")
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def initialize(path: Path, roster: Roster) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect(path)) as connection:
        migrate(connection, roster)
