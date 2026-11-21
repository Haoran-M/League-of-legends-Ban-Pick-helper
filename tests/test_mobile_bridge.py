from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import shutil
import time

import numpy as np
import pytest

from league_draft.recommendation import engine

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mobile_bridge", ROOT / "android/app/src/main/python/mobile_bridge.py")
mobile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mobile)


@pytest.fixture
def session(tmp_path):
    return mobile.MobileSession(str(tmp_path / "phone"), str(ROOT / "src/league_draft/resources/seed.sqlite3"))


def assign(session, champion, index=0, team="blue", kind="pick"):
    return session.dispatch("assign", dict(team=team, kind=kind, index=index, champion=champion))


def test_mobile_full_draft_swaps_and_restart(session):
    names = iter(session.roster.names[:20])
    for kind in ("pick", "ban"):
        for team in ("blue", "red"):
            for index in range(5):
                assert assign(session, next(names), index, team, kind)["ok"]
    before = session.model.state
    assert not assign(session, before.blue_picks[1].champion)["ok"]
    assert not assign(session, before.blue_bans[0])["ok"]
    assert session.model.state == before
    assert session.dispatch("swap", {"source": {"team": "blue", "kind": "pick", "index": 0}, "destination": {"team": "blue", "kind": "pick", "index": 2}})["ok"]
    assert session.dispatch("undo", {})["ok"]
    assert session.model.state == before
    assert session.dispatch("set_role", {"team": "blue", "index": 0, "role": "Mid"})["ok"]
    assert session.model.state.blue_picks[2].role.value == "Top"
    recovered = mobile.MobileSession(str(session.directory), str(ROOT / "src/league_draft/resources/seed.sqlite3"))
    assert recovered.model.state == session.model.state
    session.dispatch("reset", {}); session.dispatch("undo", {})
    assert session.model.state == recovered.model.state


def test_mobile_reuses_same_scoring_and_no_numpy_fallback(session, monkeypatch):
    assign(session, "Leona", 4)
    assign(session, "Akali", team="red")
    normal = session.analyze()
    monkeypatch.setattr(engine, "np", None)
    fallback = session.analyze()
    assert [r["name"] for r in normal["results"]] == [r["name"] for r in fallback["results"]]
    for first, second in zip(normal["results"], fallback["results"]):
        if first["score"] is not None:
            assert first["score"] == pytest.approx(second["score"])
    assert all(r["name"] not in {"Akali", "Leona"} for r in fallback["results"])
    assert fallback["elapsed_ms"] < 10000


@pytest.mark.parametrize("observations", [[1], [1, 3], [4, 1, 8, 2, 9], [-.2, .7, -.1, .01]])
def test_linear_percentile_matches_numpy(monkeypatch, observations):
    expected = float(np.percentile(observations, 20))
    monkeypatch.setattr(engine, "np", None)
    assert engine.percentile(observations, 20) == pytest.approx(expected)


def test_mobile_import_and_filters_are_exact(session):
    source = session.directory / "import.json"
    shutil.copyfile(ROOT / "src/league_draft/resources/demo.json", source)
    assert session.dispatch("import_json", {"path": str(source)})["ok"]
    first = session.filters.dataset_id
    assert session.view()["metadata"]["is_demo"] == 1
    assert session.dispatch("import_json", {"path": str(source)})["ok"]
    assert session.filters.dataset_id == first
    assert len(session.datasets) == 5
    assert session.analyze()["metadata"]["is_demo"] == 1
    assert not session.dispatch("set_filters", {"dataset_id": "missing"})["ok"]
    assert not session.dispatch("import_json", {"path": str(ROOT / "src/league_draft/resources/demo.json")})["ok"]


def test_mobile_corruption_export_and_opt_out(session):
    assign(session, "kaisa", 3)
    exported = session.dispatch("export", {})
    assert json.loads(exported["json"])["blue_picks"][3]["champion"] == "Kai'Sa"
    assert session.dispatch("remember", {"enabled": False})["ok"]
    assert not session.state_path.exists()
    assert session.dispatch("remember", {"enabled": True})["ok"]
    session.state_path.write_text("corrupt fixture", encoding="utf-8")
    recovered = mobile.MobileSession(str(session.directory), str(ROOT / "src/league_draft/resources/seed.sqlite3"))
    assert recovered.model.state.blue_picks[3].champion is None
    assert list(session.directory.glob("draft-state.json.corrupt-*"))
