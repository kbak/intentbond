"""An equivalent bounded policy change preserves unrelated promises and exact-revision checks."""

import copy
import json
import shlex
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from test_workflow import WorkflowFixture

from intentbond.common import CheckError, read_json
from intentbond.impact import impact, render_impact


class ImpactTests(WorkflowFixture):
    def setUp(self):
        super().setUp()
        shutil.rmtree(self.repo)
        shutil.copytree(
            Path(__file__).resolve().parents[1] / "examples/granular-retries", self.repo
        )
        self.git("init", "-q", "-b", "main")
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()
        shutil.copyfile(self.repo / "scope.json", self.scope)

    def revised(self, behavior=True, stale=False):
        for path in ("requirements.md", "retry.py", "tests/test_retry.py"):
            if path != "tests/test_retry.py" or not stale:
                self.replace(path, "req~retry-cap~1", "req~retry-cap~2")
        self.replace("retry.py", "impl~retry-cap~1", "impl~retry-cap~2")
        self.replace("tests/test_retry.py", "utest~retry-cap~1", "utest~retry-cap~2")
        if behavior:
            self.replace("requirements.md", "and 8 seconds", "and 16 seconds")
            self.replace("retry.py", "min(delay, 8)", "min(delay, 16)")
            self.replace(
                "tests/test_retry.py",
                "self.assertEqual(cap(100), 8)",
                "self.assertEqual(cap(16), 16)\n        self.assertEqual(cap(100), 16)",
            )

    def report(self):
        return impact(self.out / "evidence.json", self.jar)

    def test_policy_change_affects_only_cap_promise_and_consumers(self):
        self.revised()
        result = self.run_check()
        self.assertEqual(result["status"], "review_required")
        report = self.report()
        counts = report["counts"]
        self.assertEqual(counts["base_declarations"], 6)
        self.assertEqual(counts["candidate_declarations"], 6)
        self.assertEqual(counts["changed_declarations_excluding_location"], 3)
        # [utest->req~ib-impact-report~1]
        self.assertEqual(counts["normative_text_changed"], 1)
        self.assertEqual(counts["base_edges"], 4)
        self.assertEqual(counts["candidate_edges"], 4)
        self.assertEqual(counts["continuing_edges_with_revised_endpoints"], 2)
        changed = [d for d in report["declarations"] if d["classification"] != "location_only"]
        self.assertEqual(
            {d["key"] for d in changed}, {"req~retry-cap", "impl~retry-cap", "utest~retry-cap"}
        )
        kinds = {c["path"]: c["classification"] for c in report["source_changes"]}
        self.assertEqual(kinds["retry.py"], "implementation_or_other_source_changed")
        self.assertEqual(kinds["tests/test_retry.py"], "assertion_or_test_source_changed")
        self.assertIsNone(report["human_review_minutes"])

    def test_revision_only_annotations_are_distinct_and_do_not_establish_adequacy(self):
        self.revised(behavior=False)
        self.run_check()
        report = self.report()
        # [utest->req~ib-impact-report~1]
        self.assertEqual(report["counts"]["normative_text_changed"], 0)
        self.assertEqual(report["counts"]["link_or_revision_only_declarations"], 3)
        kinds = {c["path"]: c["classification"] for c in report["source_changes"]}
        self.assertEqual(kinds["retry.py"], "recognized_annotation_lines_only")
        self.assertEqual(kinds["tests/test_retry.py"], "recognized_annotation_lines_only")
        self.assertEqual(report["review"]["status"], "required")
        self.assertTrue(any("never establishes" in text for text in report["limitations"]))

    def test_stale_test_link_is_rejected_even_when_changed_assertions_pass(self):
        self.revised(stale=True)
        result = self.run_check()
        self.assertEqual(result["tests"]["status"], "passed")
        self.assertEqual(result["status"], "rejected")
        report = self.report()
        self.assertEqual(report["trace"]["candidate"], "failed")
        self.assertGreater(report["counts"]["ambiguous_logical_edge_pairs"], 0)
        self.assertTrue(report["edges"]["ambiguous_pairs"])

    def test_cli_reproduces_report_without_repository_or_tests(self):
        self.revised()
        self.run_check()
        original = (self.out / "evidence.json").read_bytes()
        shutil.rmtree(self.repo)
        with patch(
            "intentbond.runner.execute_tests",
            side_effect=AssertionError("No test execution"),
        ):
            code, text, error = self.run_cli(
                "impact",
                "--evidence",
                str(self.out / "evidence.json"),
                "--format",
                "json",
                cwd=self.root,
            )
        self.assertEqual(code, 0, error)
        report = json.loads(text)
        self.assertEqual(report["counts"], self.report()["counts"])
        self.assertEqual((self.out / "evidence.json").read_bytes(), original)
        code, text, error = self.run_cli(
            "impact", "--evidence", str(self.out / "evidence.json"), cwd=self.root
        )
        self.assertEqual(code, 0, error)
        self.assertIn("Human review effort: not measured", text)
        code, compact, error = self.run_cli(
            "impact", "--compact", "--evidence", str(self.out / "evidence.json"), cwd=self.root
        )
        # [utest->req~ib-impact-report~1]
        self.assertEqual(code, 0, error)
        self.assertIn("Recorded check: review_required", compact)
        self.assertIn("Semantic review: required", compact)
        self.assertIn("normative text changed: 1", compact)
        self.assertNotIn("req~retry-cap: normative_text_changed", compact)
        code, structured, error = self.run_cli(
            "impact",
            "--compact",
            "--format",
            "json",
            "--evidence",
            str(self.out / "evidence.json"),
            cwd=self.root,
        )
        self.assertEqual(code, 0, error)
        self.assertEqual(json.loads(structured), report)
        self.assertEqual((self.out / "evidence.json").read_bytes(), original)

    def test_changed_export_or_report_is_rejected(self):
        self.revised()
        self.run_check()
        path = self.out / "review.json"
        path.write_text(path.read_text() + " ")
        with self.assertRaisesRegex(CheckError, "artifact missing or changed"):
            self.report()

    def test_test_body_edit_cannot_be_hidden_by_relinking(self):
        self.revised(behavior=False)
        self.replace(
            "tests/test_retry.py", "self.assertEqual(cap(100), 8)", "self.assertTrue(True)"
        )
        self.run_check()
        source = read_json(self.out / "review.json")["source_changes"]
        # [utest->req~ib-impact-report~1]
        self.assertEqual(
            next(c["classification"] for c in source if c["path"] == "tests/test_retry.py"),
            "assertion_or_test_source_changed",
        )


