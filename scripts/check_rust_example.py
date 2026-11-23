"""Qualify the packaged Rust example with pinned tools and an external readiness service."""

import argparse
import json
import os
import shutil
import socketserver
import subprocess
import threading
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from intentbond.check_output import render_check
from intentbond.common import CheckError, read_json
from intentbond.oft import default_jar
from intentbond.runner import check, verify

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "rust-execution"


# [utest->req~ib-cargo-evidence~1]
# [utest->req~ib-report-merge~1]
def qualify_early_failure(repo, base, out):
    source = repo / "src/lib.rs"
    driver = repo / "run.py"
    original_source, original_driver = source.read_text(), driver.read_text()
    try:
        source.write_text(original_source.replace("Some(2)", 'Some(3), "retained cargo failure"'))
        driver.write_text(
            original_driver.replace(
                "results = [subprocess.run(command).returncode for command in commands]",
                "results = []\nfor command in commands:\n"
                "    code = subprocess.run(command).returncode\n"
                "    if code: sys.exit(code)\n    results.append(code)",
            )
        )
        evidence = out / "early-cargo-failure"
        result = check(repo, None, base, "worktree", evidence, default_jar())
        assert result["status"] == "rejected", result
        assert result["tests"]["exit_code"] != 0
        assert result["tests"]["reports"] == [{"source": "ordinary.xml", "artifact": "tests-1.xml"}]
        assert "retained cargo failure" in (evidence / "tests.log").read_text()
        assert "retained cargo failure" in (evidence / "tests-1.xml").read_text()
        assert not (evidence / "tests.xml").exists()
        assert not (evidence / "verus-3.json").exists()
        text = render_check(result, evidence)
        assert "retained cargo failure" in text, text
        assert "proofs.xml.verus.json" in text, text
        assert "counts" not in result["tests"]
        print("early Cargo failure: output retained; missing downstream reports reject", flush=True)
    finally:
        source.write_text(original_source)
        driver.write_text(original_driver)


# [utest->req~ib-cargo-build-reuse~1]
# [utest->req~ib-cargo-doctests~1]
def qualify_reuse(repo, base, out):
    policy = read_json(repo / ".intentbond/scope.json")
    tests = policy["tests"]
    tests["cargo_build"] = {"doctests": True}
    tests["reports"].append("second-service.xml")
    scope = out / "reuse-scope.json"
    scope.write_text(json.dumps(policy))
    driver = repo / "run.py"
    original = driver.read_text()
    source = repo / "src/lib.rs"
    original_source = source.read_text()
    source.write_text(
        "//! ```rust\n//! assert_eq!(1_i32.checked_add(1), Some(2));\n//! ```\n" + original_source
    )
    counter = out / "compilations"
    (repo / "build.rs").write_text(
        "fn main() { use std::io::Write; let mut f = std::fs::OpenOptions::new()"
        '.append(true).create(true).open(std::env::var("BUILD_COUNTER").unwrap()).unwrap();'
        'writeln!(f, "compiled").unwrap(); }\n'
    )
    driver_with_reuse = original.replace(
        '"intentbond.cargo_junit",', '"intentbond.cargo_junit", "--use-captured-build",'
    )
    repeat = 'commands.append([*cargo, "--report", "second-service.xml", "--ignored", *service])'
    driver.write_text(driver_with_reuse.replace("results = ", repeat + "\nresults = "))
    evidence = out / "captured-build"
    try:
        with patch.dict(os.environ, {"BUILD_COUNTER": str(counter)}):
            passing = out / "captured-build-passing"
            result = check(repo, scope, base, "worktree", passing, default_jar())
            assert result["status"] == "review_required", result
            verify(
                repo, scope, base, "worktree", passing / "evidence.json", allow_pending_review=True
            )
            assert counter.read_text().splitlines() == ["compiled"]
            assert result["tests"]["cargo_build"]["doctests"]["status"] == "passed"
            log = passing / "cargo-doctests.log"
            raw = log.read_bytes()
            assert b"1 passed" in raw
            for altered in (False, True):
                if altered:
                    log.write_bytes(raw + b"changed")
                else:
                    log.unlink()
                try:
                    verify(
                        repo,
                        scope,
                        base,
                        "worktree",
                        passing / "evidence.json",
                        allow_pending_review=True,
                    )
                except (CheckError, FileNotFoundError):
                    pass
                else:
                    raise AssertionError("Verifier accepted missing or altered doctest output")
                finally:
                    log.write_bytes(raw)
            # Change only the runtime fixture for the repeated execution.
            driver.write_text(
                driver.read_text().replace(
                    "commands.append([*cargo",
                    'commands.append(["env", "EXAMPLE_READY_ADDR=invalid", *cargo',
                )
            )
            result = check(repo, scope, base, "worktree", evidence, default_jar())
        assert result["status"] == "rejected", result
        assert counter.read_text().splitlines() == ["compiled", "compiled"]
        suites = [ET.parse(evidence / f"tests-{i}.xml").getroot() for i in (1, 2, 4)]
        archives = [
            s.find("properties/property[@name='build_archive_sha256']").get("value") for s in suites
        ]
        assert len(set(archives)) == 1
        for suite in suites:
            assert (
                suite.find("properties/property[@name='build_candidate_sha256']").get("value")
                == result["candidate"]["sha256"]
            )
        first = suites[1].find("testcase")
        second = suites[2].find("testcase")
        assert first.get("name") == second.get("name") == "tests::round_trip"
        assert first.find("failure") is None and second.find("failure") is not None
        print(
            "captured build: one compilation including fresh doctests; separate fixture observations",
            flush=True,
        )
        source.write_text(
            source.read_text().replace(
                "//! assert_eq!(1_i32.checked_add(1), Some(2));",
                "//! assert_eq!(1_i32.checked_add(1), Some(3));",
            )
        )
        with patch.dict(os.environ, {"BUILD_COUNTER": str(counter)}):
            failed = out / "captured-doctest-failure"
            result = check(repo, scope, base, "worktree", failed, default_jar())
        assert result["status"] == "rejected", result
        assert result["tests"]["cargo_build"]["doctests"]["status"] == "failed"
        assert counter.read_text().splitlines() == ["compiled"] * 3
        assert not (failed / "tests-1.xml").exists()
        print("captured doctests: failure rejects the check before fixture execution", flush=True)
    finally:
        driver.write_text(original)
        source.write_text(original_source)
        (repo / "build.rs").unlink()


