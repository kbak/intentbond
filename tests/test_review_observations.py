"""Review observations retain native OFT and actual execution distinctions."""

import json
import shutil
import sys

from test_workflow import WorkflowFixture

from intentbond import worklist
from intentbond.common import CheckError, read_json, write_json
from intentbond.explain import explain
from intentbond.impact import impact, render_impact

REQ = "req~session-expiration~1"
TEST = "utest~expiration-boundary~1"


class ObservationTests(WorkflowFixture):
    def report(self):
        return impact(self.out / "evidence.json", self.jar)

    def execution(self):
        self.replace("tests/test_session.py", f"[utest->{REQ}]", f"[{TEST}->{REQ}]")
        write_json(
            self.repo / "tests/oft-links.json",
            {"test_session.SessionTests.test_expiration_boundary": [TEST]},
        )
        self.configure(
            lambda scope: scope["tests"].update(
                command=[
                    sys.executable,
                    "-m",
                    "intentbond.unittest_junit",
                    "--start",
                    "tests",
                    "--report",
                    "test-results.xml",
                    "--links",
                    "tests/oft-links.json",
                ],
                execution_links={
                    "format": "junit-properties-v1",
                    "artifact_types": ["utest"],
                    "required_artifacts": ["utest~expiration-boundary"],
                },
            )
        )

    def test_cli_distinguishes_coverage_gaps_and_tracing_boundaries(self):
        # [utest->req~ib-review-observations~1]
        (self.repo / "unannotated.py").write_text("def helper():\n    return 1\n")
        (self.repo / "excluded.py").write_text("# Illustrative source.\n")
        (self.repo / "notes.txt").write_text("Outside tracing.\n")
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()
        self.replace("tests/test_session.py", f"# [utest->{REQ}]", "# No declared test coverage")
        for name in ("unannotated.py", "excluded.py", "notes.txt"):
            with (self.repo / name).open("a") as stream:
                stream.write("\n# Candidate edit\n")
        self.configure(
            lambda scope: scope.update(
                inputs=[*scope["inputs"], "unannotated.py", "excluded.py"],
                trace_exclude=["excluded.py"],
            )
        )
        result = self.run_check()
        self.assertEqual(result["status"], "rejected", result)
        code, output, error = self.run_cli(
            "impact", "--evidence", str(self.out / "evidence.json"), "--format", "json"
        )
        self.assertEqual(code, 0, error)
        report = json.loads(output)
        files = {item["path"]: item for item in report["inspection"]["changed_files"]}
        self.assertEqual(files["unannotated.py"]["annotation_status"], "no_imported_artifacts")
        self.assertEqual(files["excluded.py"]["annotation_status"], "excluded_from_tracing")
        self.assertEqual(files["notes.txt"]["annotation_status"], "outside_tracing_inputs")
        gap = next(item for item in report["inspection"]["coverage_gaps"] if item["id"] == REQ)
        self.assertIn("utest", gap["coverage"]["uncovered_types"])

    def test_hub_counts_distinct_exact_artifacts_and_explain_navigates_neighbors(self):
        (self.repo / "extra.py").write_text(f"# [impl~another~1->{REQ}]\nVALUE = 1\n")
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()
        self.replace("extra.py", "VALUE = 1", "VALUE = 2")
        self.configure(lambda scope: scope["inputs"].append("extra.py"))
        self.run_check()
        report = self.report()
        hub = next(item for item in report["inspection"]["hubs"] if item["id"] == REQ)
        self.assertEqual(hub["in"], 3)
        self.assertIn("impl~another~1", hub["incoming"])
        self.assertEqual(
            explain(REQ, self.out / "evidence.json", self.jar)["degree"]["incoming"],
            hub["incoming"],
        )

    def test_required_execution_gaps_distinguish_skips_and_missing_declarations(self):
        self.execution()
        self.configure(
            lambda scope: scope["tests"]["execution_links"]["required_artifacts"].append(
                "utest~absent"
            )
        )
        self.replace(
            "tests/test_session.py",
            "    def test_expiration_boundary",
            "    @unittest.skip('boundary deferred')\n    def test_expiration_boundary",
        )
        with (self.repo / "tests/test_session.py").open("a") as stream:
            stream.write("\n    def test_smoke(self):\n        self.assertFalse(expired(0))\n")
        result = self.run_check()
        self.assertEqual(result["tests"]["status"], "passed", result)
        self.assertEqual(result["status"], "rejected")
        report = self.report()
        self.assertEqual(
            {
                item["key"]: item["status"]
                for item in report["inspection"]["required_execution_gaps"]
            },
            {"utest~expiration-boundary": "skipped", "utest~absent": "not_established"},
        )
        item = next(item for item in report["inspection"]["artifacts"] if item["id"] == REQ)
        self.assertEqual(item["linked_test_execution"], "skipped")
        self.assertIn("Linked execution: " + REQ + " skipped", render_impact(report))

    def test_stale_edges_are_not_counted_as_resolved_neighbors(self):
        self.execution()
        revised = "req~session-expiration~2"
        self.replace("requirements.md", REQ, revised)
        result = self.run_check()
        self.assertEqual(result["tests"]["status"], "passed")
        self.assertEqual(result["status"], "rejected")
        report = self.report()
        current = {item["id"]: item for item in report["inspection"]["artifacts"]}
        self.assertEqual(current[revised]["degree"]["in"], 0)
        self.assertEqual(current[revised]["coverage"]["deep"], "UNCOVERED")
        self.assertEqual(current[revised]["linked_test_execution"], "not_established")
        self.assertEqual(current[revised]["linked_tests"], [])
        self.assertTrue(
            any(
                relation["status"] == "COVERING_WRONG_VERSION"
                for relation in current[revised]["covering_statuses"]
            )
        )
        self.assertEqual(current[TEST]["linked_test_execution"], "passed")
        explained = explain(revised, self.out / "evidence.json", self.jar)
        self.assertEqual(explained["linked_test_execution"], "not_established")
        self.assertEqual(explained["linked_tests"], [])
        frozen = worklist.start(
            self.out / "evidence.json",
            self.root / "review",
            self.repo,
            self.jar,
            scope_path=self.scope,
        )
        task = next(
            item for item in frozen["items"] if item["id"] == f"artifact:candidate:{revised}"
        )
        self.assertEqual(task["artifact"]["linked_test_execution"], "not_established")
        self.assertEqual(task["artifact"]["linked_tests"], [])
        self.assertIn(REQ, current[TEST]["covers"])
        self.assertEqual(current[TEST]["degree"]["outgoing"], [])

    def test_retained_execution_needs_no_source_and_rejects_summary_tampering(self):
        self.execution()
        self.run_check()
        evidence = self.out / "evidence.json"
        shutil.rmtree(self.repo)
        self.assertEqual(self.report()["inspection"]["required_execution_gaps"], [])
        # A rewritten summary cannot replace the retained report associations.
        value = read_json(evidence)
        value["predicate"]["tests"]["execution_links"]["artifacts"][0]["status"] = "skipped"
        write_json(evidence, value)
        with self.assertRaisesRegex(CheckError, "Execution links do not match"):
            self.report()
