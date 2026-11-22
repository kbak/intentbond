import contextlib
import json
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from intentbond import cargo_junit, verus_junit
from intentbond.common import CheckError
from intentbond.execution import collect_execution_links
from intentbond.rust_junit import bindings


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
