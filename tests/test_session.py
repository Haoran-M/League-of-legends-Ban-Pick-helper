import json
import os

import pytest

from league_draft.domain.draft import DraftModel, Kind, Role, Target, Team
from league_draft.storage.session import SessionError, load_session, save_session


def test_roundtrip_unicode_and_roles(roster, tmp_path):
    model = DraftModel(roster)
    model.assign(Target(Team.RED, Kind.PICK, 0), "Kai'Sa")
    model.assign(Target(Team.BLUE, Kind.BAN, 0), "Nunu & Willump")
    model.set_user(role=Role.SUPPORT, team=Team.RED)
    path = tmp_path / "path with spaces" / "draft.json"
    save_session(path, model.state, roster)
    assert load_session(path, roster) == model.state
    assert not list(path.parent.glob("*.tmp"))


@pytest.mark.parametrize("corruption", ["json", "version", "slots", "duplicate", "unknown", "role", "fields", "type", "size"])
def test_corrupt_file_preserved(roster, tmp_path, corruption):
    path = tmp_path / "draft.json"
    save_session(path, DraftModel(roster).state, roster)
    document = json.loads(path.read_text(encoding="utf-8"))
    if corruption == "version":
        document["schema_version"] = 2
    elif corruption == "slots":
        document["blue_picks"] = []
    elif corruption == "duplicate":
        document["blue_picks"][0]["champion"] = "Ahri"
        document["red_picks"][0]["champion"] = "Ahri"
    elif corruption == "unknown":
        document["red_bans"][0] = "unknown"
    elif corruption == "role":
        document["red_picks"][0]["role"] = "Carry"
    elif corruption == "fields":
        document["unexpected"] = True
    elif corruption == "type":
        document["red_bans"][0] = []
    path.write_text("broken{" if corruption == "json" else " " * 100_001 if corruption == "size"
                    else json.dumps(document), encoding="utf-8")
    original = path.read_bytes()
    with pytest.raises(SessionError):
        load_session(path, roster)
    assert path.read_bytes() == original


def test_failed_replace_keeps_previous_session(roster, tmp_path, monkeypatch):
    path = tmp_path / "draft.json"
    model = DraftModel(roster)
    save_session(path, model.state, roster)
    before = path.read_bytes()
    model.assign(Target(Team.BLUE, Kind.PICK, 0), "Ahri")

    def denied(*args):
        raise PermissionError("test: replacement denied")

    monkeypatch.setattr(os, "replace", denied)
    with pytest.raises(PermissionError):
        save_session(path, model.state, roster)
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]
