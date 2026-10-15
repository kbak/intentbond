"""Real retained OFT evidence can be assessed without another test invocation."""

import copy
from unittest.mock import patch

from test_workflow import WorkflowFixture

from intentbond.assurance import assess_files, capture_context
from intentbond.assurance_contract import policy
from intentbond.common import CheckError, write_json


class EvidenceAssessmentTests(WorkflowFixture):
    def prepare_context(self):
        self.assertEqual(self.run_check()["status"], "passed")
        self.evidence = self.out / "evidence.json"
        self.policy = policy(required=["execution", "traceability"])
        self.change = capture_context(
            self.repo,
            self.base,
            "worktree",
            self.policy,
            "controller-check-1",
            evidence_path=self.evidence,
        )
        self.change_path, self.policy_path = (
            self.root / "change.json",
            self.root / "assurance-policy.json",
        )
        write_json(self.change_path, self.change)
        write_json(self.policy_path, self.policy)

    def test_retained_check_assessment_does_not_rerun_tests_or_trace(self):
        # [utest->req~ib-assurance-source~1]
        self.prepare_context()
        with (
            patch(
                "intentbond.runner.execute_tests", side_effect=AssertionError("No second execution")
            ),
            patch("intentbond.runner.trace", side_effect=AssertionError("No second trace")),
        ):
            report = assess_files(
                self.repo,
                self.change_path,
                self.policy_path,
                self.root / "assessment",
                evidence_path=self.evidence,
                scope_path=self.scope,
            )
        self.assertEqual(report["status"], "satisfied")

    def test_another_bundle_and_invented_requirement_index_are_rejected(self):
        # [utest->req~ib-assurance-source~1]
        self.prepare_context()
        first = self.evidence
        self.run_check()
        with self.assertRaisesRegex(CheckError, "designated bundle"):
            assess_files(
                self.repo,
                self.change_path,
                self.policy_path,
                self.root / "assessment",
                evidence_path=self.out / "evidence.json",
                scope_path=self.scope,
            )
        mutated = copy.deepcopy(self.change)
        mutated["repositories"]["project"]["requirement_index"]["candidate"]["ids"].append(
            "req~invented~1"
        )
        write_json(self.change_path, mutated)
        with self.assertRaisesRegex(CheckError, "Requirement index"):
            assess_files(
                self.repo,
                self.change_path,
                self.policy_path,
                self.root / "assessment",
                evidence_path=first,
                scope_path=self.scope,
            )

    def test_symlinked_evidence_uses_canonical_bundle_exports(self):
        # [utest->req~ib-assurance-source~1]
        self.prepare_context()
        alias = self.root / "alias"
        alias.mkdir()
        evidence = alias / "evidence.json"
        (self.root / "evidence-link.json").symlink_to(self.evidence.relative_to(self.root))
        evidence.symlink_to("../evidence-link.json")
        for altered_exports in (False, True):
            with self.subTest(altered_exports=altered_exports):
                if altered_exports:
                    for label in ("base", "candidate"):
                        path = f"{label}-items.xml"
                        (alias / path).write_text(
                            (self.out / path)
                            .read_text()
                            .replace("session-expiration", "invented-requirement")
                        )
                change = capture_context(
                    self.repo,
                    self.base,
                    "worktree",
                    self.policy,
                    "controller-check-1",
                    evidence_path=evidence,
                )
                self.assertEqual(change, self.change)
                report = assess_files(
                    self.repo,
                    self.change_path,
                    self.policy_path,
                    self.root / f"assessment-{altered_exports}",
                    evidence_path=evidence,
                    scope_path=self.scope,
                )
                self.assertEqual(report["status"], "satisfied")

    def test_symlinked_evidence_rejects_index_from_unverified_alias_exports(self):
        # [utest->req~ib-assurance-source~1]
        self.prepare_context()
        alias = self.root / "alias"
        alias.mkdir()
        evidence = alias / "evidence.json"
        evidence.symlink_to(self.evidence)
        for label in ("base", "candidate"):
            path = f"{label}-items.xml"
            (alias / path).write_text(
                (self.out / path).read_text().replace("session-expiration", "invented-requirement")
            )
        for label in ("base", "candidate"):
            with self.subTest(snapshot=label):
                change = copy.deepcopy(self.change)
                index = change["repositories"]["project"]["requirement_index"][label]
                index["ids"] = [
                    item.replace("session-expiration", "invented-requirement")
                    for item in index["ids"]
                ]
                write_json(self.change_path, change)
                with self.assertRaisesRegex(CheckError, "Requirement index"):
                    assess_files(
                        self.repo,
                        self.change_path,
                        self.policy_path,
                        self.root / "assessment",
                        evidence_path=evidence,
                        scope_path=self.scope,
                    )
                self.assertFalse((self.root / "assessment").exists())

    def test_changed_specification_remains_pending_after_passing_execution(self):
        path = self.repo / "requirements.md"
        path.write_text(path.read_text() + "\nClarify the reason for expiry.\n")
        self.assertEqual(self.run_check()["status"], "review_required")
        checking_policy = policy(required=["execution", "traceability"])
        evidence = self.out / "evidence.json"
        change = capture_context(
            self.repo, self.base, "worktree", checking_policy, "spec-change", evidence_path=evidence
        )
        write_json(self.root / "change.json", change)
        write_json(self.root / "assurance-policy.json", checking_policy)
        report = assess_files(
            self.repo,
            self.root / "change.json",
            self.root / "assurance-policy.json",
            self.root / "assessment",
            evidence_path=evidence,
            scope_path=self.scope,
        )
        self.assertEqual(report["status"], "decision_pending")
