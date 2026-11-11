"""Observe the fixture in a fresh interpreter without importing reference models."""

import json
import sys
from pathlib import Path

source, inputs, helpers = sys.argv[1:]
sys.path[:0] = [source, helpers]
from observer import observe  # noqa: E402

for row in json.loads(Path(inputs).read_text()):
    try:
        result = {"id": row["id"], "status": "returned", "value": observe(row["input"])}
    except Exception as exc:
        result = {
            "id": row["id"],
            "status": "candidate_exception",
            "error": type(exc).__name__ + ": " + str(exc),
        }
    print(json.dumps(result, allow_nan=False), flush=True)
