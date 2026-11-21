from dataclasses import replace

import pytest

from league_draft.domain.draft import DraftState, Pick, Role
from league_draft.recommendation.engine import DEFAULT_WEIGHTS, Settings, recommend, smooth
from league_draft.storage.repository import Counts, Snapshot


@pytest.fixture
def snapshot():
    result = Snapshot()
    for name, role, wins in (("Ahri", "Mid", 120), ("Akali", "Mid", 100), ("Annie", "Mid", 110),
                             ("Lux", "Mid", 105), ("Lux", "Support", 90), ("Leona", "Support", 110), ("Garen", "Top", 100)):
        result.baselines[name, role] = Counts(wins, 200)
        result.roles.setdefault(name, set()).add(role)
        result.attributes[name] = {"frontline": 0.5, "engage": 0.5, "utility": 0.5}
    for name in ("Ahri", "Akali", "Annie"):
        for opponent in ("Ahri", "Akali", "Annie", "Lux"):
            if name != opponent:
                result.matchups[name, "Mid", opponent, "Mid"] = Counts(40, 60)
        result.matchups[name, "Mid", "Lux", "Support"] = Counts(15, 30)
        result.synergies[name, "Mid", "Leona", "Support"] = Counts(35, 50)
    return result


def test_smoothing_and_determinism(snapshot):
    assert smooth(Counts(0, 0), 20) == 0.5
    assert smooth(Counts(10, 10), 10) == 0.75
    first = recommend(DraftState(), snapshot)
    second = recommend(DraftState(), snapshot)
    assert first == second
    assert first
    assert all(0 <= c.score <= 100 and 0 <= c.coverage <= 1 for c in first if c.score is not None)


def test_partial_and_complete_draft_exclusions(snapshot):
    draft = replace(DraftState(), blue_picks=(Pick("Leona", Role.SUPPORT),) + (Pick(),) * 4,
                    red_picks=(Pick("Lux", Role.MID),) + (Pick(),) * 4, blue_bans=("Akali",) + (None,) * 4)
    candidates = recommend(draft, snapshot)
    assert {c.name for c in candidates} == {"Ahri", "Annie"}
    assert all("lane" in c.components and "synergy" in c.components for c in candidates)
    assert all("other_enemy" not in c.components for c in candidates)
    assert all(sum(c.effective_weights.values()) == pytest.approx(1) for c in candidates)


def test_unknown_flex_role_is_marginalized(snapshot):
    draft = replace(DraftState(), red_picks=(Pick("Lux"),) + (Pick(),) * 4)
    ahri = next(c for c in recommend(draft, snapshot) if c.name == "Ahri")
    evidence = [e for e in ahri.evidence if e.counterpart == "Lux"]
    assert {e.role for e in evidence} == {"Mid", "Support"}
    assert sum(e.role_weight for e in evidence) == pytest.approx(1)
    assert any("marginalized" in warning for warning in ahri.warnings)


def test_missing_low_samples_all_zero_and_no_statistical_evidence(snapshot):
    assert recommend(DraftState(), Snapshot()) == []
    high_support = Settings(minimum_games=10_000)
    assert all(c.score is None for c in recommend(DraftState(), snapshot, high_support))
    zeros = Settings(weights=dict.fromkeys(DEFAULT_WEIGHTS, 0))
    assert all(c.score is None for c in recommend(DraftState(), snapshot, zeros))
    only_composition = Settings(weights={key: 1 if key == "composition" else 0 for key in DEFAULT_WEIGHTS})
    assert all(c.score is None for c in recommend(DraftState(), snapshot, only_composition))
    snapshot.baselines.clear(); snapshot.matchups.clear(); snapshot.synergies.clear()
    assert all(c.score is None for c in recommend(DraftState(), snapshot))


def test_settings_reject_nonfinite_and_negative():
    with pytest.raises(ValueError): Settings(alpha=0)
    with pytest.raises(ValueError): Settings(weights={**DEFAULT_WEIGHTS, "lane": -1})
    with pytest.raises(ValueError): Settings(weights={**DEFAULT_WEIGHTS, "lane": float("nan")})
