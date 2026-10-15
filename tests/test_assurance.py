"""Assurance retains missing evidence and decisions in manual and adapter workflows."""

import contextlib
import copy
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from intentbond.assurance import assess, assess_files, observation, render
from intentbond.assurance_contract import context, policy
from intentbond.cli import main
from intentbond.common import canonical, digest, write_json
from intentbond.snapshot import snapshot


class AssuranceTests(unittest.TestCase):
    def setUp(self):
        self.policy = policy(required=["execution", "review", "intent"])
        self.repo = {
            "base": {"commit": "a" * 40, "sha256": "b" * 64},
            "candidate": {"commit": "c" * 40, "sha256": "d" * 64},
            "changed_paths": ["app.py"],
        }
        self.change = context("attempt-2", {"app": self.repo}, self.policy)

    def observations(self, change=None, **outcomes):
        change = change or self.change
        return {
            "app": observation(
                change, "app", {"source": "satisfied", "execution": "satisfied", **outcomes}
            )
        }

    def review(self, change=None, **updates):
        return {
            "schema_version": 1,
            "context_sha256": digest(canonical(change or self.change)),
            "producer": "reviewer",
            "verdict": "satisfied",
            "traceability_assessment": [],
            "intent_alignment": [
                {
                    "project": "app",
                    "status": "aligned",
                    "references": ["approved request"],
                    "summary": "Preserves the accepted behavior.",
                }
            ],
            **updates,
        }

    def test_missing_evidence_and_missing_review_are_not_success(self):
        # [utest->req~ib-assurance-context~1]
        report = assess(self.change, self.policy)
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(
            assess(self.change, self.policy, observations=self.observations())["status"],
            "incomplete",
        )
        report = assess(
            self.change, self.policy, observations=self.observations(), review=self.review()
        )
        self.assertEqual(report["status"], "satisfied")
        self.assertIn("does not authorize", render(report))

    def test_records_bind_source_policy_and_current_invocation(self):
        # [utest->req~ib-assurance-context~1]
        for target in ("invocation", "source", "policy"):
            change, checking_policy = copy.deepcopy(self.change), copy.deepcopy(self.policy)
            if target == "invocation":
                change["invocation"] = "attempt-3"
            elif target == "source":
                change["repositories"]["app"]["candidate"]["sha256"] = "e" * 64
            else:
                checking_policy["decisions"] = ["new-acceptance"]
            with self.subTest(target=target), self.assertRaises(ValueError):
                assess(
                    change, checking_policy, observations=self.observations(), review=self.review()
                )

    def test_failed_current_observation_cannot_be_hidden_by_passing_review(self):
        report = assess(
            self.change,
            self.policy,
            observations=self.observations(execution="failed"),
            review=self.review(),
        )
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["obligations"][1]["status"], "failed")

    def test_required_decision_remains_separate_from_tests_and_review(self):
        # [utest->req~ib-assurance-context~1]
        checking_policy = policy(required=["execution", "review"], decisions=["expiry-change"])
        change = context("attempt-2", {"app": self.repo}, checking_policy)
        kwargs = {"observations": self.observations(change), "review": self.review(change)}
        self.assertEqual(assess(change, checking_policy, **kwargs)["status"], "decision_pending")
        decision = {
            "schema_version": 1,
            "context_sha256": digest(canonical(change)),
            "producer": "maintainer-system",
            "id": "expiry-change",
            "actor": "owner",
            "outcome": "accepted",
        }
        self.assertEqual(
            assess(change, checking_policy, decisions=[decision], **kwargs)["status"], "satisfied"
        )
        decision["outcome"] = "rejected"
        self.assertEqual(
            assess(change, checking_policy, decisions=[decision], **kwargs)["status"], "failed"
        )
        with self.assertRaises(ValueError):
            assess(change, checking_policy, decisions=[decision, decision], **kwargs)

    def test_specification_check_preserves_review_pending_even_in_lightweight_policy(self):
        checking_policy = policy()
        change = context("check", {"app": self.repo}, checking_policy)
        report = assess(
            change,
            checking_policy,
            observations=self.observations(change, change_review="decision_pending"),
        )
        self.assertEqual(report["status"], "decision_pending")

    def test_independent_review_requires_caller_trusted_producer_and_implementer(self):
        # [utest->req~ib-assurance-review~1]
        checking_policy = policy(
            required=["review"], reviewers=["reviewer"], independent_review=True
        )
        for implementer, producer, expected in (
            (None, "reviewer", "incomplete"),
            ("reviewer", "reviewer", "incomplete"),
            ("author", "untrusted", "incomplete"),
            ("author", "reviewer", "satisfied"),
        ):
            change = context("check", {"app": self.repo}, checking_policy, implementer=implementer)
            result = assess(
                change,
                checking_policy,
                observations=self.observations(change),
                review=self.review(change, producer=producer),
            )
            self.assertEqual(result["status"], expected)

    def test_intent_conflict_uncertainty_and_missing_repositories_are_preserved(self):
        for status, expected in (("conflict", "failed"), ("uncertain", "incomplete")):
            review = self.review()
            review["intent_alignment"][0]["status"] = status
            self.assertEqual(
                assess(self.change, self.policy, observations=self.observations(), review=review)[
                    "status"
                ],
                expected,
            )
        self.assertEqual(
            assess(
                self.change,
                self.policy,
                observations=self.observations(),
                review=self.review(intent_alignment=[]),
            )["status"],
            "incomplete",
        )

    def test_repeated_review_references_preserve_existing_review_acceptance(self):
        # [utest->req~ib-assurance-review~1]
        review = self.review()
        review["intent_alignment"][0]["references"] *= 2
        self.assertEqual(
            assess(self.change, self.policy, observations=self.observations(), review=review)[
                "status"
            ],
            "satisfied",
        )

    def test_profile_is_optional_and_preserves_accepted_artifacts(self):
        # [utest->req~ib-assurance-profile~1]
        checking_policy = policy(profile="ai-native-sdlc")
        change = context("check", {"app": self.repo}, checking_policy)
        self.assertEqual(
            assess(change, checking_policy, observations=self.observations(change))["status"],
            "satisfied",
        )
        change["artifacts"] = [
            {
                "id": "task-spec",
                "repository": "app",
                "role": "specification",
                "path": "docs/task.md",
                "sha256": "e" * 64,
                "accepted_sha256": "f" * 64,
            }
        ]
        self.assertEqual(
            assess(change, checking_policy, observations=self.observations(change))["status"],
            "failed",
        )
        change["artifacts"][0]["role"] = "plan"
        self.assertEqual(
            assess(change, checking_policy, observations=self.observations(change))["status"],
            "satisfied",
        )
        custom = policy(
            profile={
                "name": "team",
                "version": 1,
                "required_roles": ["design"],
                "immutable_roles": [],
            }
        )
        change = context("check", {"app": self.repo}, custom)
        self.assertEqual(
            assess(change, custom, observations=self.observations(change))["status"], "incomplete"
        )

    def test_unknown_versions_fields_and_candidate_policy_changes_are_errors(self):
        for updates in (
            {"schema_version": 2},
            {"schema_version": True},
            {"approval": True},
            {"repositories": {}},
            {"policy_sha256": "f" * 64},
        ):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                assess({**self.change, **updates}, self.policy)
        with self.assertRaises(ValueError):
            policy(
                profile={
                    "name": "ai-native-sdlc",
                    "version": 1,
                    "required_roles": [],
                    "immutable_roles": [],
                }
            )

    def test_source_index_and_verifier_receipt_cannot_name_another_source(self):
        # [utest->req~ib-assurance-context~1]
        changed = copy.deepcopy(self.change)
        changed["repositories"]["app"]["requirement_index"] = {
            "candidate": {"source": self.repo["base"], "ids": ["req~expiry~1"]}
        }
        with self.assertRaisesRegex(ValueError, "another source"):
            assess(changed, self.policy)
        with self.assertRaises(ValueError):
            assess(self.change, self.policy, observations={"unknown": self.observations()["app"]})

    def test_traceability_citations_must_resolve_and_cover_selected_change(self):
        # [utest->req~ib-assurance-review~1]
        from intentbond.assurance_review import validate_assessments

        expected = {
            "app": {
                "changed_paths": ["app.py"],
                "requirement_index": {"candidate": {"ids": ["req~expiry~1"]}},
            }
        }
        entry = {
            "changed_paths": ["app.py"],
            "behavior": "Expiry",
            "status": "covered",
            "requirement_ids": ["req~expiry~1"],
            "documentation": ["requirements.md"],
            "implementation": ["app.py"],
            "verification": ["test_expiry"],
            "rationale": "Boundary assertion is linked.",
        }
        assessment = {"project": "app", "summary": "Expiry accounted for", "changes": [entry]}
        validate_assessments([assessment], expected)
        for invalid in (
            [{**assessment, "changes": []}],
            [{**assessment, "changes": [{**entry, "requirement_ids": ["req~invented~1"]}]}],
            [assessment, assessment],
            [{**assessment, "changes": [{**entry, "verification": []}]}],
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_assessments(invalid, expected)


class StandaloneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        (self.repo / "app.py").write_text("value = 1\n")
        self.git("add", ".")
        self.git(
            "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "base"
        )
        self.base = self.git("rev-parse", "HEAD").strip()
        (self.repo / "app.py").write_text("value = 2\n")
        with tempfile.TemporaryDirectory() as directory:
            before = snapshot(self.repo, self.base, Path(directory) / "base")
            after = snapshot(self.repo, "worktree", Path(directory) / "candidate")
            self.policy = policy()
            self.change = context(
                "manual-1",
                {
                    "app": {
                        "base": before.identity(),
                        "candidate": after.identity(),
                        "changed_paths": ["app.py"],
                    }
                },
                self.policy,
            )
        self.change_path, self.policy_path = self.root / "change.json", self.root / "policy.json"
        write_json(self.change_path, self.change)
        write_json(self.policy_path, self.policy)

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.repo), *args], check=True, capture_output=True, text=True
        ).stdout

    def test_manual_cli_needs_no_factory_java_test_run_or_planning_documents(self):
        # [utest->req~ib-assurance-source~1]
        with (
            patch(
                "intentbond.runner.execute_tests",
                side_effect=AssertionError("No extra test execution"),
            ),
            patch("intentbond.oft.validate_jar", side_effect=AssertionError("No Java required")),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            code = main(
                [
                    "assess",
                    "--repo",
                    str(self.repo),
                    "--change",
                    str(self.change_path),
                    "--policy",
                    str(self.policy_path),
                    "--out",
                    str(self.root / "report"),
                ]
            )
        self.assertEqual(code, 0)
        result = json.loads((self.root / "report/assessment.json").read_text())
        self.assertEqual(
            next(x for x in result["obligations"] if x["obligation"] == "execution")["status"],
            "incomplete",
        )
        self.assertFalse((self.repo / "plan.md").exists())

    def test_source_mutation_omitted_change_and_output_inside_repo_are_rejected(self):
        # [utest->req~ib-assurance-source~1]
        (self.repo / "app.py").write_text("value = 3\n")
        with self.assertRaisesRegex(Exception, "source differs"):
            assess_files(self.repo, self.change_path, self.policy_path, self.root / "report")
        (self.repo / "app.py").write_text("value = 2\n")
        self.change["repositories"]["app"]["changed_paths"] = []
        write_json(self.change_path, self.change)
        with self.assertRaisesRegex(Exception, "omits"):
            assess_files(self.repo, self.change_path, self.policy_path, self.root / "report")
        with self.assertRaisesRegex(Exception, "outside"):
            assess_files(self.repo, self.change_path, self.policy_path, self.repo / "report")

    def test_non_oft_execution_requirement_remains_incomplete(self):
        checking_policy = policy(required=["execution"])
        change = context("manual-1", self.change["repositories"], checking_policy)
        write_json(self.policy_path, checking_policy)
        write_json(self.change_path, change)
        report = assess_files(self.repo, self.change_path, self.policy_path, self.root / "report")
        self.assertEqual(report["status"], "incomplete")


if __name__ == "__main__":
    unittest.main()
