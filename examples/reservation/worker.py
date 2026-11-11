"""Observe responses and complete state in a fresh interpreter, without references."""

import json
import sys
from pathlib import Path

source, inputs = sys.argv[1:]
sys.path.insert(0, source)
from entrypoint import evaluate  # noqa: E402

for row in json.loads(Path(inputs).read_text()):
    try:
        value = json.dumps(
            evaluate(row["input"]), sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        result = {"id": row["id"], "status": "returned", "value": value}
    except Exception as exc:
        result = {
            "id": row["id"],
            "status": "candidate_exception",
            "error": type(exc).__name__ + ": " + str(exc),
        }
    print(json.dumps(result, allow_nan=False), flush=True)
