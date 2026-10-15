"""Exercise a requirement change, review observations, resume, and repair in a new directory."""

import argparse
import shutil
import sys
from pathlib import Path

from intentbond import worklist
from intentbond.common import CheckError, read_json, write_json
from intentbond.impact import impact
from intentbond.oft import default_jar
from intentbond.runner import check
from intentbond.snapshot import git

REQ = "req~retry-cap~1"


def run(out, jar):
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    repo = out / "project"
    shutil.copytree(
        Path(__file__).resolve().parents[1] / "granular-retries",
        repo,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    scope = read_json(repo / "scope.json")
    scope.update(
        inputs=["requirements.md", "retry.py", "tests", "helpers"], review_paths=["retry.py"]
    )
    scope["tests"] = {
        "format": "junit",
        "command": [
            sys.executable,
            "-m",
            "intentbond.unittest_junit",
            "--start",
            "tests",
            "--report",
            "results.xml",
            "--links",
            "tests/oft-links.json",
        ],
        "report": "results.xml",
        "timeout_seconds": 30,
        "execution_links": {
            "format": "junit-properties-v1",
            "artifact_types": ["utest"],
            "required_artifacts": ["utest~retry-cap"],
        },
    }
    write_json(repo / "scope.json", scope)
    write_json(
        repo / "tests/oft-links.json",
        {
            "test_retry.RetryTests.test_growth": ["utest~retry-growth~1"],
            "test_retry.RetryTests.test_cap": ["utest~retry-cap~1"],
            "test_retry.RetryTests.test_small_delays": ["utest~retry-small-delays~1"],
        },
    )
    (repo / "helpers").mkdir()
    (repo / "helpers/notes.txt").write_text("Selected helper sources live here.\n")
    with (repo / "tests/test_retry.py").open("a") as stream:
        stream.write(
            "\n    # [utest~retry-small-delays~1->req~retry-cap~1]\n    def test_small_delays(self):\n        for delay in (0, 1, 2):\n            self.assertEqual(cap(delay), delay)\n"
        )
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", ".")
    git(
        repo,
        "-c",
        "user.name=Example",
        "-c",
        "user.email=example@example.invalid",
        "commit",
        "-qm",
        "Accepted retry promises and policy",
    )
    base = git(repo, "rev-parse", "HEAD").decode().strip()

    def checking(name, policy=None):
        return check(repo, policy, base, "worktree", out / name, jar)

    def replace(path, before, after):
        target = repo / path
        text = target.read_text()
        if before not in text:
            raise CheckError(f"Example input missing in {path}: {before}")
        target.write_text(text.replace(before, after))

    results = {"baseline": checking("baseline")["status"]}
    # Same editorial change: strict policy rejects a missing bump, permissive policy retains review.
    original = (repo / "requirements.md").read_text()
    replace("requirements.md", "Capping a nonnegative delay", "For a nonnegative delay, capping")
    results["strict_editorial"] = checking("strict-editorial")["status"]
    permissive = {**scope, "policy": {"require_revision_increase": False}}
    write_json(out / "permissive-policy.json", permissive)
    results["permissive_editorial"] = checking(
        "permissive-editorial", out / "permissive-policy.json"
    )["status"]
    (repo / "requirements.md").write_text(original)

    for path in ("requirements.md", "retry.py", "tests/test_retry.py"):
        replace(path, REQ, "req~retry-cap~2")
    replace("requirements.md", "and 8 seconds", "and 16 seconds")
    replace("retry.py", "min(delay, 8)", "min(delay, 16)")
    replace("tests/test_retry.py", "cap(100), 8", "cap(100), 16")
    with (repo / "helpers/new.py").open("w") as stream:
        stream.write("def describe(delay):\n    return str(delay)\n")
    replace(
        "tests/test_retry.py",
        "    def test_cap",
        "    @unittest.skip('boundary review pending')\n    def test_cap",
    )
    results["skipped_required_test"] = checking("changed")["status"]
    report = impact(out / "changed/evidence.json", jar)
    write_json(out / "observations.json", report)
    frozen = worklist.start(out / "changed/evidence.json", out / "worklist", repo, jar)
    first = frozen["current"]["id"]
    worklist.record(
        out / "worklist",
        first,
        "deferred",
        "Inspect the updated cap boundary and restore its execution",
    )
    results["resumed_progress"] = worklist.status(out / "worklist")["counts"]

    replace("tests/test_retry.py", "    @unittest.skip('boundary review pending')\n", "")
    replace(
        "tests/test_retry.py",
        "self.assertEqual(cap(8), 8)",
        "self.assertEqual(cap(8), 8)\n        self.assertEqual(cap(16), 16)",
    )
    try:
        worklist.status(out / "worklist")
    except CheckError:
        results["old_progress_after_repair"] = "refused"
    else:
        raise CheckError("Changed source unexpectedly reused old review progress")
    results["repaired"] = checking("repaired")["status"]
    fresh = worklist.start(out / "repaired/evidence.json", out / "fresh-worklist", repo, jar)
    results["fresh_progress"] = fresh["counts"]
    expected = {
        "baseline": "passed",
        "strict_editorial": "rejected",
        "permissive_editorial": "review_required",
        "skipped_required_test": "rejected",
        "repaired": "review_required",
    }
    if any(results[name] != value for name, value in expected.items()):
        raise CheckError(f"Unexpected example outcomes: {results}")
    write_json(out / "results.json", results)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, required=True, help="New directory outside your checkout"
    )
    parser.add_argument("--oft-jar", type=Path, default=default_jar())
    args = parser.parse_args()
    run(args.out, args.oft_jar)
    print(args.out.resolve() / "results.json")
