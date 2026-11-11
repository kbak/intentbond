"""Reservation reference phases and instructions over the shared command bridge."""

import json
import subprocess
import sys
from pathlib import Path

import reservation_profile as profile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent_bridge as bridge  # noqa: E402

INSTRUCTIONS = (
    "Repair the concrete failures below. Read requirements.md: every accepted requirement "
    "remains binding. Failed batches must preserve both active reservations and the entire "
    "idempotency history. Replay after cancellation must not reactivate a key; conflicting "
    "quantities still fail. Preserve capacity, cancellation, successful and empty batches. "
    "Only the body of Service.batch in service.py is authorized. Keep its signature, all "
    "other source, requirements and existing tests/data intact. The current tests include "
    "retained regressions; run python -B run_tests.py."
)


def observe(q, folder):
    folder.mkdir()
    source = Path(q["worktree"])
    initial = bridge.inventory(source)
    inputs = folder / "inputs.json"
    bridge.save(inputs, [{"id": c["id"], "input": c["input"]} for c in q["cases"]])
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(profile.ROOT / "worker.py"), str(source), str(inputs)],
        cwd=source,
        capture_output=True,
        text=True,
        timeout=min(10, q["remaining_seconds"]),
    )
    (folder / "stdout.jsonl").write_text(result.stdout)
    (folder / "stderr.log").write_text(result.stderr)
    if result.returncode:
        raise ValueError("reservation_observer_unavailable")
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    if [r["id"] for r in rows] != [c["id"] for c in q["cases"]]:
        raise ValueError("incomplete_reservation_observation")
    if bridge.inventory(source) != initial:
        raise ValueError("observer_changed_source")
    return rows


def main():
    config, request, response = map(Path, sys.argv[1:])
    q = bridge.read(request)
    result = {"source_sha256": q["source_sha256"]}
    if q["phase"] == "generate":
        result["cases"] = profile.generate(q["stage"])
    elif q["phase"] == "observe":
        result["observations"] = observe(q, request.parent / "observed")
    elif q["phase"] == "regression":
        result.update(test=profile.scaffold(q["regression"]), links=profile.LINKS)
    elif q["phase"] == "propose":
        result["proposal"] = bridge.propose(
            q,
            config,
            request.parent / "agent",
            instructions=INSTRUCTIONS,
            report_path="test-results.xml",
        )
    else:
        raise ValueError("unknown_reservation_phase")
    bridge.save(response, result)


if __name__ == "__main__":
    main()
