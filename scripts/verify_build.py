"""Exercise built EXEs with isolated user data and a Python-free PATH.

This does not replace testing on a clean Windows machine or disabling networking
at OS level. It records actual local checks without touching real app storage.
"""

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import subprocess
import time

from league_draft.domain.draft import DraftModel, Kind, Target, Team
from league_draft.domain.roster import load_roster
from league_draft.storage.database import connect
from league_draft.storage.importer import import_bundle
from league_draft.storage.session import save_session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--output", type=Path, default=root / "test-artifacts/build-verification.json")
    args = parser.parse_args()
    roster, _ = load_roster()
    directory = root / ".tmp" / f"build verification {time.time_ns()}"
    directory.mkdir(parents=True)
    environment = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "QT_QPA_PLATFORM"):
        environment.pop(key, None)
    environment["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
    environment["HTTP_PROXY"] = environment["HTTPS_PROXY"] = "http://127.0.0.1:9"
    reports = []

    def run_case(label, executable, data_dir, restore=False):
        output = directory / f"{label}.json"
        command = [str(executable), "--data-dir", str(data_dir), "--self-test", str(output)]
        if not restore:
            command.append("--no-restore")
        started = time.perf_counter()
        result = subprocess.run(command, cwd=directory, env=environment, timeout=60)
        wall_ms = (time.perf_counter() - started) * 1000
        if not output.exists():
            raise RuntimeError(f"{label}: executable produced no diagnostics; exit {result.returncode}")
        report = json.loads(output.read_text(encoding="utf-8"))
        if result.returncode != 0 or not report.get("ok") or not report.get("frozen"):
            raise RuntimeError(f"{label}: failed: {report}")
        reports.append({"case": label, "wall_ms_including_bootloader_and_diagnostic_probes": wall_ms, **report})
        print(f"{label}: passed; {wall_ms:.0f} ms full diagnostic run, {report['analysis_ms']:.1f} ms analysis")
        return report

    portable = root / "dist/portable/LeagueDraftAssistant/LeagueDraftAssistant.exe"
    onefile = root / "dist/LeagueDraftAssistant.exe"
    run_case("portable-fresh", portable, directory / "portable data")
    data_dir = directory / "one file data"
    run_case("onefile-fresh", onefile, data_dir)
    model = DraftModel(roster)
    names = iter(roster.names[:20])
    for kind in Kind:
        for team in Team:
            for index in range(5):
                model.assign(Target(team, kind, index), next(names))
    save_session(data_dir / "draft-state.json", model.state, roster)
    recovered = run_case("onefile-restart-full-draft", onefile, data_dir, restore=True)
    assert recovered["recovered_picks"] == recovered["recovered_bans"] == 10
    assert recovered["remember_draft"]
    demo = json.loads((root / "src/league_draft/resources/demo.json").read_text(encoding="utf-8"))
    with closing(connect(data_dir / "draft-data.sqlite3")) as db:
        import_bundle(db, demo, roster)
    imported = run_case("onefile-restart-imported-data", onefile, data_dir, restore=True)
    assert imported["datasets"] == 5
    bad_draft = b"invalid saved draft fixture"
    (data_dir / "draft-state.json").write_bytes(bad_draft)
    invalid = run_case("onefile-invalid-saved-state", onefile, data_dir, restore=True)
    assert invalid["recovered_picks"] == 0 and not invalid["remember_draft"]
    assert (data_dir / "draft-state.json").read_bytes() == bad_draft
    (data_dir / "draft-data.sqlite3").write_bytes(b"corrupt database fixture")
    restored = run_case("onefile-corrupt-database", onefile, data_dir)
    assert restored["datasets"] == 4 and "preserved" in restored["notice"]
    assert list(data_dir.glob("*.corrupt-*"))
    summary = {"ok": True, "host": "Windows 11 x64, same development machine", "python_on_path": False,
               "network_test": "Invalid proxies; OS networking was not disabled", "cases": reports}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"All {len(reports)} packaged checks passed. Report: {args.output}")


if __name__ == "__main__":
    main()
