import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from intentbond.check_output import follow_test_log, render_check
from intentbond.cli import main
from intentbond.common import run
from intentbond.evidence import EXIT_CODES


class CheckOutputTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.out = Path(directory.name)
        self.result = {
            "status": "rejected",
            "diagnostics": ["Test execution did not pass"],
            "tests": {"status": "failed", "level": "suite", "source_status": "matched"},
            "artifacts": {},
        }

    def test_failure_excerpt_retains_names_and_points_to_unmodified_report(self):
        report = self.out / "tests.xml"
        report.write_text(
            '<testsuite tests="4">'
            + "".join(
                f'<testcase classname="Boundary" name="case{i}">'
                f'<failure message="expected expiry">{"details " * 200}</failure></testcase>'
                for i in range(4)
            )
            + "</testsuite>"
        )
        self.result["artifacts"] = {report.name: "retained digest"}
        before = report.read_bytes()
        text = render_check(self.result, self.out)
        self.assertIn("Boundary::case0: expected expiry", text)
        self.assertIn("1 more failing cases", text)
        self.assertNotIn("Boundary::case3", text)
        self.assertIn(f"tests.xml: {report}", text)
        self.assertIn("[excerpt]", text)
        self.assertLess(len(text), 3000)
        self.assertEqual(report.read_bytes(), before)

    def test_diagnostics_are_bounded_with_full_evidence_reference(self):
        self.result["diagnostics"] = [f"problem{i} " + "x" * 2000 for i in range(8)]
        text = render_check(self.result, self.out)
        self.assertIn(f"rejected: {self.out / 'evidence.json'}", text)
        self.assertIn("problem4", text)
        self.assertNotIn("problem5", text)
        self.assertIn("3 more diagnostics in evidence.json", text)
        self.assertLess(len(text), 4000)
        self.assertEqual(len(self.result["diagnostics"]), 8)

    def test_missing_or_invalid_report_falls_back_to_bounded_log(self):
        (self.out / "tests.log").write_text("setup noise\n" * 300 + "actual command failure\n")
        self.result["tests"]["error"] = "Invalid report"
        for report in (None, "<broken", "<!DOCTYPE bad><testsuite/>"):
            with self.subTest(report=report):
                if report is not None:
                    (self.out / "tests.xml").write_text(report)
                text = render_check(self.result, self.out)
                self.assertIn("actual command failure", text)
                self.assertIn("test error: Invalid report", text)
                self.assertIn("Test log excerpt", text)
                self.assertLess(len(text), 2500)

    def test_command_success_has_no_invented_counts_or_report(self):
        self.result.update(status="passed", diagnostics=[])
        self.result["tests"] = {"status": "passed", "level": "command", "source_status": "matched"}
        self.result["artifacts"] = {"tests.log": "digest"}
        text = render_check(self.result, self.out)
        self.assertIn("tests: passed (command); source=matched", text)
        self.assertNotIn("counts:", text)
        self.assertNotIn("tests.xml:", text)
        self.assertIn(f"tests.log: {self.out / 'tests.log'}", text)

    def test_early_error_handles_unrun_tests_and_absent_review(self):
        self.result.update(status="error", diagnostics=["OFT unavailable"])
        self.result["tests"].update(status="not_run", source_status="unchecked")
        text = render_check(self.result, self.out)
        self.assertIn("OFT unavailable", text)
        self.assertIn("review: not_recorded; changes=unknown", text)
        self.assertNotIn("review.json:", text)
        self.assertNotIn("timings:", text)

    def test_timings_use_only_recorded_command_durations(self):
        # [utest->req~ib-check-progress~1]
        self.result["trace"] = {
            "base": {"import": {"duration_seconds": 0.7}, "trace": {"duration_seconds": 0.2}},
            "candidate": {"import": {"duration_seconds": 0.4}, "trace": {"duration_seconds": 0.3}},
        }
        self.result["tests"]["duration_seconds"] = 562.739
        text = render_check(self.result, self.out)
        self.assertIn("timings: trace commands=1.600s; tests=562.739s", text)
        del self.result["tests"]["duration_seconds"]
        self.assertIn("timings: trace commands=1.600s\n", render_check(self.result, self.out))

    def test_live_output_releases_running_command_and_retains_complete_log(self):
        # [utest->req~ib-check-progress~1]
        release = self.out / "release"

        class Display(io.StringIO):
            def write(self, text):
                if "waiting" in text:
                    release.touch()
                return super().write(text)

        out = self.out / "live"
        output = Display()
        script = (
            "import pathlib, sys, time; print('waiting', flush=True); "
            "p=pathlib.Path(sys.argv[1]);\n"
            "while not p.exists(): time.sleep(0.01)\n"
            "sys.stdout.buffer.write('finished λ'.encode()); sys.exit(7)"
        )
        with follow_test_log(out, output):
            out.mkdir()
            result = run(
                [sys.executable, "-c", script, str(release)], self.out, out / "tests.log", 5
            )
        self.assertEqual(result["exit_code"], 7)
        self.assertEqual(result["status"], "failed")
        self.assertEqual((out / "tests.log").read_text(), "waiting\nfinished λ")
        self.assertTrue(output.getvalue().endswith("waiting\nfinished λ"))

    def test_progress_preserves_timeout_and_ignores_display_failure(self):
        # [utest->req~ib-check-progress~1]
        class BrokenDisplay:
            def write(self, text):
                raise BrokenPipeError("viewer disconnected")

        for display in (io.StringIO(), BrokenDisplay()):
            with self.subTest(display=type(display).__name__):
                out = self.out / type(display).__name__
                with follow_test_log(out, display):
                    out.mkdir()
                    result = run(
                        [
                            sys.executable,
                            "-c",
                            "import time; print('started', flush=True); time.sleep(60)",
                        ],
                        self.out,
                        out / "tests.log",
                        0.3,
                    )
                self.assertEqual(result["status"], "error")
                self.assertIn("timed out", result["error"])
                self.assertEqual((out / "tests.log").read_text(), "started\n")
                if isinstance(display, io.StringIO):
                    self.assertTrue(display.getvalue().endswith("started\n"))

    def test_existing_output_is_not_followed(self):
        (self.out / "tests.log").write_text("old check")
        display = io.StringIO()
        with follow_test_log(self.out, display):
            pass
        self.assertEqual(display.getvalue(), "")

    def test_cli_preserves_each_native_exit_and_does_not_rerun_checks(self):
        for status, expected in EXIT_CODES.items():
            for progress in (False, True):
                with self.subTest(status=status, progress=progress):
                    self.check_cli_status(status, expected, progress)

    def check_cli_status(self, status, expected, progress):
        # [utest->req~ib-check-progress~1]
        self.result["status"] = status
        output = io.StringIO()
        display = io.StringIO()
        with (
            patch("intentbond.cli.check", return_value=self.result) as check,
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(display),
        ):
            code = main(
                [
                    "check",
                    "--repo",
                    str(self.out),
                    "--base",
                    "fixed-base",
                    "--out",
                    str(self.out / "bundle"),
                ]
                + (["--progress"] if progress else [])
            )
        self.assertEqual(code, expected)
        check.assert_called_once()
        self.assertEqual(
            output.getvalue().splitlines()[0],
            f"{status}: {self.out / 'bundle/evidence.json'}",
        )
        self.assertEqual(bool(display.getvalue()), progress)
