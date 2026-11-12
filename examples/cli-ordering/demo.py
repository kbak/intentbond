"""Qualify CLI ordering offline with scripted actors and the real shared bridge."""

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import agent_demo
import ordering_profile as profile
from agent_adapter import bridge

from intentbond.common import CheckError, digest, read_json, write_json
from intentbond.oft import default_jar
from intentbond.repair import Session, outside_symbol, repair

CONTROLS = (
    "repair",
    "alternative",
    "two-round",
    "stable",
    "pretty-json",
    "protected",
    "old-test",
    "requirement",
    "unrelated",
    "signature",
    "path-escape",
    "drop-duplicates",
    "reject-duplicates",
    "quantities",
    "json-blank-line",
    "no-progress",
    "partial",
    "stale",
    "unknown",
    "conflict",
    "missing-label",
    "incomplete-observation",
)
GOOD = {"repair", "alternative", "two-round", "stable", "pretty-json"}
UNKNOWN = {"partial", "stale", "unknown", "conflict", "missing-label", "incomplete-observation"}


def injected_adapter(control):
    original = Session.adapter

    def call(session, phase, **payload):
        result = original(session, phase, **payload)
        # Deliberately malformed trusted-adapter responses. No file escapes occur.
        if phase == "generate" and control in ("conflict", "missing-label"):
            result["cases"][0]["label"]["status"] = (
                "conflict" if control == "conflict" else "unavailable"
            )
        elif phase == "observe" and control == "incomplete-observation":
            result["observations"].pop()
        elif phase == "propose" and control == "path-escape":
            result["proposal"]["files"]["../escape.py"] = "unwanted = True\n"
        return result

    return call


def boundary(before, after, cases, control):
    old, new = [bridge.inventory(p, "test-results.xml") for p in (before, after)]
    changed = sorted(p for p in old.keys() | new.keys() if old.get(p) != new.get(p))
    wanted = [profile.REGRESSION[k] for k in ("test_path", "data_path", "links_path")]
    if control != "stable":
        wanted.append("formatters.py")
    assert changed == sorted(wanted), changed
    first, second = [(p / "formatters.py").read_text() for p in (before, after)]
    assert outside_symbol(first, "ordered") == outside_symbol(second, "ordered")
    oldlinks, newlinks = [read_json(p / profile.REGRESSION["links_path"]) for p in (before, after)]
    assert newlinks == {**oldlinks, **profile.LINKS}
    assert read_json(after / profile.REGRESSION["data_path"]) == cases
    assert (after / profile.REGRESSION["test_path"]).read_text() == profile.scaffold(
        profile.REGRESSION
    )
    return {"changed_paths": changed, "outside_body_unchanged": True, "all_cases_retained": True}


