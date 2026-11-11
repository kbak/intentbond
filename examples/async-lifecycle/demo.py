"""Qualify the opt-in form lifecycle example without network or model calls."""

import argparse
import ast
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import contract
import lifecycle
from qualification import canonical, qualify
from runtime import ROOT, identity, observe

from intentbond.change_guard import prepare
from intentbond.common import CheckError, digest, read_json, write_json
from intentbond.oft import default_jar
from intentbond.repair import outside_symbol, repair
from intentbond.runner import check, verify

REGRESSION = {
    "test_path": "tests/test_async_lifecycle.py",
    "data_path": "tests/async_lifecycle_cases.json",
    "links_path": "tests/links.json",
    "checks": [contract.CHECK],
}
CONTROLS = (
    "original",
    "unique-token",
    "repair",
    "alternative",
    "signature",
    "protected",
    "old-test",
    "requirement",
    "no-progress",
    "conflict",
    "unavailable",
    "observation-unavailable",
)
RESET = "            # Reuse small counters once the latest response has completed.\n            self.serial = 0\n"


def git(repo, *args):
    return subprocess.check_output(
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "init.templateDir=",
            "-C",
            str(repo),
            *args,
        ],
        text=True,
    ).strip()


def native(source, scope, base, out, jar):
    result = check(source, scope, base, "worktree", out, jar)
    verification = None
    if result["status"] in ("passed", "review_required"):
        verification = verify(source, scope, base, "worktree", out / "evidence.json", True)
        assert verification["status"] == "matched"
    return {
        "status": result["status"],
        "tests": result["tests"]["counts"],
        "execution": result["tests"]["execution_links"],
        "verification": verification,
    }


