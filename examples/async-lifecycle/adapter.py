"""Caller-supplied, offline D11 profile; compatible with the unchanged repair API."""

import json
import sys
from pathlib import Path

import lifecycle
from runtime import observe


def answer(q, control, request):
    result = {"source_sha256": q["source_sha256"]}
    if q["phase"] == "generate":
        result["cases"] = lifecycle.generate(q["stage"], control)
    elif q["phase"] == "observe":
        result["observations"] = observe(
            Path(q["worktree"]), q["cases"], request.parent / "observed"
        )
        if control == "observation-unavailable":
            result["observations"][0] = {"id": q["cases"][0]["id"], "status": "unavailable"}
        for row in result["observations"]:
            if row["status"] == "returned":
                row["value"] = json.dumps(
                    row["value"], sort_keys=True, separators=(",", ":"), allow_nan=False
                )
    elif q["phase"] == "regression":
        result["test"] = lifecycle.scaffold(q["regression"])
        result["links"] = {"test_async_lifecycle.Lifecycle.test_events": q["regression"]["checks"]}
    elif q["phase"] == "propose":
        result["proposal"] = lifecycle.proposal(Path(q["worktree"]), control)
    else:
        raise ValueError("unknown adapter phase")
    return result


def main():
    control, request, response = sys.argv[1:]
    request = Path(request)
    result = answer(json.loads(request.read_text()), control, request)
    Path(response).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
