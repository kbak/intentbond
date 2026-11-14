"""Completed checker evidence may guide repair; partial evidence cannot authorize it."""

import copy
import shutil
import unittest

import test_completion as completion_fixtures
import test_python_compare as comparison_fixtures
from test_python_compare import BASE, REQ

from intentbond.common import CheckError, digest, read_json, write_json
from intentbond.repair import identity, policy
from intentbond.repair_feedback import FORMAT, python_comparison_failures, validate_failures


class PythonFeedbackTests(unittest.TestCase):
    setUp = comparison_fixtures.PythonComparisonTests.setUp
    git = comparison_fixtures.PythonComparisonTests.git
    pin = comparison_fixtures.PythonComparisonTests.pin
    compare = comparison_fixtures.PythonComparisonTests.compare

    def feedback(self, result, **kwargs):
        return python_comparison_failures(
            result,
            source_sha256=kwargs.get("source_sha256", result["candidate"]["sha256"]),
            policy_sha256=kwargs.get("policy_sha256", self.pin()),
            requirements=[REQ],
        )

    def test_real_regression_feedback_and_legitimate_alternative(self):
        # [utest->req~ib-repair-feedback~1]
        result, _ = self.compare(BASE.replace(">= 1800", "> 1800"))
        rows = self.feedback(result)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["input"]["arguments"], {"seconds": 1800})
        self.assertEqual(rows[0]["requirements"], [REQ])
        self.assertEqual(rows[0]["expected"], [{"kind": "returned", "value": True}])
        self.assertEqual(rows[0]["observed"], [{"kind": "returned", "value": False}])
        result, _ = self.compare(BASE.replace(">= 1800", "> 1799").replace("Sign in", "Continue"))
        self.assertEqual(self.feedback(result), [])

    def test_partial_stale_contradictory_and_unknown_evidence_is_not_feedback(self):
        # [utest->req~ib-repair-feedback~1]
        result, _ = self.compare(BASE.replace(">= 1800", "> 1800"))
        for key, value in (
            ("complete", False),
            ("complete", 1),
            ("execution_copies_removed", False),
            ("status", "unresolved"),
            ("status", "no_difference"),
            ("semantic_approval", True),
            ("diagnostics", ["deadline exhausted"]),
            ("observations", []),
            ("scheduled_cases", 999),
        ):
            with self.subTest(key=key, value=value), self.assertRaises(CheckError):
                self.feedback({**result, key: value})
        for key in ("source_sha256", "policy_sha256"):
            with self.subTest(key=key), self.assertRaisesRegex(CheckError, "Stale"):
                self.feedback(result, **{key: "0" * 64})
        with self.assertRaisesRegex(CheckError, "identity"):
            self.feedback(result, source_sha256=None)
        bad = copy.deepcopy(result)
        bad["observations"][0]["observed"] = [{"kind": "unknown"}]
        with self.assertRaises(CheckError):
            self.feedback(bad)

    def test_attribution_duplicates_and_nonfinite_values_are_rejected(self):
        # [utest->req~ib-repair-feedback~1]
        row = {"id": "one", "requirements": [REQ], "input": 1, "expected": 2, "observed": 1}
        self.assertEqual(validate_failures([row], [REQ]), [row])
        for rows in (
            [row, row],
            [{**row, "requirements": ["req~foreign~1"]}],
            [{**row, "requirements": [REQ, REQ]}],
            [{**row, "requirements": []}],
            [{**row, "observed": float("nan")}],
            [{k: v for k, v in row.items() if k != "expected"}],
        ):
            with self.subTest(rows=rows), self.assertRaises(CheckError):
                validate_failures(rows, [REQ])


class StructuredCompletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        completion_fixtures.CompletionTests.setUpClass.__func__(cls)
        text = cls.checker.read_text()
        cls.checker.write_text(
            text.replace(
                "Path(response).write_text(json.dumps(r))",
                "r['failures'] = [] if passed else [dict(id='local-result', "
                "requirements=['req~absolute-value~1'], input={'x':-1}, "
                "expected={'local_result': True}, observed={'local_result':False})]\n"
                "if mode == 'unmapped': r['failures'][0]['requirements']=['req~foreign~1']\n"
                "if mode == 'no_failures': r['failures']=[]\n"
                "Path(response).write_text(json.dumps(r))",
            )
        )

    def session(self, mode="normal", **kwargs):
        session = completion_fixtures.CompletionTests.session(self, mode, **kwargs)
        session.policy["completion"]["format"] = FORMAT
        write_json(session.policy_path, session.policy)
        session.policy_hash = digest(session.policy_path.read_bytes())
        policy(session.policy, session.scope, session.plan)
        return session

    def test_expected_observed_and_preservation_reach_the_existing_repair_path(self):
        # [utest->req~ib-repair-feedback~1]
        session = self.session()
        result = session.execute()
        self.assertEqual(result["loop_status"], "passed", result)
        self.assertEqual(result["repairs"], 1)
        self.assertEqual(result["status"], "review_required")
        self.assertEqual(result["completion"]["source_sha256"], result["candidate"]["sha256"])
        requests = list(session.out.glob("adapter-*-propose/request.json"))
        self.assertEqual(len(requests), 1)
        q = read_json(requests[0])
        row = q["failures"][0]
        self.assertEqual(row["case"]["accepted"], [{"local_result": True}])
        self.assertEqual(row["observed"], {"local_result": False})
        self.assertEqual(row["case"]["input"]["counterexample"], {"x": -1})
        self.assertEqual(q["preservation"]["edits"], session.policy["edits"])
        self.assertEqual(
            q["preservation"]["retained_checks"], session.plan["declaration"]["checks"]
        )
        self.assertFalse(q["preservation"]["semantic_approval"])

    def test_passing_alternative_stops_without_proposal(self):
        # [utest->req~ib-repair-feedback~1]
        session = self.session()
        target = session.repo / "value.py"
        before = target.read_text()
        try:
            target.write_text(
                before.replace("return abs(x)", "result = -x if x < 0 else x\n    return result")
            )
            session.original = identity(session.repo)
            result = session.execute()
        finally:
            target.write_text(before)
        self.assertEqual(result["loop_status"], "passed", result)
        self.assertEqual(result["repairs"], 0)
        self.assertFalse(list(session.out.glob("adapter-*-propose")))

    def test_unwanted_changes_and_exhausted_budget_remain_blocked(self):
        # [utest->req~ib-repair-feedback~1]
        for control, repairs, reason in (
            ("collateral", 2, "repair_scope_violation"),
            ("repair", 0, "repair_budget_exhausted"),
        ):
            session = self.session(control=control, repairs=repairs)
            result = session.execute()
            self.assertEqual(result["loop_status"], "rejected", result)
            self.assertEqual(result["reason"], reason)
            self.assertEqual(result["repairs"], 0)

    def test_invalid_structured_feedback_cannot_trigger_proposal(self):
        # [utest->req~ib-repair-feedback~1]
        for mode in ("unmapped", "no_failures", "partial", "source_sha256", "contradiction"):
            with self.subTest(mode=mode):
                session = self.session(mode)
                shutil.copytree(self.repo, session.work)
                session.expected_source = identity(session.work)["sha256"]
                with self.assertRaises(CheckError):
                    session.completion(0)
                self.assertEqual(session.result["completion"]["status"], "unresolved")
                self.assertFalse(list(session.out.glob("adapter-*-propose")))

    def test_unknown_format_is_rejected(self):
        # [utest->req~ib-repair-feedback~1]
        session = self.session()
        session.policy["completion"]["format"] = "unknown"
        with self.assertRaises(CheckError):
            policy(session.policy, session.scope, session.plan)


if __name__ == "__main__":
    unittest.main()
