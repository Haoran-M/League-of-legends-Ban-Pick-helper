"""Measure exact-filter loads and scoring on the bundled historical database."""

import argparse
from dataclasses import replace
import json
from pathlib import Path
import statistics
import time

from league_draft.domain.draft import DraftModel, DraftState, Kind, Role, Target, Team
from league_draft.domain.roster import load_roster
from league_draft.recommendation.engine import recommend
from league_draft.storage.repository import Filters, Repository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--database", type=Path, default=root / "src/league_draft/resources/seed.sqlite3")
    parser.add_argument("--output", type=Path, default=root / "test-artifacts/benchmark.json")
    args = parser.parse_args()
    roster, _ = load_roster()
    repository = Repository(args.database)
    report = []
    for dataset in repository.datasets():
        filters = Filters(dataset["id"], dataset["patch"], "PRO", "GLOBAL")
        started = time.perf_counter()
        snapshot = repository.load(filters)
        load_ms = (time.perf_counter() - started) * 1000
        model = DraftModel(roster)
        for team in Team:
            for index, role in enumerate(Role):
                eligible = sorted(((counts.games, name) for (name, known_role), counts in snapshot.baselines.items() if known_role == role.value), reverse=True)
                selected = {p.champion for t in Team for p in model.state.picks(t) if p.champion}
                champion = next(name for _, name in eligible if name not in selected)
                model.assign(Target(team, Kind.PICK, index), champion)
                if team == Team.RED:
                    model.set_pick_role(team, index, role)
        full = model.state
        partial = replace(full, blue_picks=full.blue_picks[:2] + DraftState().blue_picks[2:], red_picks=full.red_picks[:2] + DraftState().red_picks[2:])
        for role in Role:
            for scenario, draft in (("empty", DraftState()), ("partial", partial), ("complete", full)):
                started = time.perf_counter()
                result = recommend(replace(draft, user_role=role), snapshot)
                elapsed = (time.perf_counter() - started) * 1000
                report.append({"patch": dataset["patch"], "role": role.value, "scenario": scenario,
                               "load_ms": load_ms, "score_ms": elapsed, "candidates": len(result),
                               "supported": sum(c.score is not None for c in result)})
    times = sorted(row["score_ms"] for row in report)
    summary = {"cases": len(report), "median_score_ms": statistics.median(times),
               "p95_score_ms": times[int((len(times) - 1) * .95)], "max_score_ms": max(times),
               "max_load_ms": max(row["load_ms"] for row in report), "results": report}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}, indent=2))


if __name__ == "__main__":
    main()
