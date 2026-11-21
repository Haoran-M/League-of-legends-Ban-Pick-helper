"""Versioned JSON recovery with validation and atomic replacement."""

import json
import os
from pathlib import Path
import tempfile

from league_draft.domain.draft import DraftState, Pick, Role, Team, validate
from league_draft.domain.roster import Roster


class SessionError(ValueError):
    pass


def save_session(path: Path, state: DraftState, roster: Roster) -> None:
    validate(state, roster)
    document = {"schema_version": 1, "user_role": state.user_role.value,
                "user_team": state.user_team.value}
    for team in Team:
        document[f"{team.value}_picks"] = [
            {"champion": p.champion, "role": p.role.value if p.role else None}
            for p in state.picks(team)
        ]
        document[f"{team.value}_bans"] = list(state.bans(team))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(document, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_session(path: Path, roster: Roster) -> DraftState:
    try:
        if path.stat().st_size > 100_000:
            raise ValueError("File too large")
        document = json.loads(path.read_text(encoding="utf-8"))
        expected = {"schema_version", "user_role", "user_team", "blue_picks",
                    "red_picks", "blue_bans", "red_bans"}
        if not isinstance(document, dict) or set(document) != expected:
            raise ValueError("Unexpected fields")
        if type(document["schema_version"]) is not int or document["schema_version"] != 1:
            raise ValueError("Unsupported schema")
        values = {"user_role": Role(document["user_role"]), "user_team": Team(document["user_team"])}
        for team in Team:
            picks = document[f"{team.value}_picks"]
            bans = document[f"{team.value}_bans"]
            if not isinstance(picks, list) or not isinstance(bans, list):
                raise ValueError("Slots must be lists")
            for pick in picks:
                if not isinstance(pick, dict) or set(pick) != {"champion", "role"}:
                    raise ValueError("Invalid pick fields")
            values[f"{team.value}_picks"] = tuple(
                Pick(p["champion"], Role(p["role"]) if p["role"] is not None else None)
                for p in picks
            )
            values[f"{team.value}_bans"] = tuple(bans)
        state = DraftState(**values)
        validate(state, roster)
        return state
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise SessionError("Saved draft is invalid or incompatible. Started a fresh draft; the file was kept.") from exc
