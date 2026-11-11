"""Run D4's reservation profile with a caller-supplied coding agent, offline if desired."""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import reservation_profile as profile
from agent_adapter import bridge

from intentbond.change_guard import prepare
from intentbond.common import CheckError, digest, read_json, write_json
from intentbond.oft import default_jar
from intentbond.repair import repair
from intentbond.runner import check, verify


def policy(config_path, seconds):
    return bridge.policy(
        config_path,
        seconds,
        root=profile.ROOT,
        requirements=profile.REQUIREMENTS,
        edits=[
            {
                "path": "service.py",
                "symbol": "Service.batch",
                "requirements": [profile.references.ATOMIC],
            }
        ],
        regression=profile.REGRESSION,
    )


def baseline(out, variant, jar):
    source = out / "source"
    shutil.copytree(
        profile.ROOT / "fixture", source, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    if variant == "deep-copy":
        path = source / "service.py"
        path.write_text(
            path.read_text().replace("copy.copy(self.store)", "copy.deepcopy(self.store)")
        )
    elif variant != "shallow-copy":
        raise CheckError("Unknown reservation variant")
    scope = read_json(source / "scope.json")
    scope["tests"]["command"] = [sys.executable, "-B", "run_tests.py"]
    write_json(source / "scope.json", scope)
    write_json(out / "scope.json", scope)

    def git(*args):
        return subprocess.check_output(
            [
                "git",
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "init.templateDir=",
                "-C",
                str(source),
                *args,
            ],
            text=True,
        ).strip()

    git("init", "-q", "-b", "main")
    git("add", ".")
    git(
        "-c",
        "user.name=Offline example",
        "-c",
        "user.email=example@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-qm",
        "Accepted reservation fixture",
    )
    base = git("rev-parse", "HEAD")
    initial = bridge.inventory(source, "test-results.xml")
    with patch("intentbond.repair.repair", side_effect=AssertionError("default invoked repair")):
        result = check(source, out / "scope.json", base, "worktree", out / "native", jar)
        matched = verify(
            source, out / "scope.json", base, "worktree", out / "native/evidence.json", True
        )
    assert result["status"] == "passed" and matched["status"] == "matched"
    assert bridge.inventory(source, "test-results.xml") == initial
    assert not (source / profile.REGRESSION["test_path"]).exists()
    checks = sorted(
        {c for values in read_json(source / "tests/links.json").values() for c in values}
    )
    assert len(checks) == 5
    declaration = {
        "schema_version": 1,
        "requirements": {"preserve": profile.REQUIREMENTS, "add": [], "change": [], "remove": []},
        "protected_paths": ["api_contract.py", "api.py", "entrypoint.py", "store.py"],
        "checks": checks,
        "check_support_paths": ["run_tests.py"],
    }
    write_json(out / "declaration.json", declaration)
    guard = prepare(
        out / "native/evidence.json",
        out / "declaration.json",
        out / "guard",
        source,
        base,
        jar,
        scope_path=out / "scope.json",
    )
    return {
        "source": source,
        "base": base,
        "scope": out / "scope.json",
        "guard": guard,
        "native": result["status"],
    }


def run(out, config, jar, seconds=240, variant="shallow-copy"):
    if not __debug__:
        raise CheckError("Qualification assertions require Python without -O")
    out, config = out.resolve(), config.resolve()
    if out.is_relative_to(profile.ROOT.parents[1]):
        raise CheckError("Use a new output directory outside the source checkout")
    if config.is_relative_to(out):
        raise CheckError("Keep the agent configuration outside the output directory")
    if not 0 < seconds <= 600:
        raise CheckError("Use a repair budget between 0 and 600 seconds")
    value = policy(config, seconds)
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "references.json", profile.qualify())
    base = baseline(out / "baseline", variant, jar)
    write_json(out / "policy.json", value)
    guard = base["guard"]
    result = repair(
        base["source"],
        base["scope"],
        Path(guard["plan"]),
        guard["plan_sha256"],
        out / "policy.json",
        digest((out / "policy.json").read_bytes()),
        out / "repair",
        jar,
    )
    write_json(out / "result.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--agent-config", type=Path, required=True)
    parser.add_argument("--oft-jar", type=Path, default=default_jar())
    parser.add_argument("--seconds", type=float, default=240)
    parser.add_argument("--variant", choices=("shallow-copy", "deep-copy"), default="shallow-copy")
    args = parser.parse_args()
    result = run(args.out, args.agent_config, args.oft_jar, args.seconds, args.variant)
    print(json.dumps({k: result[k] for k in ("status", "loop_status", "reason")}, indent=2))
    sys.exit({"passed": 0, "review_required": 4, "rejected": 1, "unresolved": 5}[result["status"]])
