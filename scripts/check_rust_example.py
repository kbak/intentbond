"""Qualify the packaged Rust example with pinned tools and an external readiness service."""

import argparse
import json
import os
import shutil
import socketserver
import subprocess
import threading
from pathlib import Path
from unittest.mock import patch

from intentbond.common import CheckError, read_json
from intentbond.oft import default_jar
from intentbond.runner import check, verify

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "rust-execution"


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
