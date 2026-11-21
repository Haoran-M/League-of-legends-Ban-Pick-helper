"""Deterministic support-aware comparative scores; never win probabilities."""

from dataclasses import dataclass, field
import math

try:
    import numpy as np
except ImportError:
    # Android embeds the shared engine without shipping the NumPy native runtime.
    np = None

from league_draft.domain.draft import DraftState, Team
from league_draft.storage.repository import Counts, Snapshot

DEFAULT_WEIGHTS = {"lane": 30.0, "other_enemy": 15.0, "synergy": 25.0,
                   "composition": 15.0, "baseline": 10.0, "robustness": 5.0}


@dataclass(frozen=True)
class Settings:
    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    alpha: float = 20.0
    minimum_games: int = 20

    def __post_init__(self):
        if set(self.weights) != set(DEFAULT_WEIGHTS) or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in self.weights.values()):
            raise ValueError("Weights must be finite nonnegative values for every component.")
        if not math.isfinite(self.alpha) or self.alpha <= 0 or type(self.minimum_games) is not int or self.minimum_games < 1:
            raise ValueError("Smoothing must be positive and minimum games must be at least 1.")


@dataclass(frozen=True)
class Evidence:
    kind: str
    counterpart: str
    role: str
    wins: int
    games: int
    expected: float
    smoothed: float
    effect: float
    role_weight: float


@dataclass
class Candidate:
    name: str
    score: float | None
    coverage: float
    baseline: Counts | None
    components: dict[str, float] = field(default_factory=dict)
    effective_weights: dict[str, float] = field(default_factory=dict)
    evidence: list[Evidence] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def smooth(counts: Counts, alpha: float, prior: float = 0.5) -> float:
    return (counts.wins + alpha * prior) / (counts.games + alpha)


def _logit(probability: float) -> float:
    bounded = max(1e-6, min(1 - 1e-6, probability))
    return math.log(bounded / (1 - bounded))


def _sigmoid(value: float) -> float:
    return 1 / (1 + math.exp(-value))


def normalize_effect(effect: float) -> float:
    """A residual -20..+20 percentage points maps to 0..100, clipped."""
    return max(0.0, min(100.0, 50.0 + 250.0 * effect))


def percentile(values: list[float], percentage: float) -> float:
    """NumPy's default linear percentile, with an equivalent stdlib fallback."""
    if not values or not 0 <= percentage <= 100:
        raise ValueError("Percentile requires observations and a percentage from 0 to 100.")
    if np is not None:
        return float(np.percentile(values, percentage))
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentage / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def role_distribution(snapshot: Snapshot, name: str, known_role) -> dict[str, float]:
    if known_role is not None:
        return {str(known_role): 1.0}
    counts = {role: stat.games for (champion, role), stat in snapshot.baselines.items() if champion == name}
    total = sum(counts.values())
    return {role: games / total for role, games in counts.items()} if total else {}


def composition_gaps(draft: DraftState, snapshot: Snapshot) -> list[str]:
    allies = [p.champion for p in draft.picks(draft.user_team) if p.champion and p.role != draft.user_role]
    if not any(snapshot.attributes.get(name) for name in allies):
        return ["Composition attributes are unavailable for selected allies."] if allies else ["No allies selected; composition is provisional."]
    totals = {key: sum(snapshot.attributes.get(name, {}).get(key, 0) for name in allies) for key in ("frontline", "engage", "utility")}
    gaps = [f"Low {key} by class heuristic" for key, total in totals.items() if total < 1]
    return gaps or ["Frontline, engage and utility heuristics are covered."]


