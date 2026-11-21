from dataclasses import FrozenInstanceError

import pytest

from league_draft.domain.draft import DraftError, DraftModel, DraftState, Kind, Role, Target, Team
from league_draft.domain.roster import Roster, load_roster


def target(team=Team.BLUE, kind=Kind.PICK, index=0):
    return Target(team, kind, index)


@pytest.mark.parametrize("alias,canonical", [
    ("kai sa", "Kai'Sa"), ("K’SANTE", "K'Sante"), ("MONKEYKING", "Wukong"),
    ("nunu", "Nunu & Willump"), ("J4", "Jarvan IV"), ("  Dr. Mundo  ", "Dr. Mundo"),
])
def test_canonical_aliases(roster, alias, canonical):
    assert roster.resolve(alias) == canonical
    assert canonical in roster.search(alias)


def test_roster_provenance_and_names_only():
    roster, metadata = load_roster()
    assert len(roster.names) == 173
    assert metadata["version"] == "16.23.1"
    assert metadata["source"].startswith("https://ddragon.leagueoflegends.com/")
    assert roster.search("zzzznomatch") == ()


def test_ambiguous_alias_rejected():
    with pytest.raises(ValueError, match="Ambiguous"):
        Roster(["Ahri", "Akali"], {"AHRI": "Akali"})


def test_full_draft_replace_clear_undo_reset(roster):
    model = DraftModel(roster)
    original = model.state
    names = iter(roster.names[:20])
    for kind in Kind:
        for team in Team:
            for index in range(5):
                model.assign(target(team, kind, index), next(names))
    complete = model.state
    assert sum(p.champion is not None for t in Team for p in complete.picks(t)) == 10
    assert sum(b is not None for t in Team for b in complete.bans(t)) == 10
    model.assign(target(), roster.names[20])
    assert model.state.blue_picks[0].champion == roster.names[20]
    model.undo()
    assert model.state == complete
    model.assign(target(), None)
    assert model.state.blue_picks[0].champion is None
    assert model.state.blue_picks[0].role == Role.TOP
    model.undo()
    model.reset()
    assert model.state == original
    model.undo()
    assert model.state == complete


@pytest.mark.parametrize("other", [target(index=1), target(Team.RED)])
def test_duplicate_pick_is_transactional(roster, other):
    model = DraftModel(roster)
    model.assign(target(), "Ahri")
    before = model.state
    with pytest.raises(DraftError, match="already picked"):
        model.assign(other, "ahri")
    assert model.state == before
    model.undo()
    assert model.state == DraftState()
    assert not model.can_undo


@pytest.mark.parametrize("ban_first", [True, False])
def test_ban_pick_conflicts_both_directions(roster, ban_first):
    model = DraftModel(roster)
    ban = target(Team.RED, Kind.BAN)
    first, second = (ban, target()) if ban_first else (target(), ban)
    model.assign(first, "Ahri")
    before = model.state
    with pytest.raises(DraftError, match="banned champion"):
        model.assign(second, "Ahri")
    assert model.state == before


def test_same_opposing_ban_allowed_but_own_duplicate_rejected(roster):
    model = DraftModel(roster)
    model.assign(target(kind=Kind.BAN), "Ahri")
    model.assign(target(Team.RED, Kind.BAN), "Ahri")
    with pytest.raises(DraftError, match="same champion twice"):
        model.assign(target(kind=Kind.BAN, index=1), "Ahri")


def test_unknown_roles_and_role_conflict(roster):
    model = DraftModel(roster)
    assert all(p.role is None for p in model.state.red_picks)
    model.set_pick_role(Team.RED, 0, Role.MID)
    with pytest.raises(DraftError, match="already has that role"):
        model.set_pick_role(Team.RED, 1, Role.MID)
    model.set_pick_role(Team.RED, 0, None)
    model.set_pick_role(Team.RED, 1, Role.MID)
    model.set_user(role=Role.ADC, team=Team.RED)
    assert model.state.user_team == Team.RED
    assert model.state.user_role == Role.ADC


def test_noop_unknown_champion_and_immutable_snapshot(roster):
    model = DraftModel(roster)
    assert not model.undo()
    assert not model.reset()
    assert not model.assign(target(), None)
    with pytest.raises(DraftError, match="Unknown champion"):
        model.assign(target(), "imaginary champion")
    assert not model.can_undo
    with pytest.raises(FrozenInstanceError):
        model.state.user_team = Team.RED


@pytest.mark.parametrize("index", [-1, 5, True, "0"])
def test_invalid_slot(index):
    with pytest.raises(DraftError):
        target(index=index)
