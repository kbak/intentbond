"""Portable execution helpers for the trusted example; no network or model client."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def identity(source):
    return {
        p.relative_to(source).as_posix(): (
            hashlib.sha256(p.read_bytes()).hexdigest(),
            "100755" if p.stat().st_mode & 0o111 else "100644",
        )
        for p in sorted(source.rglob("*"))
        if p.is_file() and not {".git", "__pycache__"}.intersection(p.relative_to(source).parts)
    }


def observe(source, rows, folder):
    """Only observer code and inputs are put on the isolated worker's import path.

    This separates reference execution from observation, not OS permissions.
    Run untrusted candidates with external isolation, as with native tests.
    """
    folder.mkdir(parents=True)
    helpers = folder / "helpers"
    helpers.mkdir()
    for name in ("observer.py", "contract.py"):
        shutil.copyfile(ROOT / name, helpers / name)
    inputs = folder / "inputs.json"
    inputs.write_text(json.dumps([{"id": r["id"], "input": r["input"]} for r in rows]))
    before = identity(source)
    command = [
        sys.executable,
        "-I",
        "-B",
        str(ROOT / "worker.py"),
        str(source),
        str(inputs),
        str(helpers),
    ]
    completed = subprocess.run(command, cwd=source, capture_output=True, text=True, timeout=10)
    (folder / "stdout.jsonl").write_text(completed.stdout)
    (folder / "stderr.log").write_text(completed.stderr)
    if completed.returncode:
        raise ValueError("observer_unavailable: see retained stderr.log")
    observations = [json.loads(line) for line in completed.stdout.splitlines()]
    if [row["id"] for row in observations] != [row["id"] for row in rows]:
        raise ValueError("incomplete_observation")
    if identity(source) != before:
        raise ValueError("observer_changed_source")
    return observations
