"""Real OFT and executed regression controls for the opt-in change guard."""

import copy
import json
from unittest.mock import patch

from test_execution import OPTIONS, REQ, TEST
from test_workflow import WorkflowFixture

from intentbond import change_guard
from intentbond.common import CheckError, digest, read_json, write_json


class ChangeGuardTests(WorkflowFixture):
    def setUp(self):
        super().setUp()
        self.replace(
            "tests/test_session.py", "# [utest->" + REQ + "]", "# [" + TEST + "->" + REQ + "]"
        )
        path = self.repo / "tests/test_session.py"
        path.write_text(path.read_text() + f'\n    test_expiration_boundary.oft_id = "{TEST}"\n')
        self.replace(
            "run_tests.py",
            'self.case = ET.SubElement(suite_xml, "testcase", name=test.id())',
            'self.case = ET.SubElement(suite_xml, "testcase", name=test.id())\n        identifier = getattr(getattr(test, test._testMethodName), "oft_id", None)\n        if identifier:\n            properties = ET.SubElement(self.case, "properties")\n            ET.SubElement(properties, "property", name="oft_id", value=identifier)',
        )
        self.configure(lambda scope: scope["tests"].update(execution_links=copy.deepcopy(OPTIONS)))
        write_json(self.repo / "scope.json", read_json(self.scope))
        (self.repo / "api").mkdir()
        (self.repo / "api/schema.json").write_text('{"field": "inactive_seconds"}\n')
        (self.repo / "label.txt").write_text("Sign in\n")
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()
        self.declaration = {
            "schema_version": 1,
            "requirements": {"preserve": [], "change": [], "remove": [], "add": []},
            "protected_paths": ["api"],
            "checks": [TEST],
            "check_support_paths": ["run_tests.py"],
        }
        self.plan_number = 0

    def prepare(self):
        self.run_check()
        self.plan_number += 1
        declaration = self.root / "change.json"
        write_json(declaration, self.declaration)
        result = change_guard.prepare(
            self.out / "evidence.json",
            declaration,
            self.root / f"guard-{self.plan_number}",
            self.repo,
            self.base,
            self.jar,
            scope_path=self.scope,
        )
        self.plan = self.root / f"guard-{self.plan_number}/plan.json"
        self.plan_hash = result["plan_sha256"]
        return result

    def evaluate(self, fresh=True):
        if fresh:
            self.run_check()
        return change_guard.check(
            self.out / "evidence.json",
            self.plan,
            self.plan_hash,
            self.repo,
            self.jar,
            scope_path=self.scope,
        )

    def codes(self, result):
        return {item["code"] for item in result["diagnostics"]}

    def test_label_change_and_equivalent_implementation_refactor_pass(self):
        # [utest->req~ib-change-guard-preservation~1]
        # [utest->req~ib-change-guard-checks~1]
        self.prepare()
        (self.repo / "label.txt").write_text("Continue\n")
        (self.repo / "api_backup.txt").write_text("Unprotected sibling prefix\n")
        self.replace("session.py", "inactive_seconds >= 30 * 60", "not inactive_seconds < 1800")
        result = self.evaluate()
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(
            result["requirements"], [{"id": REQ, "action": "preserve", "candidate": REQ}]
        )
        self.assertEqual(result["checks"][0]["status"], "passed")
        self.assertEqual(
            result["candidate"]["sha256"],
            read_json(self.out / "evidence.json")["predicate"]["candidate"]["sha256"],
        )

    def test_protected_content_mode_deletion_and_new_child_are_rejected(self):
        # [utest->req~ib-change-guard-preservation~1]
        self.prepare()
        path = self.repo / "api/schema.json"
        original = path.read_bytes()
        for variant in ("content", "mode", "delete", "new_child"):
            with self.subTest(variant=variant):
                path.write_bytes(original)
                path.chmod(0o644)
                if variant == "content":
                    path.write_text('{"field": "renamed"}\n')
                elif variant == "mode":
                    path.chmod(0o755)
                elif variant == "delete":
                    path.unlink()
                else:
                    (self.repo / "api/new.json").write_text("{}\n")
                result = self.evaluate()
                self.assertEqual(result["status"], "rejected", result)
                self.assertIn("protected_path_changed", self.codes(result))

    def test_retained_regression_failure_is_not_hidden_by_passing_new_feature(self):
        # [utest->req~ib-change-guard-checks~1]
        self.prepare()
        self.replace("session.py", ">= 30 * 60", "> 30 * 60")
        (self.repo / "tests/test_feature.py").write_text(
            "import unittest\nclass Feature(unittest.TestCase):\n    def test_label(self):\n        self.assertEqual('Continue'.lower(), 'continue')\n"
        )
        result = self.evaluate()
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["checks"][0]["status"], "failed")
        self.assertEqual(result["checks"][0]["changed_source_paths"], [])
        self.assertIn("check_unresolved", self.codes(result))
        counts = read_json(self.out / "evidence.json")["predicate"]["tests"]["counts"]
        self.assertEqual(counts["total"], 2)
        self.assertEqual(counts["failed"], 1)

    def test_weakened_passing_assertion_still_requires_reassessment(self):
        # [utest->req~ib-change-guard-checks~1]
        self.prepare()
        self.replace("session.py", ">= 30 * 60", "> 30 * 60")
        self.replace(
            "tests/test_session.py", "self.assertTrue(expired(1800))", "self.assertTrue(True)"
        )
        result = self.evaluate()
        self.assertEqual(result["checks"][0]["status"], "passed")
        self.assertEqual(result["guard_status"], "review_required")
        self.assertIn("check_source_changed", self.codes(result))
        self.assertIn("tests/test_session.py", result["checks"][0]["changed_source_paths"])

    def test_skipped_removed_and_unobserved_retained_check_do_not_pass(self):
        # [utest->req~ib-change-guard-checks~1]
        self.prepare()
        path = self.repo / "tests/test_session.py"
        original = path.read_text()
        for variant in ("skip", "remove", "unobserved"):
            with self.subTest(variant=variant):
                path.write_text(original)
                if variant == "skip":
                    self.replace(
                        "tests/test_session.py",
                        "    def test_expiration_boundary",
                        "    @unittest.skip('fixture')\n    def test_expiration_boundary",
                    )
                elif variant == "remove":
                    path.write_text(
                        "import unittest\nclass Other(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n"
                    )
                else:
                    self.replace(
                        "tests/test_session.py",
                        f'test_expiration_boundary.oft_id = "{TEST}"',
                        "test_expiration_boundary.oft_id = None",
                    )
                result = self.evaluate()
                self.assertNotEqual(result["status"], "passed")
                self.assertIn("check_unresolved", self.codes(result))
                self.assertIn("check_source_changed", self.codes(result))

    def test_changed_check_support_requires_reassessment(self):
        self.prepare()
        with (self.repo / "run_tests.py").open("a") as stream:
            stream.write("\n# Producer was edited.\n")
        result = self.evaluate()
        self.assertEqual(result["guard_status"], "review_required")
        self.assertEqual(result["checks"][0]["changed_source_paths"], ["run_tests.py"])

    def test_unselected_execution_is_not_a_preservation_claim(self):
        # [utest->req~ib-change-guard-checks~1]
        self.declaration["checks"] = []
        self.prepare()
        result = self.evaluate(False)
        self.assertEqual(result["guard_status"], "review_required")
        self.assertIn("requirement_unchecked", self.codes(result))

    def test_accidental_requirement_removal_and_prose_edit_are_distinct(self):
        # [utest->req~ib-change-guard-preservation~1]
        self.prepare()
        path = self.repo / "requirements.md"
        original = path.read_text()
        self.replace("requirements.md", "30 minutes", "31 minutes")
        result = self.evaluate()
        self.assertEqual(result["guard_status"], "review_required")
        self.assertIn("requirement_changed", self.codes(result))
        path.write_text(original.replace("`" + REQ + "`", ""))
        result = self.evaluate()
        self.assertEqual(result["guard_status"], "rejected")
        self.assertIn("requirement_missing", self.codes(result))

    def test_authorized_requirement_change_preserves_native_review_gate(self):
        self.declaration["requirements"]["change"] = [REQ]
        self.prepare()
        self.replace("requirements.md", "30 minutes", "30 minutes of inactivity")
        result = self.evaluate()
        self.assertEqual(result["guard_status"], "passed", result)
        self.assertEqual(result["status"], "review_required")
        self.assertEqual(result["recorded_check_status"], "review_required")

    def test_authorized_addition_passes_but_missing_or_undeclared_addition_does_not(self):
        # [utest->req~ib-change-guard-preservation~1]
        added = "req~new-feature~1"
        self.declaration["requirements"]["add"] = [added]
        self.prepare()
        self.assertIn("addition_missing", self.codes(self.evaluate(False)))
        with (self.repo / "requirements.md").open("a") as stream:
            stream.write(
                f"\n### New feature\n`{added}`\n\nThe label is Continue.\n\nNeeds: impl, utest\n"
            )
        (self.repo / "tests/test_feature.py").write_text(
            f"# [impl->{added}]\nimport unittest\nclass Feature(unittest.TestCase):\n"
            f"    # [utest->{added}]\n    def test_label(self):\n"
            "        from pathlib import Path\n        self.assertEqual(Path('label.txt').read_text(), 'Continue\\n')\n"
        )
        (self.repo / "label.txt").write_text("Continue\n")
        result = self.evaluate()
        self.assertEqual(result["guard_status"], "passed", result)
        self.assertEqual(result["status"], "review_required")
        # A caller can explicitly replace the plan; candidate changes cannot do so.
        self.declaration["requirements"]["add"] = []
        self.prepare()
        self.assertIn("undeclared_addition", self.codes(self.evaluate(False)))

    def test_requirement_location_move_is_allowed(self):
        self.prepare()
        path = self.repo / "requirements.md"
        path.write_text("\n\n" + path.read_text())
        result = self.evaluate()
        self.assertEqual(result["guard_status"], "passed", result)
        self.assertNotIn("requirement_changed", self.codes(result))

    def test_no_execution_profile_is_an_explicit_gap_and_cannot_select_checks(self):
        self.configure(lambda scope: scope["tests"].pop("execution_links"))
        self.declaration["checks"] = []
        self.prepare()
        result = self.evaluate(False)
        self.assertIn("requirement_unchecked", self.codes(result))
        self.assertEqual(result["status"], "review_required")
        self.declaration["checks"] = [TEST]
        with self.assertRaisesRegex(CheckError, "named baseline execution artifact"):
            self.prepare()

    def test_cli_prepare_pins_plan_and_pending_review_exits_four(self):
        self.declaration["checks"] = []
        self.run_check()
        write_json(self.root / "declaration.json", self.declaration)
        code, output, error = self.run_cli(
            "guard",
            "prepare",
            "--repo",
            str(self.repo),
            "--base",
            self.base,
            "--scope",
            str(self.scope),
            "--evidence",
            str(self.out / "evidence.json"),
            "--declaration",
            str(self.root / "declaration.json"),
            "--out",
            str(self.root / "cli-plan"),
            "--format",
            "json",
        )
        self.assertEqual(code, 0, error)
        prepared = json.loads(output)
        code, output, error = self.run_cli(
            "guard",
            "check",
            "--repo",
            str(self.repo),
            "--scope",
            str(self.scope),
            "--evidence",
            str(self.out / "evidence.json"),
            "--plan",
            prepared["plan"],
            "--plan-sha256",
            prepared["plan_sha256"],
            "--format",
            "json",
        )
        self.assertEqual(code, 4, error)
        self.assertEqual(json.loads(output)["guard_status"], "review_required")

    def test_authorized_removal_is_distinguished_from_accidental_loss(self):
        # [utest->req~ib-change-guard-preservation~1]
        old = "req~obsolete~1"
        with (self.repo / "requirements.md").open("a") as stream:
            stream.write(
                f"\n### Old behavior\n`{old}`\n\nThe old endpoint returns 1.\n\nNeeds: impl, utest\n"
            )
        (self.repo / "tests/test_old.py").write_text(
            f"# [impl->{old}]\nimport unittest\nclass Old(unittest.TestCase):\n    # [utest->{old}]\n    def test_old(self):\n        self.assertEqual(1, 1)\n"
        )
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()
        self.declaration["requirements"]["remove"] = [old]
        self.prepare()
        path = self.repo / "requirements.md"
        path.write_text(path.read_text().split("### Old behavior")[0])
        (self.repo / "tests/test_old.py").unlink()
        result = self.evaluate()
        self.assertEqual(result["guard_status"], "passed", result)
        self.assertIn({"id": old, "action": "remove", "candidate": None}, result["requirements"])
        self.assertEqual(result["status"], "review_required")

    def test_stale_result_changed_baseline_and_changed_policy_are_distinct(self):
        # [utest->req~ib-change-guard-policy~1]
        self.prepare()
        (self.repo / "label.txt").write_text("Changed\n")
        self.assertIn("stale_evidence", self.codes(self.evaluate(False)))
        self.commit()
        original_base = self.base
        self.base = self.git("rev-parse", "HEAD").strip()
        self.assertIn("baseline_changed", self.codes(self.evaluate()))
        self.base = original_base
        self.configure(lambda scope: scope.update(review_paths=["label.txt"]))
        self.assertIn("checking_policy_changed", self.codes(self.evaluate()))

    def test_frozen_plan_cannot_erase_obligations_or_self_authorize(self):
        # [utest->req~ib-change-guard-policy~1]
        self.prepare()
        plan = read_json(self.plan)
        self.assertEqual(plan["declaration"]["requirements"]["preserve"], [REQ])
        plan["declaration"]["protected_paths"] = []
        plan["declaration"]["checks"] = []
        write_json(self.plan, plan)
        with self.assertRaisesRegex(CheckError, "guard_plan_changed"):
            self.evaluate(False)

    def test_candidate_scope_cannot_lower_frozen_policy(self):
        self.prepare()
        scope = read_json(self.repo / "scope.json")
        scope["tests"].pop("execution_links")
        write_json(self.repo / "scope.json", scope)
        self.replace("session.py", ">= 30 * 60", "> 30 * 60")
        result = self.evaluate()
        self.assertEqual(result["checks"][0]["status"], "failed")
        self.assertEqual(result["status"], "rejected")

    def test_in_repo_records_unknown_refs_and_conflicting_actions_are_errors(self):
        # [utest->req~ib-change-guard-policy~1]
        self.prepare()
        with self.assertRaisesRegex(CheckError, "outside"):
            change_guard.prepare(
                self.out / "evidence.json",
                self.root / "change.json",
                self.repo / "guard",
                self.repo,
                self.base,
                self.jar,
                scope_path=self.scope,
            )
        for action, refs in (("change", ["req~unknown~1"]), ("remove", [REQ])):
            value = copy.deepcopy(self.declaration)
            value["requirements"]["preserve"] = [REQ]
            value["requirements"][action] = refs
            write_json(self.root / "invalid.json", value)
            with self.assertRaises(CheckError):
                change_guard.prepare(
                    self.out / "evidence.json",
                    self.root / "invalid.json",
                    self.root / "invalid",
                    self.repo,
                    self.base,
                    self.jar,
                    scope_path=self.scope,
                )

    def test_cli_reports_exit_codes_and_does_not_rerun_tests(self):
        self.prepare()
        command = [
            "guard",
            "check",
            "--repo",
            str(self.repo),
            "--scope",
            str(self.scope),
            "--evidence",
            str(self.out / "evidence.json"),
            "--plan",
            str(self.plan),
            "--plan-sha256",
            self.plan_hash,
            "--format",
            "json",
        ]
        with patch("intentbond.runner.execute_tests", side_effect=AssertionError("No rerun")):
            code, output, error = self.run_cli(*command)
        self.assertEqual(code, 0, error)
        self.assertEqual(json.loads(output)["status"], "passed")
        (self.repo / "api/schema.json").write_text("{}\n")
        self.run_check()
        command[command.index("--evidence") + 1] = str(self.out / "evidence.json")
        code, output, error = self.run_cli(*command)
        self.assertEqual(code, 1, error)
        self.assertIn("protected_path_changed", output)
        self.assertEqual(digest(self.plan.read_bytes()), self.plan_hash)
