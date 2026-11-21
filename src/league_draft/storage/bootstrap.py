"""Copy the bundled seed into writable user storage; preserve corrupt files."""

from contextlib import closing
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
import sqlite3

from .database import connect, initialize, migrate


def prepare_database(path: Path, roster, *, seed_path: Path | None = None) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    notice = ""
    if path.exists():
        try:
            with closing(connect(path)) as db:
                if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise sqlite3.DatabaseError("Integrity check failed")
                migrate(db, roster)
            return ""
        except sqlite3.DatabaseError:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
            backup = path.with_name(f"{path.name}.corrupt-{stamp}")
            path.replace(backup)
            notice = f"Corrupt database was preserved as {backup.name}; restored the bundled historical dataset."
    seed = seed_path if seed_path is not None else files("league_draft").joinpath("resources/seed.sqlite3")
    if seed.is_file():
        temporary = path.with_suffix(".installing")
        try:
            temporary.write_bytes(seed.read_bytes())
            with closing(connect(temporary)) as db:
                if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise sqlite3.DatabaseError("Bundled seed failed integrity check")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    else:
        initialize(path, roster)
        notice = notice or "Bundled statistics were unavailable. Created an empty local database; import a licensed dataset."
    return notice