def baseline(out, variant, jar):
    out.mkdir(parents=True)
    source = out / "source"
    shutil.copytree(ROOT / "fixture", source, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    controller = source / "client/controller.py"
    if variant != "original":
        controller.write_text(controller.read_text() + RESET)
        if variant == "unique-token":
            controller.write_text(
                lifecycle.proposal(source, "alternative")["files"]["client/controller.py"]
            )
    scope = read_json(source / "scope.json")
    scope["tests"]["command"] = [sys.executable, "-B", "run_tests.py"]
    write_json(source / "scope.json", scope)
    write_json(out / "scope.json", scope)
    git(source, "init", "-q", "-b", "main")
    git(source, "add", ".")
    git(
        source,
        "-c",
        "user.name=Offline example",
        "-c",
        "user.email=example@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-qm",
        "Accepted fixture requirements and retained checks",
    )
    base = git(source, "rev-parse", "HEAD")
    # Ordinary check/verify must neither generate cases nor invoke repair.
    before = identity(source)
    with patch("intentbond.repair.repair", side_effect=AssertionError("default invoked repair")):
        result = native(source, out / "scope.json", base, out / "native", jar)
    assert result["status"] == "passed" and identity(source) == before
    assert not (source / REGRESSION["test_path"]).exists()
    checks = sorted(
        {ref for refs in read_json(source / "tests/links.json").values() for ref in refs}
    )
    assert len(checks) == 5
    declaration = {
        "schema_version": 1,
        "requirements": {
            "preserve": sorted(contract.REQUIREMENTS),
            "add": [],
            "change": [],
            "remove": [],
        },
        "protected_paths": [
            "client/component.py",
            "client/labels.py",
            "schema.py",
            "server.py",
            "entrypoint.py",
        ],
        "checks": checks,
        "check_support_paths": ["run_tests.py", "tests/repair_cases.json"],
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
        "native": result,
    }


def retain(source, cases):
    (source / REGRESSION["test_path"]).write_text(lifecycle.scaffold(REGRESSION))
    write_json(source / REGRESSION["data_path"], cases)
    links = read_json(source / REGRESSION["links_path"])
    links["test_async_lifecycle.Lifecycle.test_events"] = [contract.CHECK]
    write_json(source / REGRESSION["links_path"], links)


def boundary_evidence(before, after, control, cases):
    old, new = identity(before), identity(after)
    changed = sorted(p for p in old.keys() | new.keys() if old.get(p) != new.get(p))
    wanted = [REGRESSION[k] for k in ("test_path", "data_path", "links_path")]
    if control in ("repair", "alternative"):
        wanted.append("client/controller.py")
    assert changed == sorted(wanted), changed
    first, second = [(p / "client/controller.py").read_text() for p in (before, after)]
    assert outside_symbol(first, "Form.validate") == outside_symbol(second, "Form.validate")
    header = "    async def validate(self, value, request):\n"
    assert first.split(header)[0] == second.split(header)[0]

    def without_body(text):
        tree = ast.parse(text)
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Form")
        method = next(
            n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "validate"
        )
        method.body = [ast.Pass()]
        return ast.dump(tree, include_attributes=False)

    assert without_body(first) == without_body(second)
    links = read_json(after / REGRESSION["links_path"])
    oldlinks = read_json(before / REGRESSION["links_path"])
    assert {k: v for k, v in links.items() if k in oldlinks} == oldlinks and len(links) == len(
        oldlinks
    ) + 1
    assert read_json(after / REGRESSION["data_path"]) == cases
    assert (after / REGRESSION["test_path"]).read_text() == lifecycle.scaffold(REGRESSION)
    return {
        "changed_paths": changed,
        "outside_body_unchanged": True,
        "old_cases_and_checks_unchanged": True,
    }


def run(out, jar):
    if not __debug__:
        raise CheckError("Qualification assertions require Python without -O")
    out = out.resolve()
    if out.is_relative_to(ROOT.parents[1]):
        raise CheckError("Use a new output directory outside the source checkout")
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    references = qualify()
    write_json(out / "references.json", references)
    pins = {
        str(p): digest(p.read_bytes())
        for p in sorted(ROOT.rglob("*"))
        if p.is_file() and p.suffix in (".py", ".json", ".md") and "__pycache__" not in p.parts
    }
    write_json(out / "inputs.json", pins)
    cases = lifecycle.generate("initial") + lifecycle.generate("adversarial")
    baselines = {
        v: baseline(out / "baselines" / v, v, jar)
        for v in ("original", "counter-reset", "unique-token")
    }
    ordinary = []
    for variant, base in baselines.items():
        folder = out / "ordinary-plus-retention" / variant
        source = folder / "source"
        shutil.copytree(base["source"], source)
        retain(source, cases)
        result = native(source, base["scope"], base["base"], folder / "native", jar)
        assert (result["status"] in ("passed", "review_required")) == (variant != "counter-reset")
        observed = observe(source, cases, folder / "observed")
        failed = [
            c["id"]
            for c, o in zip(cases, observed)
            if o["status"] != "returned" or canonical(o["value"]) not in c["accepted"]
        ]
        assert len(failed) == (10 if variant == "counter-reset" else 0), failed
        ordinary.append({"variant": variant, "native": result, "failed_ids": failed})
        write_json(folder / "result.json", ordinary[-1])
    results = []
    for control in CONTROLS:
        base = baselines[control if control in ("original", "unique-token") else "counter-reset"]
        folder = out / "api" / control
        folder.mkdir(parents=True)
        policy = {
            "schema_version": 1,
            "requirements": contract.REQUIREMENTS,
            "edits": [
                {
                    "path": "client/controller.py",
                    "symbol": "Form.validate",
                    "requirements": [contract.ASYNC],
                }
            ],
            "adapter": {
                "command": [sys.executable, "-B", str(ROOT / "adapter.py"), control],
                "inputs": pins,
            },
            "regression": REGRESSION,
            "limits": {"seconds": 60, "repairs": 2, "cases": 1000},
        }
        write_json(folder / "policy.json", policy)
        guard = base["guard"]
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
        good = control in ("original", "unique-token", "repair", "alternative")
        unresolved = control in ("conflict", "unavailable", "observation-unavailable")
        wanted = "passed" if good else "unresolved" if unresolved else "rejected"
        row = {
            "control": control,
            **{
                k: result.get(k)
                for k in (
                    "status",
                    "loop_status",
                    "reason",
                    "cases",
                    "repairs",
                    "original_unchanged",
                    "elapsed_seconds",
                )
            },
        }
        write_json(folder / "qualification.json", row)
        assert result["loop_status"] == wanted and result["original_unchanged"], result
        if good:
            assert (
                result["status"] == "review_required"
                and result["verification"]["status"] == "matched"
            )
            assert result["cases"] == 136 and result["adversarial_passes"] == 1
            assert result["repairs"] == (1 if control in ("repair", "alternative") else 0)
            assert all(s == "passed" for s in result["regression_execution"].values())
            assert all(c["status"] == "passed" for c in result["native"]["guard"]["checks"])
            row["boundary"] = boundary_evidence(
                base["source"], folder / "repair/frozen", control, cases
            )
            if control in ("repair", "alternative"):
                failed = read_json(folder / "repair/failures-0-0.json")
                assert [r["case"]["id"] for r in failed] == [
                    "d10-interleaved-latest-valid",
                    "d10-interleaved-latest-invalid",
                ]
                evidence = read_json(folder / "repair/cycle-0-evidence/evidence.json")["predicate"]
                statuses = {
                    a["id"]: a["status"] for a in evidence["tests"]["execution_links"]["artifacts"]
                }
                assert statuses.pop(contract.CHECK) == "failed" and set(statuses.values()) == {
                    "passed"
                }
        elif control in ("signature", "protected", "old-test", "requirement"):
            assert result["reason"] == "repair_scope_violation" and result["repairs"] == 0
        elif control == "no-progress":
            assert result["reason"] == "repair_budget_exhausted" and result["repairs"] == 2
        else:
            assert result["reason"] == (
                "unresolved_observation"
                if control == "observation-unavailable"
                else "unresolved_reference_label"
            )
        write_json(folder / "qualification.json", row)
        results.append(row)
        print(control, result["loop_status"], result["reason"], flush=True)
    for name, sha in pins.items():
        assert digest(Path(name).read_bytes()) == sha, name
    summary = {
        "qualified": True,
        "references": references,
        "ordinary_plus_retention": ordinary,
        "api": results,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "model_calls": 0,
        "default_behavior_unchanged": True,
        "network_required": False,
        "limit": "Finite fixture qualification; semantic review remains pending. OS isolation is external.",
    }
    write_json(out / "results.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="New evidence directory outside the checkout")
    parser.add_argument("--oft-jar", type=Path, default=default_jar())
    parser.add_argument(
        "--references-only",
        action="store_true",
        help="Check retained labels and generators without executing candidates",
    )
    args = parser.parse_args()
    if not __debug__:
        parser.error("Qualification requires Python without -O")
    if args.references_only:
        print(json.dumps(qualify(), indent=2))
    elif args.out:
        run(args.out, args.oft_jar)
        print(args.out.resolve() / "results.json")
    else:
        parser.error("--out is required unless --references-only is selected")
