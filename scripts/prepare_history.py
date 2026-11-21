"""Reproduce licensed historical aggregates from a local ChainCC CSV snapshot.

This offline development command strips player/team/game identifiers. It validates
complete ten-player games before deriving directed pair counts by exact patch.
"""

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path

import pandas as pd

from league_draft.domain.roster import load_roster
from league_draft.storage.database import connect, initialize
from league_draft.storage.importer import import_bundle

ROOT = Path(__file__).resolve().parents[1]
ROLES = {"top": "Top", "jng": "Jungle", "mid": "Mid", "bot": "ADC", "sup": "Support"}


def aggregate(frame: pd.DataFrame, keys: list[str]) -> list[dict]:
    result = frame.groupby(keys, sort=True, dropna=False)["win"].agg(wins="sum", games="size").reset_index()
    result["wins"] = result["wins"].astype(int)
    result["games"] = result["games"].astype(int)
    return result.to_dict("records")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--champion-metadata", type=Path, required=True)
    parser.add_argument("--patches", nargs="+", default=["16.17", "16.18", "16.20", "16.22"])
    parser.add_argument("--database", type=Path, default=ROOT / "src/league_draft/resources/seed.sqlite3")
    args = parser.parse_args()
    roster, _ = load_roster()
    # Only these columns enter memory; player names and performance telemetry are never retained.
    frame = pd.read_csv(args.source, compression="infer", dtype=str, usecols=["game_id", "date", "league", "patch", "side", "position", "champion", "result"])
    if frame.isna().any().any():
        raise ValueError("Required source values are missing")
    if frame.duplicated(["game_id", "side", "position"]).any():
        raise ValueError("Duplicate game/side/role records")
    frame["name"] = frame["champion"].map(roster.resolve)
    frame["role"] = frame["position"].map(ROLES)
    if frame["role"].isna().any() or not set(frame["side"]) <= {"Blue", "Red"}:
        raise ValueError("Unrecognized roles or sides")
    if not set(frame["result"]) <= {"TRUE", "FALSE"}:
        raise ValueError("Unrecognized results")
    frame["win"] = frame["result"].eq("TRUE").astype(int)
    for game, players in frame.groupby("game_id", sort=False):
        if (len(players) != 10 or players["name"].nunique() != 10 or players["win"].sum() != 5
                or players["patch"].nunique() != 1 or players["league"].nunique() != 1):
            raise ValueError(f"Incomplete or inconsistent game: {game}")
        for _, team in players.groupby("side"):
            if len(team) != 5 or set(team["role"]) != set(ROLES.values()) or team["win"].nunique() != 1:
                raise ValueError(f"Inconsistent team: {game}")
    tags = json.loads(args.champion_metadata.read_text(encoding="utf-8-sig"))["data"]
    champion_rows = []
    for champion in tags.values():
        classes = champion["tags"]
        # Transparent class-based heuristics, never measured performance statistics.
        attributes = {"frontline": 1.0 if "Tank" in classes else 0.4 if "Fighter" in classes else 0.0,
                      "engage": 0.7 if "Tank" in classes else 0.3 if "Fighter" in classes else 0.0,
                      "utility": 1.0 if "Support" in classes else 0.0}
        champion_rows.append({"name": champion["name"], "class": "/".join(classes) or "Unknown",
                              "damage_profile": "Unknown", "attributes": attributes})
    initialize(args.database, roster)
    destination = ROOT / "data/chaincc"
    destination.mkdir(parents=True, exist_ok=True)
    report = {"source": "https://chaincc.lol/data/chaincc-players-2026.csv.gz",
              "license_page": "https://chaincc.lol/free/data", "license": "CC-BY-4.0",
              "license_url": "https://creativecommons.org/licenses/by/4.0/",
              "source_sha256": hashlib.sha256(args.source.read_bytes()).hexdigest(),
              "input_player_rows": len(frame), "input_complete_games": frame["game_id"].nunique(),
              "patches": {}, "changes": "Selected patches; canonicalized names/roles; aggregated wins/games; removed all player, team and match identifiers.",
              "attribution": "ChainCC. League of Legends esports match dataset. https://chaincc.lol/free/data (accessed 2026-11-21)."}
    for patch in args.patches:
        current = frame.loc[frame["patch"].eq(patch)].copy()
        if current.empty:
            raise ValueError(f"No source games for {patch}")
        regional = current.assign(region=current["league"])
        global_rows = current.assign(region="GLOBAL")
        combined = pd.concat([regional, global_rows], ignore_index=True)
        combined["rank"] = "PRO"
        baseline_keys = ["name", "role", "patch", "rank", "region"]
        baselines = aggregate(combined, baseline_keys)
        # Each game/region has exactly ten rows. Pair on BOTH game and region.
        pairs = combined.merge(combined[["game_id", "region", "name", "role", "side"]], on=["game_id", "region"], suffixes=("", "_other"), validate="many_to_many")
        enemies = pairs.loc[pairs["side"].ne(pairs["side_other"])].rename(columns={"name_other": "opponent", "role_other": "opponent_role"})
        allies = pairs.loc[pairs["side"].eq(pairs["side_other"]) & pairs["name"].ne(pairs["name_other"])].rename(columns={"name_other": "ally", "role_other": "ally_role"})
        assert len(enemies) == len(combined) * 5
        assert len(allies) == len(combined) * 4
        roles = current[["name", "role"]].drop_duplicates().sort_values(["name", "role"]).to_dict("records")
        games = current["game_id"].nunique()
        bundle = {"metadata": {"source": report["source"], "license": "CC-BY-4.0", "patch": patch, "is_demo": False,
                    "notes": f"ChainCC professional esports, {games} complete games on patch {patch}. PRO is competition, not solo-queue rank. GLOBAL aggregates leagues; other region values are league codes. No solo-queue generalization. Retrieved 2026-11-21. Full attribution and audit: DATA_SOURCES.md."},
                  "champions": champion_rows, "champion_roles": roles, "champion_stats": baselines,
                  "matchup_stats": aggregate(enemies, ["name", "opponent", "role", "opponent_role", "patch", "rank", "region"]),
                  "synergy_stats": aggregate(allies, ["name", "ally", "role", "ally_role", "patch", "rank", "region"])}
        path = destination / f"patch-{patch}.json"
        path.write_text(json.dumps(bundle, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        with closing(connect(args.database)) as db:
            dataset_id, changed = import_bundle(db, bundle, roster)
        report["patches"][patch] = {"complete_games": games, "player_rows": len(current), "from": current["date"].min(), "through": current["date"].max(), "dataset_id": dataset_id,
                                    "baseline_rows": len(baselines), "matchup_rows": len(bundle["matchup_stats"]), "synergy_rows": len(bundle["synergy_stats"])}
        print(f"{patch}: {games} games; {len(baselines)} baseline, {len(bundle['matchup_stats'])} matchup, {len(bundle['synergy_stats'])} synergy rows; {'imported' if changed else 'unchanged'}")
    (destination / "PROVENANCE.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