class CompactImpactTests(unittest.TestCase):
    def report(self):
        return {
            "evidence": "/tmp/reviewer's evidence/evidence.json",
            "counts": {"changed_declarations_excluding_location": 1000},
            "declarations": [
                {"key": f"req~ordinary-change-{n}", "classification": "normative_text_changed"}
                for n in range(1000)
            ],
            "source_changes": [],
            "inspection": {
                "changed_files": [
                    {"path": f"src/file-{n}.py", "annotation_status": "no_imported_artifacts"}
                    for n in range(1000)
                ],
                "coverage_gaps": [
                    {
                        "id": f"req~draft-{n}~1",
                        "path": "spec.md",
                        "line": n + 1,
                        "coverage": {"deep": "UNCOVERED", "uncovered_types": []},
                        "oft_status": "DRAFT",
                    }
                    for n in range(7)
                ],
                "required_execution_gaps": [
                    {"key": "utest~boundary", "status": "skipped"},
                    {"key": "utest~missing", "status": "not_established"},
                ],
                "artifacts": [{"linked_tests": ["boundary"], "linked_test_execution": "skipped"}],
                "hubs": [{}] * 1000,
            },
            "trace": {"base": "passed", "candidate": "failed"},
            "recorded_check_status": "rejected",
            "review": {"status": "required"},
            "source_classification_status": "recorded_at_check",
            "limitations": ["Recorded observations do not prove correctness."],
        }

    def test_large_change_keeps_gaps_visible_and_reports_omissions(self):
        # [utest->req~ib-impact-report~1]
        report = self.report()
        before = copy.deepcopy(report)
        text = render_impact(report, compact=True)
        self.assertIn("changed declarations excluding location: 1000", text)
        self.assertIn("no_imported_artifacts: 1000", text)
        self.assertIn("Native coverage gaps: 7", text)
        self.assertIn("deep=UNCOVERED, uncovered types=(none); item status=DRAFT", text)
        self.assertIn("2 more; see full output", text)
        self.assertNotIn("req~draft-5~1", text)
        self.assertIn("Required execution gaps: 2", text)
        self.assertIn("utest~boundary: skipped", text)
        self.assertIn("utest~missing: not_established", text)
        self.assertIn("Linked execution observations: skipped=1", text)
        self.assertIn("OFT trace: base=passed; candidate=failed", text)
        self.assertIn("Recorded check: rejected", text)
        self.assertIn("Semantic review: required", text)
        self.assertIn(report["limitations"][0], text)
        self.assertLess(len(text.splitlines()), 40)
        command = next(line.strip() for line in text.splitlines() if line.startswith("  ib impact"))
        self.assertEqual(shlex.split(command), ["ib", "impact", "--evidence", report["evidence"]])
        self.assertEqual(report, before)

    def test_legacy_missing_metadata_and_no_observations_remain_explicit(self):
        # [utest->req~ib-impact-report~1]
        report = self.report()
        report["inspection"] = {name: [] for name in report["inspection"]}
        report["source_changes"] = None
        report["source_classification_status"] = "not_recorded_in_legacy_bundle"
        report["review"] = None
        text = render_impact(report, compact=True)
        self.assertIn("Changed files: 0", text)
        self.assertIn("Native coverage gaps: 0", text)
        self.assertIn("Required execution gaps: 0", text)
        self.assertIn("Linked execution observations: none recorded", text)
        self.assertIn("Source-line classification: not_recorded_in_legacy_bundle", text)
        self.assertIn("Semantic review: not_recorded", text)
