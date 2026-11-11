"""D9-style copy/propose bridge; agent commands and evidence stay caller supplied."""

import hashlib
import json
import math
import os
import shutil
import signal
import stat
import subprocess
import sys
from pathlib import Path

import adapter

MAX_JSON = 16 * 1024 * 1024


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def read(path):
    if path.is_symlink() or path.stat().st_size > MAX_JSON:
        raise ValueError("missing_or_oversized_agent_json")
    return json.loads(path.read_text())


def configuration(path):
    config = read(path)
    if not isinstance(config, dict) or set(config) != {"command", "inputs", "seconds"}:
        raise ValueError("invalid_agent_configuration")
    command, inputs, seconds = [config[k] for k in ("command", "inputs", "seconds")]
    if not (
        isinstance(command, list)
        and command
        and all(isinstance(arg, str) and arg for arg in command)
        and Path(command[0]).is_absolute()
        and isinstance(inputs, dict)
        and inputs
        and any(arg in inputs for arg in command)
        and type(seconds) in (int, float)
        and math.isfinite(seconds)
        and 0 < seconds <= 600
    ):
        raise ValueError("invalid_agent_command_or_budget")
    for name, sha in inputs.items():
        p = Path(name)
        if (
            not p.is_absolute()
            or p.is_symlink()
            or hashlib.sha256(p.read_bytes()).hexdigest() != sha
        ):
            raise ValueError("agent_input_changed: " + name)
    return config


def inventory(root):
    """Do not hide unexpected files or follow candidate-created links."""
    files = {}
    for directory, names, leaves in os.walk(root, followlinks=False):
        names[:] = sorted(n for n in names if n not in {".git", "__pycache__"})
        for name in [*names, *sorted(leaves)]:
            p = Path(directory) / name
            rel = p.relative_to(root).as_posix()
            mode = p.lstat().st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                raise ValueError("unsupported_agent_file: " + rel)
            # The fixture's configured native report is operational output only.
            if stat.S_ISREG(mode) and rel != "test-results.xml":
                files[rel] = {
                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                    "executable": bool(mode & 0o111),
                }
    return files


def prompt(q):
    return (
        "Repair the concrete failures below. Read requirements.md: every accepted "
        "requirement remains binding, including valid Unicode names, original submitted "
        "values, display_name wire fields, the Continue label and latest-request error/pending "
        "behavior. Only the body of Form.validate in client/controller.py is authorized. "
        "Keep its signature, all other source, requirements and existing tests/data intact. "
        "The current tests include retained regressions; run python -B run_tests.py. "
        "Make changes only in this separate workspace. Do not commit, install dependencies, "
        "or write documentation/evidence into it. Your complete source delta is a proposal; "
        "IntentBond rechecks boundaries, behavior and retention before accepting it. "
        "Native review_required is pending semantic review.\n\n"
        + json.dumps({k: q[k] for k in ("requirements", "failure_count", "failures")}, indent=2)
    )


def propose(q, config_path, folder):
    config = configuration(config_path)
    folder.mkdir()
    source = Path(q["worktree"])
    work = folder / "work"
    shutil.copytree(source, work, symlinks=True)
    initial = inventory(work)
    save(folder / "initial.json", initial)
    prompt_path = folder / "prompt.txt"
    prompt_path.write_text(prompt(q))
    seconds = min(config["seconds"], float(q["remaining_seconds"]) - 2)
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("agent_budget_exhausted")
    request, response = folder / "request.json", folder / "response.json"
    save(
        request,
        {
            "schema_version": 1,
            "worktree": str(work),
            "prompt": str(prompt_path),
            "source_sha256": q["source_sha256"],
            "remaining_seconds": seconds,
            "round": q["round"],
        },
    )
    command = [*config["command"], str(request), str(response)]
    outcome = {"command": command, "seconds_limit": seconds, "status": "started"}
    save(folder / "execution.json", outcome)
    with (folder / "stdout.log").open("wb") as stdout, (folder / "stderr.log").open("wb") as stderr:
        child = subprocess.Popen(
            command, cwd=work, stdout=stdout, stderr=stderr, start_new_session=True
        )
        try:
            code = child.wait(timeout=seconds)
            outcome.update(status="exited", returncode=code)
        except subprocess.TimeoutExpired:
            outcome["status"] = "timeout"
            raise ValueError("agent_timeout") from None
        finally:
            # Also stop children left running by a completed wrapper before freezing its delta.
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
            save(folder / "execution.json", outcome)
    final = inventory(work)
    changed = sorted(p for p in initial.keys() | final.keys() if initial.get(p) != final.get(p))
    save(folder / "delta.json", {"changed_paths": changed, "source": final})
    if code != 0:
        raise ValueError("agent_command_failed")
    result = read(response)
    if not isinstance(result, dict) or result.get("source_sha256") != q["source_sha256"]:
        raise ValueError("stale_agent_response")
    if result.get("status") != "completed":
        raise ValueError("agent_incomplete")
    configuration(config_path)
    for name in changed:
        if name not in final:
            raise ValueError("unsupported_agent_deletion: " + name)
        if name in initial and initial[name]["executable"] != final[name]["executable"]:
            raise ValueError("unsupported_agent_mode_change: " + name)
    return {
        "targets": sorted({r for f in q["failures"] for r in f["case"]["requirements"]}),
        "reason": "Caller agent proposal responding to retained counterexamples",
        "files": {name: (work / name).read_text() for name in changed},
    }


def main():
    config, request, response = map(Path, sys.argv[1:])
    q = read(request)
    if q["phase"] == "propose":
        result = {
            "source_sha256": q["source_sha256"],
            "proposal": propose(q, config, request.parent / "agent"),
        }
    else:
        result = adapter.answer(q, "repair", request)
    save(response, result)


if __name__ == "__main__":
    main()