def run(out, jar):
    if not __debug__:
        raise CheckError("Qualification requires Python without -O")
    out = out.resolve()
    if out.is_relative_to(profile.ROOT.parents[1]):
        raise CheckError("Use a new output directory outside the source checkout")
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    refs = profile.qualify()
    write_json(out / "references.json", refs)
    cases = profile.generate("initial") + profile.generate("adversarial")
    baselines = {
        v: agent_demo.baseline(out / "baselines" / v, v, jar)
        for v in ("tie-breaker", "stable", "pretty-json")
    }
    actor = profile.ROOT / "demo_actor.py"
    results = []
    for control in CONTROLS:
        folder = out / control
        folder.mkdir()
        config = out / (control + "-agent.json")
        write_json(
            config,
            {
                "command": [sys.executable, "-B", str(actor), control],
                "inputs": {str(actor): digest(actor.read_bytes())},
                "seconds": 30,
            },
        )
        value = agent_demo.policy(config, 120)
        write_json(folder / "policy.json", value)
        base = baselines[control if control in ("stable", "pretty-json") else "tie-breaker"]
        guard = base["guard"]
        write_json(
            folder / "control.json",
            {
                "control": control,
                "response_injection": control
                in ("conflict", "missing-label", "incomplete-observation", "path-escape"),
            },
        )
        with patch.object(Session, "adapter", injected_adapter(control)):
            result = repair(
                base["source"],
                base["scope"],
                Path(guard["plan"]),
                guard["plan_sha256"],
                folder / "policy.json",
                digest((folder / "policy.json").read_bytes()),
                folder / "repair",
                jar,
            )
        write_json(folder / "result.json", result)
        wanted = "passed" if control in GOOD else "unresolved" if control in UNKNOWN else "rejected"
        assert result["loop_status"] == wanted and result["original_unchanged"], result
        if control in ("drop-duplicates", "reject-duplicates", "json-blank-line", "no-progress"):
            assert result["reason"] == "repair_budget_exhausted" and result["repairs"] == 2
            assert read_json(folder / "repair/failures-1-0.json")
        elif control == "quantities":
            assert result["reason"] == "preservation_failed"
        row = {
            "control": control,
            **{
                k: result[k]
                for k in (
                    "status",
                    "loop_status",
                    "reason",
                    "cases",
                    "repairs",
                    "elapsed_seconds",
                )
            },
        }
        if control in GOOD:
            assert result["status"] == "review_required"
            assert result["verification"]["status"] == "matched"
            assert result["cases"] == 280 and result["adversarial_passes"] == 1
            assert result["repairs"] == (
                0 if control == "stable" else 2 if control == "two-round" else 1
            )
            assert all(s == "passed" for s in result["regression_execution"].values())
            assert all(c["status"] == "passed" for c in result["native"]["guard"]["checks"])
            row["boundary"] = boundary(base["source"], folder / "repair/frozen", cases, control)
            if control != "stable":
                failed = read_json(folder / "repair/failures-0-0.json")
                assert len(failed) == 6
                row["initial_failed_ids"] = [f["case"]["id"] for f in failed]
            if control == "two-round":
                failed = read_json(folder / "repair/failures-1-1.json")
                assert len(failed) == 51
                row["second_round_failed_ids"] = [f["case"]["id"] for f in failed]
            requests = [
                read_json(p)
                for p in sorted((folder / "repair").glob("adapter-*-propose/agent/request.json"))
            ]
            assert [q["round"] for q in requests] == list(range(1, result["repairs"] + 1))
            assert all(0 < q["remaining_seconds"] <= 30 for q in requests)
            assert len({q["source_sha256"] for q in requests}) == len(requests)
            deadlines = [
                read_json(p)["remaining_seconds"]
                for p in sorted((folder / "repair").glob("adapter-*/request.json"))
            ]
            assert all(a > b for a, b in zip(deadlines, deadlines[1:]))
        for name, sha in value["adapter"]["inputs"].items():
            assert digest(Path(name).read_bytes()) == sha
        write_json(folder / "qualification.json", row)
        results.append(row)
        print(control, result["loop_status"], result["reason"], flush=True)
    # Reintroducing the original tie breaker must fail the new ordinary tests.
    source = out / "reintroduced"
    shutil.copytree(out / "repair/repair/frozen", source)
    shutil.copyfile(baselines["tie-breaker"]["source"] / "formatters.py", source / "formatters.py")
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_cli_ordering_regression.py",
        ],
        cwd=source,
        capture_output=True,
        text=True,
        timeout=20,
    )
    (out / "reintroduced.log").write_text(result.stdout + result.stderr)
    assert result.returncode != 0 and "initial-009" in result.stderr
    summary = {
        "qualified": True,
        "references": refs,
        "controls": results,
        "reintroduced_regression_caught": True,
        "default_behavior_unchanged": True,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "model_calls": 0,
        "network_required": False,
        "limit": "Finite fixture qualification; semantic review remains pending. OS isolation is external.",
    }
    write_json(out / "results.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--oft-jar", type=Path, default=default_jar())
    parser.add_argument("--references-only", action="store_true")
    args = parser.parse_args()
    if not __debug__:
        parser.error("Qualification requires Python without -O")
    if args.references_only:
        print(json.dumps(profile.qualify(), indent=2))
    elif args.out:
        run(args.out, args.oft_jar)
        print(args.out.resolve() / "results.json")
    else:
        parser.error("--out is required unless --references-only is selected")