def recommend(draft: DraftState, snapshot: Snapshot, settings: Settings | None = None) -> list[Candidate]:
    settings = settings or Settings()
    user_role = draft.user_role.value
    enemy_team = Team.RED if draft.user_team == Team.BLUE else Team.BLUE
    enemies = [p for p in draft.picks(enemy_team) if p.champion]
    allies = [p for p in draft.picks(draft.user_team) if p.champion and p.role != draft.user_role]
    excluded = {p.champion for team in Team for p in draft.picks(team) if p.champion}
    excluded.update(b for team in Team for b in draft.bans(team) if b)
    uncertainty = (sum(p.role is None for p in enemies) / len(enemies)) if enemies else 1.0
    requested = dict(settings.weights)
    transfer = requested["lane"] * 0.5 * uncertainty
    requested["lane"] -= transfer
    requested["robustness"] += transfer
    total_requested = sum(requested.values())
    results = []
    for name in sorted(snapshot.roles, key=str.casefold):
        if name in excluded or user_role not in snapshot.roles[name]:
            continue
        baseline = snapshot.baselines.get((name, user_role))
        result = Candidate(name, None, 0.0, baseline)
        components, coverage = {}, {}
        if baseline is not None and baseline.games >= settings.minimum_games:
            candidate_rate = smooth(baseline, settings.alpha)
            components["baseline"] = normalize_effect(candidate_rate - 0.5)
            coverage["baseline"] = 1.0
        else:
            candidate_rate = smooth(baseline, settings.alpha) if baseline else 0.5
        pair_effects: dict[str, list[tuple[float, float]]] = {"lane": [], "other_enemy": [], "synergy": []}
        possible = {"lane": 0.0, "other_enemy": 0.0, "synergy": 0.0}
        for kind, partners, table in (("enemy", enemies, snapshot.matchups), ("ally", allies, snapshot.synergies)):
            for partner in partners:
                distribution = role_distribution(snapshot, partner.champion, partner.role)
                if not distribution:
                    # Unknown-role observations without baseline support provide no evidence.
                    possible["other_enemy" if kind == "enemy" else "synergy"] += 1.0
                for role, probability in distribution.items():
                    component = "lane" if kind == "enemy" and role == user_role else "other_enemy" if kind == "enemy" else "synergy"
                    if kind == "ally" and role == user_role:
                        continue
                    possible[component] += probability
                    count = table.get((name, user_role, partner.champion, role))
                    other = snapshot.baselines.get((partner.champion, role))
                    if not baseline or not count or not other or min(baseline.games, count.games, other.games) < settings.minimum_games:
                        continue
                    other_rate = smooth(other, settings.alpha)
                    expected = _sigmoid(_logit(candidate_rate) - _logit(other_rate)) if kind == "enemy" else _sigmoid((_logit(candidate_rate) + _logit(other_rate)) / 2)
                    observed = smooth(count, settings.alpha, expected)
                    effect = observed - expected
                    pair_effects[component].append((effect, probability))
                    result.evidence.append(Evidence(component, partner.champion, role, count.wins, count.games,
                                                     expected, observed, effect, probability))
        for component, values in pair_effects.items():
            supported = sum(weight for _, weight in values)
            if supported:
                components[component] = normalize_effect(sum(effect * weight for effect, weight in values) / supported)
                coverage[component] = supported / possible[component] if possible[component] else 0.0
        # Robustness is a lower-tail summary of supported lane residuals, not independent trials.
        lane_effects = []
        if baseline and baseline.games >= settings.minimum_games:
            for (champion, role, opponent, opponent_role), count in snapshot.matchups.items():
                if champion != name or role != user_role or opponent_role != user_role or count.games < settings.minimum_games:
                    continue
                other = snapshot.baselines.get((opponent, opponent_role))
                if other is None or other.games < settings.minimum_games:
                    continue
                expected = _sigmoid(_logit(candidate_rate) - _logit(smooth(other, settings.alpha)))
                lane_effects.append(smooth(count, settings.alpha, expected) - expected)
        if len(lane_effects) >= 3:
            components["robustness"] = normalize_effect(percentile(lane_effects, 20))
            coverage["robustness"] = min(1.0, len(lane_effects) / 10)
        attributes = snapshot.attributes.get(name, {})
        keys = ("frontline", "engage", "utility")
        if all(key in attributes for key in keys):
            deficits = {key: max(0, 1 - sum(snapshot.attributes.get(p.champion, {}).get(key, 0) for p in allies)) for key in keys}
            need = sum(deficits.values())
            components["composition"] = 50 + 50 * sum(deficits[key] * attributes[key] for key in keys) / need if need else 50.0
            coverage["composition"] = sum(bool(snapshot.attributes.get(p.champion)) for p in allies) / len(allies) if allies else 1.0
        statistical = set(components) - {"composition"}
        if total_requested == 0:
            result.warnings.append("All component weights are zero.")
        elif not any(requested[c] > 0 for c in statistical):
            result.warnings.append("Insufficient statistical evidence at the selected filters and minimum support.")
        else:
            available = {c: requested[c] for c in components if requested[c] > 0}
            denominator = sum(available.values())
            result.effective_weights = {c: w / denominator for c, w in available.items()}
            result.score = sum(components[c] * w for c, w in result.effective_weights.items())
            result.coverage = sum(requested[c] * coverage.get(c, 0) for c in components) / total_requested
        result.components = components
        if uncertainty:
            result.warnings.append("Unknown opponent roles are marginalized using observed role frequencies; flex uncertainty remains.")
        if result.coverage < 0.65:
            result.warnings.append("Limited evidence coverage; unavailable components were dropped and weights renormalized.")
        if baseline and baseline.games < 100:
            result.warnings.append(f"Small baseline sample: {baseline.games} champion-role appearances.")
        result.warnings.append("Comparative score, not win probability. Pair rows overlap the same matches; their sample counts must not be summed.")
        results.append(result)
    return sorted(results, key=lambda c: (c.score is None, -(c.score or 0), c.name.casefold()))
