import contextlib
import json
import os
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from intentbond import cargo_build, cargo_junit, verus_junit
from intentbond.common import CheckError
from intentbond.config import validate_scope
from intentbond.execution import collect_execution_links
from intentbond.rust_junit import bindings
from intentbond.snapshot import Snapshot, put_file
from intentbond.testing import execute_tests


class RustProducers(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.enterContext(contextlib.chdir(directory.name))
        self.rows = [{"function": "demo::proof", "success": True}]
        self.report = {
            "verus": {"version": verus_junit.VERSION, "toolchain": "1.99.1"},
            "verification-results": {
                "success": True,
                "encountered-error": False,
                "encountered-vir-error": False,
                "verified": 1,
                "errors": 0,
                "is-verifying-entire-crate": True,
            },
            "times-ms": {"smt": {"smt-run-module-times": [{"function-breakdown": self.rows}]}},
        }
        self.source = Path("checks.rs")
        self.source.write_text("// [proof~named~2->req~demo~1] ib-verus demo::proof\n")

    def verus(self, raw, exit_code=0):
        def verifier(command, stdout):
            stdout.write(raw)
            return subprocess.CompletedProcess(command, exit_code)

        with patch.object(subprocess, "run", side_effect=verifier):
            return verus_junit.main(["--source", "checks.rs", "--report", "proof.xml"])

    # [utest->req~ib-verus-evidence~1]
    def test_raw_retention_exact_revision_and_wrong_revision_rejected(self):
        raw = json.dumps(self.report, indent=3).encode()
        self.assertEqual(self.verus(raw), 0)
        self.assertEqual(Path("proof.xml.verus.json").read_bytes(), raw)
        path = Path("proof.xml")
        verus_junit.validate_retained(path, raw)
        declarations = [{"id": "proof~named~1", "type": "proof", "path": "checks.rs"}]
        scope = {
            "tests": {"execution_links": {"artifact_types": ["proof"]}},
            "test_paths": ["checks.rs"],
        }
        self.assertEqual(collect_execution_links(path, declarations, scope)["status"], "invalid")
        xml = path.read_bytes()
        path.write_bytes(xml.replace(b'name="demo::proof"', b'name="demo::another"'))
        with self.assertRaisesRegex(CheckError, "differ"):
            verus_junit.validate_retained(path, raw)
        self.assertEqual(self.verus(b"replacement"), 1)
        path.unlink()
        self.assertEqual(self.verus(b"replacement"), 1)
        self.assertEqual(Path("proof.xml.verus.json").read_bytes(), raw)

    def test_failed_process_and_malformed_reports(self):
        raw = json.dumps(self.report).encode()
        self.assertEqual(self.verus(raw, -15), 1)
        tree = ET.parse("proof.xml")
        self.assertIsNotNone(tree.find("error"))
        self.assertEqual(tree.find("testcase").get("name"), "demo::proof")
        with self.assertRaises(CheckError):
            verus_junit.validate_retained(Path("proof.xml"), raw)
        for malformed in (b"{", b'{"x":0,"x":1}', b'{"verification-results":{"success":true}}'):
            with self.subTest(raw=malformed):
                Path("proof.xml").unlink()
                Path("proof.xml.verus.json").unlink()
                self.assertEqual(self.verus(malformed), 1)
                self.assertEqual(Path("proof.xml.verus.json").read_bytes(), malformed)
                self.assertIsNone(ET.parse("proof.xml").find("testcase"))

    def test_duplicate_non_boolean_and_absent_function(self):
        self.rows.append(self.rows[0])
        with self.assertRaisesRegex(CheckError, "duplicate"):
            verus_junit.observations(json.dumps(self.report))
        self.rows.pop()
        self.rows[0]["success"] = 1
        with self.assertRaisesRegex(CheckError, "Invalid"):
            verus_junit.observations(json.dumps(self.report))
        self.rows.clear()
        functions, passing = verus_junit.observations(json.dumps(self.report))
        self.assertEqual(functions, {})
        self.assertFalse(passing)

    # [utest->req~ib-cargo-evidence~1]
    def test_cargo_duplicate_ambiguous_and_interrupted_reports(self):
        a, b = ("pkg", "same"), ("pkg::other", "same")
        info = {"package-name": "pkg", "binary-name": "target", "kind": "test"}
        inventory = {a: (False, info), b: (False, info)}
        path = Path("native.xml")
        case = '<testcase classname="pkg" name="same"/>'
        for xml, message in (
            (case, "Incomplete"),
            (case + case, "duplicate"),
            (case.replace("/>", "><flakyFailure/></testcase>"), "Ambiguous"),
            (case.replace("/>", "><failure/><error/></testcase>"), "Ambiguous"),
        ):
            path.write_text(f'<testsuites><testsuite name="pkg">{xml}</testsuite></testsuites>')
            with self.subTest(xml=xml), self.assertRaisesRegex(CheckError, message):
                cargo_junit.reconcile(ET.Element("testsuite"), path, inventory, {a, b}, set(), {})

    def test_exact_ignored_selection_and_duplicate_bindings(self):
        a, b = ("pkg", "same"), ("pkg::other", "same")
        cases = {a: (False, {}), b: (True, {})}
        self.assertEqual(cargo_junit.selection(cases, [b], []), ({b}, set()))
        self.assertEqual(cargo_junit.selection(cases, [], [b]), ({a}, set()))
        for invalid in ([a], [b, b], [("pkg::missing", "same")]):
            with self.subTest(selection=invalid), self.assertRaises(CheckError):
                cargo_junit.selection(cases, invalid, [])
        self.source.write_text(self.source.read_text() * 2)
        with self.assertRaisesRegex(CheckError, "duplicate"):
            bindings(["checks.rs"], "verus")

    def test_cargo_failure_and_report_freshness(self):
        with patch.object(cargo_junit, "run_nextest", side_effect=OSError("interrupted")):
            self.assertEqual(cargo_junit.main(["--report", "cargo.xml"]), 1)
        self.assertIsNotNone(ET.parse("cargo.xml").find("error"))
        before = Path("cargo.xml").read_bytes()
        with patch.object(cargo_junit, "run_nextest") as runner:
            self.assertEqual(cargo_junit.main(["--report", "cargo.xml"]), 1)
            runner.assert_not_called()
        self.assertEqual(before, Path("cargo.xml").read_bytes())

    # [utest->req~ib-cargo-build-reuse~1]
    def test_archive_is_private_source_bound_and_discarded_after_the_command(self):
        root = Path.cwd() / "candidate"
        root.mkdir()
        snap = Snapshot(root, "commit", "commit", [put_file(root, "lib.rs", "100644", b"v1")])
        config = {
            "cargo_build": {"packages": ["demo"], "features": "db"},
            "command": ["driver"],
            "timeout_seconds": 30,
        }
        env = dict(os.environ)
        tools = {"cargo": "cargo version", "rustc": "rustc version", "nextest": "nextest version"}
        used = []

        def run(command, cwd, log, timeout, env):
            if command != config["command"]:
                archive = Path(command[command.index("--archive-file") + 1])
                self.assertFalse(archive.exists())
                self.assertEqual(command[command.index("--package") + 1], "demo")
                self.assertEqual(command[command.index("--features") + 1], "db")
                self.assertTrue(Path(env["CARGO_BUILD_BUILD_DIR"]).is_relative_to(archive.parent))
                Path(env["CARGO_BUILD_BUILD_DIR"]).mkdir()
                archive.write_bytes(b"compiled binaries")
                used.append(archive)
            else:
                with contextlib.chdir(root), patch.dict(os.environ, env, clear=True):
                    scratch = Path(self.enterContext(tempfile.TemporaryDirectory()))
                    copied, binding = cargo_build.captured_archive(scratch, tools)
                    self.assertEqual(copied.read_bytes(), used[-1].read_bytes())
                    self.assertEqual(binding["candidate"], snap.identity())
                    with self.assertRaisesRegex(CheckError, "toolchain"):
                        cargo_build.captured_archive(scratch, {**tools, "rustc": "different"})
                    with (
                        patch.dict(os.environ, {"RUSTFLAGS": "-C opt-level=3"}),
                        self.assertRaisesRegex(CheckError, "environment"),
                    ):
                        cargo_build.captured_archive(scratch, tools)
                    with (
                        contextlib.chdir(root.parent),
                        self.assertRaisesRegex(CheckError, "different candidate"),
                    ):
                        cargo_build.captured_archive(scratch, tools)
                    with patch.object(cargo_junit, "versions", return_value=tools):
                        self.assertEqual(
                            cargo_junit.main(
                                [
                                    "--report",
                                    "mismatch.xml",
                                    "--use-captured-build",
                                    "--features",
                                    "other",
                                ]
                            ),
                            1,
                        )
                        self.assertIn(
                            "packages and features",
                            ET.parse("mismatch.xml").find("error").get("message"),
                        )
                    (root / "lib.rs").write_bytes(b"v2")
                    with self.assertRaisesRegex(CheckError, "source differs"):
                        cargo_build.captured_archive(scratch, tools)
                    (root / "lib.rs").write_bytes(b"v1")
                    used[-1].write_bytes(b"other binaries")
                    with self.assertRaisesRegex(CheckError, "archive digest"):
                        cargo_build.captured_archive(scratch, tools)
            return {"status": "passed", "exit_code": 0}

        with (
            patch.object(cargo_build, "run", side_effect=run),
            patch.object(cargo_build, "versions", return_value=tools),
        ):
            cargo_build.run_with_build(snap, config, root.parent, env)
        self.assertFalse(used[0].parent.exists())

    def test_default_check_discards_inherited_build_and_rejects_external_cache_options(self):
        snap = Snapshot(Path.cwd(), "commit", "commit", [])
        tests = {"command": ["driver"], "format": "command", "timeout_seconds": 5}
        with (
            patch.dict(os.environ, {cargo_build.BUILD_ENV: "stale"}),
            patch("intentbond.testing.run", return_value={}) as runner,
        ):
            execute_tests(snap, {"tests": tests}, Path.cwd())
            self.assertNotIn(cargo_build.BUILD_ENV, runner.call_args.args[-1])
        template = (
            Path(__file__).resolve().parents[1] / "examples/rust-execution/.intentbond/scope.json"
        )
        policy = json.loads(template.read_text())
        for build in (
            False,
            {"path": "existing/target"},
            {"packages": "demo"},
            {"packages": ["demo", "demo"]},
            {"features": ["db"]},
        ):
            with self.subTest(build=build), self.assertRaises(CheckError):
                validate_scope({**policy, "tests": {**policy["tests"], "cargo_build": build}})
        with self.assertRaises(CheckError):
            validate_scope({**policy, "tests": {**tests, "cargo_build": {}}})

    def test_report_from_another_preparation_is_rejected(self):
        preparation = {
            "status": "passed",
            "exit_code": 0,
            "configuration": {},
            "candidate_sha256": "c" * 64,
            "archive_sha256": "a" * 64,
        }
        suite = ET.Element("testsuite", name="cargo-nextest")
        for name, value in (
            ("build_candidate_sha256", "c" * 64),
            ("build_archive_sha256", "b" * 64),
            ("build_configuration", "{}"),
        ):
            cargo_junit.property_value(suite, name, value)
        path = Path("stale.xml")
        ET.ElementTree(suite).write(path)
        with self.assertRaisesRegex(CheckError, "report differs"):
            cargo_build.validate_build_evidence(preparation, {}, "c" * 64, path)
        with self.assertRaisesRegex(CheckError, "configured build"):
            cargo_build.validate_build_evidence(preparation, {"features": "db"}, "c" * 64, path)
