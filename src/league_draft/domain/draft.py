"""Immutable snapshots and transactional edits; never imports Qt."""

from dataclasses import dataclass, replace
from enum import StrEnum

from .roster import Roster


class Team(StrEnum):
    BLUE = "blue"
    RED = "red"


class Role(StrEnum):
    TOP = "Top"
    JUNGLE = "Jungle"
    MID = "Mid"
    ADC = "ADC"
    SUPPORT = "Support"


class Kind(StrEnum):
    PICK = "pick"
    BAN = "ban"


class DraftError(ValueError):
    """An edit was rejected without changing state or history."""


@dataclass(frozen=True)
class Pick:
    champion: str | None = None
    role: Role | None = None


@dataclass(frozen=True)
class Target:
    team: Team
    kind: Kind
    index: int

    def __post_init__(self):
        if not isinstance(self.team, Team) or not isinstance(self.kind, Kind):
            raise DraftError("Invalid team or slot type.")
        if type(self.index) is not int or not 0 <= self.index < 5:
            raise DraftError("Slot must be between 1 and 5.")


@dataclass(frozen=True)
class DraftState:
    blue_picks: tuple[Pick, ...] = tuple(Pick(role=role) for role in Role)
    red_picks: tuple[Pick, ...] = (Pick(),) * 5
    blue_bans: tuple[str | None, ...] = (None,) * 5
    red_bans: tuple[str | None, ...] = (None,) * 5
    user_role: Role = Role.MID
    user_team: Team = Team.BLUE

    def picks(self, team: Team) -> tuple[Pick, ...]:
        return getattr(self, f"{team.value}_picks")

    def bans(self, team: Team) -> tuple[str | None, ...]:
        return getattr(self, f"{team.value}_bans")

    def champion_at(self, target: Target) -> str | None:
        if target.kind == Kind.PICK:
            return self.picks(target.team)[target.index].champion
        return self.bans(target.team)[target.index]


def validate(state: DraftState, roster: Roster) -> None:
    if not isinstance(state.user_role, Role) or not isinstance(state.user_team, Team):
        raise DraftError("Invalid user role or team.")
    picked: list[str] = []
    banned: list[str] = []
    for team in Team:
        picks, bans = state.picks(team), state.bans(team)
        if len(picks) != 5 or len(bans) != 5:
            raise DraftError("Each team requires five pick and five ban slots.")
        roles = []
        for pick in picks:
            if not isinstance(pick, Pick):
                raise DraftError("Invalid pick.")
            if pick.role is not None:
                if not isinstance(pick.role, Role):
                    raise DraftError("Invalid role.")
                roles.append(pick.role)
            if pick.champion is not None:
                picked.append(pick.champion)
        if len(set(roles)) != len(roles):
            raise DraftError(f"{team.value.title()} already has that role. Set it to Unknown first.")
        own_bans = [ban for ban in bans if ban is not None]
        if len(set(own_bans)) != len(own_bans):
            raise DraftError("A team cannot ban the same champion twice.")
        banned.extend(own_bans)
    for name in picked + banned:
        if not isinstance(name, str) or roster.resolve(name) != name:
            raise DraftError("Draft must contain canonical champion names.")
    if len(set(picked)) != len(picked):
        raise DraftError("That champion is already picked. Clear its other slot first.")
    if set(picked) & set(banned):
        raise DraftError("A banned champion cannot be picked; a picked champion cannot be banned.")


class DraftModel:
    def __init__(self, roster: Roster, state: DraftState | None = None):
        self.roster = roster
        self._state = state or DraftState()
        validate(self._state, roster)
        self._history: list[DraftState] = []

    @property
    def state(self) -> DraftState:
        return self._state

    @property
    def can_undo(self) -> bool:
        return bool(self._history)

    def _commit(self, state: DraftState) -> bool:
        validate(state, self.roster)
        if state == self._state:
            return False
        self._history.append(self._state)
        self._state = state
        return True

    def assign(self, target: Target, champion: str | None) -> bool:
        try:
            champion = self.roster.resolve(champion) if champion is not None else None
        except ValueError as exc:
            raise DraftError(str(exc)) from exc
        field = f"{target.team.value}_{target.kind.value}s"
        slots = list(getattr(self.state, field))
        slots[target.index] = (
            replace(slots[target.index], champion=champion)
            if target.kind == Kind.PICK else champion
        )
        return self._commit(replace(self.state, **{field: tuple(slots)}))

    def set_pick_role(self, team: Team, index: int, role: Role | None) -> bool:
        Target(team, Kind.PICK, index)
        field = f"{team.value}_picks"
        picks = list(self.state.picks(team))
        picks[index] = replace(picks[index], role=role)
        return self._commit(replace(self.state, **{field: tuple(picks)}))

    def swap_champions(self, source: Target, destination: Target) -> bool:
        """Move to an empty slot or swap occupied slots, preserving row roles."""
        if source.kind != destination.kind:
            raise DraftError("Drag picks to picks, or bans to bans.")
        if self.state.champion_at(source) is None:
            raise DraftError("The source slot is empty.")
        if source == destination:
            return False
        updates = {}
        for target, name in ((source, self.state.champion_at(destination)),
                             (destination, self.state.champion_at(source))):
            field = f"{target.team.value}_{target.kind.value}s"
            slots = updates.setdefault(field, list(getattr(self.state, field)))
            slots[target.index] = replace(slots[target.index], champion=name) if target.kind == Kind.PICK else name
        return self._commit(replace(self.state, **{field: tuple(slots) for field, slots in updates.items()}))

    def swap_roles(self, team: Team, source: int, destination: int) -> bool:
        Target(team, Kind.PICK, source)
        Target(team, Kind.PICK, destination)
        picks = list(self.state.picks(team))
        left, right = picks[source].role, picks[destination].role
        picks[source] = replace(picks[source], role=right)
        picks[destination] = replace(picks[destination], role=left)
        return self._commit(replace(self.state, **{f"{team.value}_picks": tuple(picks)}))

    def set_user(self, *, role: Role | None = None, team: Team | None = None) -> bool:
        return self._commit(replace(
            self.state,
            user_role=self.state.user_role if role is None else role,
            user_team=self.state.user_team if team is None else team,
        ))

    def undo(self) -> bool:
        if not self._history:
            return False
        self._state = self._history.pop()
        return True

    def reset(self) -> bool:
        return self._commit(DraftState())
