"""Early execution stops retain diagnostics without establishing suite completion."""

import sys
import tempfile
import unittest
from pathlib import Path

from intentbond.check_output import render_check
from intentbond.snapshot import Snapshot
from intentbond.testing import execute_tests

PASS = '<testsuite><testcase name="ok"/></testsuite>'
FAIL = (
    '<testsuite><testcase classname="cargo" name="broken">'
    '<failure message="test failed"/><system-out>before panic</system-out>'
    "<system-err>original panic detail</system-err></testcase></testsuite>"
)


class PartialReports(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.counter = 0

    def execute(self, files, names, *, extra="", exit_code=0, timeout=5, **config):
        self.counter += 1
        candidate = self.root / f"candidate-{self.counter}"
        candidate.mkdir()
        out = self.root / f"out-{self.counter}"
        out.mkdir()
        script = "from pathlib import Path; import sys, time\n"
        script += "\n".join(f"Path({name!r}).write_text({text!r})" for name, text in files.items())
        script += f"\n{extra}\nsys.exit({exit_code})\n"
        tests = {
            "command": [sys.executable, "-c", script],
            "timeout_seconds": timeout,
            "reports": names,
            **config,
        }
        result = execute_tests(Snapshot(candidate, "worktree", "commit", []), {"tests": tests}, out)
        return result, out

    # [utest->req~ib-report-merge~1]
    def test_missing_or_invalid_report_does_not_discard_other_originals(self):
        for contents in (None, "<broken", '<testsuite tests="2"><testcase name="ok"/></testsuite>'):
            for names in (["bad.xml", "failure.xml"], ["failure.xml", "bad.xml"]):
                with self.subTest(contents=contents, names=names):
                    files = {"failure.xml": FAIL}
                    if contents is not None:
                        files["bad.xml"] = contents
                    result, out = self.execute(files, names)
                    self.assertEqual(result["status"], "error")
                    self.assertEqual(result["exit_code"], 0)
                    self.assertNotIn("counts", result)
                    self.assertFalse((out / "tests.xml").exists())
                    for record in result["reports"]:
                        self.assertEqual(
                            (out / record["artifact"]).read_text(), files[record["source"]]
                        )
                    self.assertEqual(len(result["reports"]), len(files))
                    self.assertIn("bad.xml", " ".join(result["report_errors"]))
                    rendered = render_check(
                        {
                            "status": "rejected",
                            "tests": {**result, "source_status": "matched"},
                            "diagnostics": [],
                        },
                        out,
                    )
                    self.assertIn("cargo::broken", rendered)
                    self.assertIn("original panic detail", rendered)
                    self.assertIn("before panic", rendered)
                    self.assertIn(
                        str(out / f"tests-{names.index('failure.xml') + 1}.xml"), rendered
                    )

    # [utest->req~ib-report-merge~1]
    def test_timeout_and_exit_failure_survive_report_errors(self):
        for timeout in (False, True):
            with self.subTest(timeout=timeout):
                result, out = self.execute(
                    {"cargo.xml": FAIL},
                    ["cargo.xml", "proof.xml"],
                    exit_code=7,
                    extra="time.sleep(60)" if timeout else "",
                    timeout=0.5 if timeout else 5,
                    verus_reports=["proof.xml"],
                )
                self.assertEqual(result["status"], "error")
                self.assertEqual(result["exit_code"], None if timeout else 7)
                self.assertIn("timed out" if timeout else "exit 7", result["error"])
                self.assertEqual((out / "tests-1.xml").read_text(), FAIL)
                self.assertEqual(len(result["report_errors"]), 2)
                self.assertIn("proof.xml.verus.json", " ".join(result["report_errors"]))

    # [utest->req~ib-fresh-reports~1]
    def test_unsafe_reports_are_rejected_while_safe_originals_are_retained(self):
        outside = self.root / "outside.xml"
        outside.write_text(PASS)
        for extra in (
            f"Path('unsafe.xml').symlink_to({str(outside)!r})",
            "Path('unsafe.xml').mkdir()",
            "import os; os.mkfifo('unsafe.xml')",
        ):
            with self.subTest(extra=extra):
                result, out = self.execute(
                    {"safe.xml": PASS}, ["unsafe.xml", "safe.xml"], extra=extra
                )
                self.assertEqual(result["status"], "error")
                self.assertFalse((out / "tests-1.xml").exists())
                self.assertEqual((out / "tests-2.xml").read_text(), PASS)
                self.assertNotIn("counts", result)

    # [utest->req~ib-verus-evidence~1]
    def test_invalid_native_projection_does_not_discard_later_reports(self):
        result, out = self.execute(
            {"proof.xml": PASS, "proof.xml.verus.json": "{broken", "cargo.xml": FAIL},
            ["proof.xml", "cargo.xml"],
            verus_reports=["proof.xml"],
        )
        self.assertEqual(result["status"], "error")
        self.assertEqual((out / "verus-1.json").read_text(), "{broken")
        self.assertEqual((out / "tests-2.xml").read_text(), FAIL)
        self.assertEqual(len(result["reports"]), 2)
        self.assertNotIn("counts", result)

    # [utest->req~ib-junit-completion~1]
    def test_complete_passing_reports_cannot_override_command_failure_or_timeout(self):
        for timeout in (False, True):
            with self.subTest(timeout=timeout):
                result, out = self.execute(
                    {"ok.xml": PASS},
                    ["ok.xml"],
                    exit_code=7,
                    extra="time.sleep(60)" if timeout else "",
                    timeout=0.5 if timeout else 5,
                )
                self.assertEqual(result["status"], "error" if timeout else "failed")
                self.assertIn("timed out" if timeout else "exit 7", result["error"])
                self.assertEqual(result["counts"]["passed"], 1)
                self.assertTrue((out / "tests.xml").exists())