class Readiness(socketserver.StreamRequestHandler):
    def handle(self):
        self.wfile.write(b"ready\n")


def qualify(out):
    out.mkdir(parents=True, exist_ok=False)
    repo = out / "project"
    shutil.copytree(EXAMPLE, repo)
    git = ["git", "-C", str(repo)]
    subprocess.run([*git, "init", "-qb", "main"], check=True)
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run(
        [
            *git,
            "-c",
            "user.name=Example",
            "-c",
            "user.email=example@example.invalid",
            "commit",
            "-qm",
            "Accepted example",
        ],
        check=True,
    )
    base = subprocess.check_output([*git, "rev-parse", "HEAD"], text=True).strip()

    def run(label, expected):
        evidence = out / label
        result = check(repo, None, base, "worktree", evidence, default_jar())
        if result["status"] != expected:
            raise RuntimeError(
                f"{label}: {result['status']} {result['diagnostics']} {result['tests']}"
            )
        print(f"{label}: {expected}", flush=True)
        return {item["id"]: item for item in result["tests"]["execution_links"]["artifacts"]}

    def edit(name, old, new):
        path = repo / name
        source = path.read_text()
        assert source.count(old) == 1
        path.write_text(source.replace(old, new))

    with socketserver.TCPServer(("127.0.0.1", 0), Readiness) as service:
        threading.Thread(target=service.serve_forever, daemon=True).start()
        addr = f"127.0.0.1:{service.server_address[1]}"
        with patch.dict(os.environ, {"EXAMPLE_READY_ADDR": addr}):
            links = run("passing", "passed")
            assert len(links) == 3 and all(item["status"] == "passed" for item in links.values())
            evidence = out / "passing" / "evidence.json"
            verify(repo, None, base, "worktree", evidence)
            explanation = subprocess.check_output(
                [
                    "ib",
                    "explain",
                    "proof~increment~1",
                    "--format",
                    "json",
                    "--evidence",
                    str(evidence),
                ],
                text=True,
            )
            assert json.loads(explanation)["linked_test_execution"] == "passed"
            qualify_early_failure(repo, base, out)
            qualify_reuse(repo, base, out)

            native = out / "passing" / "verus-3.json"
            raw = native.read_bytes()
            for altered in (False, True):
                if altered:
                    native.write_bytes(raw + b"\n")
                else:
                    native.unlink()
                try:
                    verify(repo, None, base, "worktree", evidence)
                except (CheckError, FileNotFoundError):
                    pass
                else:
                    raise AssertionError("Verifier accepted missing or altered native bytes")
                finally:
                    native.write_bytes(raw)

            proof = "proofs/arithmetic.rs"
            edit(proof, "n + 1 > n", "n + 1 == n")
            assert run("failed-proof", "rejected")["proof~increment~1"]["status"] == "failed"
            edit(proof, "n + 1 == n", "n + 1 > n")
            edit(proof, "pub proof fn increment", "#[cfg(any())]\n    pub proof fn increment")
            assert run("absent-proof", "rejected")["proof~increment~1"]["status"] == "not_observed"
            edit(proof, "#[cfg(any())]\n    pub proof fn increment", "pub proof fn increment")

            edit("run.py", ', "--exclude", *service', "")
            mixed = run("conflicting-runs", "rejected")["utest~service~1"]
            assert sorted(case["status"] for case in mixed["cases"]) == ["passed", "skipped"]
            edit("run.py", '"ordinary.xml"]', '"ordinary.xml", "--exclude", *service]')

            edit("run.py", '"--ignored", *service', '"--ignored", service[0], "misspelled"')
            assert run("zero-match", "rejected")["utest~service~1"]["status"] == "not_observed"
            edit("run.py", '"--ignored", service[0], "misspelled"', '"--ignored", *service')

            edit(
                "tests/service.rs",
                "let address =",
                'compile_error!("broken test target"); let address =',
            )
            assert run("build-error", "rejected")["utest~service~1"]["status"] == "not_observed"
            edit(
                "tests/service.rs",
                'compile_error!("broken test target"); let address =',
                "let address =",
            )
            edit("tests/service.rs", "let address =", "std::process::abort(); let address =")
            assert run("crashed-test", "rejected")["utest~service~1"]["status"] == "failed"
            edit("tests/service.rs", "std::process::abort(); let address =", "let address =")

            edit(proof, "// [proof~increment~1", "// removed [proof~unused~1")
            scope = repo / ".intentbond/scope.json"
            policy = read_json(scope)
            policy["tests"]["execution_links"]["required_artifacts"].remove("proof~increment")
            scope.write_text(json.dumps(policy))
            assert "proof~increment~1" not in run("removed-required", "rejected")
        service.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    qualify(parser.parse_args().out.resolve())
