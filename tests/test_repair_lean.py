"""Structured locality controls; real Lean validation belongs to caller adapters."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from intentbond.common import CheckError
from intentbond.repair import Session, outside_lean_clauses, policy

PRE = "req~domain~1"
POST = "req~successor~1"
OTHER = "req~positive~1"
CANDIDATE = {
    "imports": "",
    "precond_aux": "",
    "postcond_aux": "",
    "clauses": [
        {"requirement": PRE, "expr": "n < 10"},
        {"requirement": POST, "expr": "True"},
        {"requirement": OTHER, "expr": "result > 0"},
    ],
}


class LeanBoundaryTests(unittest.TestCase):
    # [utest->req~ib-repair-lean-clauses~1]
    def test_local_alternatives_and_json_formatting_pass(self):
        for expression in ("result = n + 1", "n + 1 = result", "result = Nat.succ n"):
            candidate = copy.deepcopy(CANDIDATE)
            candidate["clauses"][1]["expr"] = expression
            self.assertEqual(
                outside_lean_clauses(json.dumps(CANDIDATE), {POST}),
                outside_lean_clauses(json.dumps(candidate, sort_keys=True, indent=4), {POST}),
            )

    # [utest->req~ib-repair-lean-clauses~1]
    def test_helpers_unselected_expressions_identity_and_order_are_protected(self):
        for change in (
            lambda c: c.update(imports="import Std"),
            lambda c: c.update(precond_aux="def helper := 1"),
            lambda c: c.update(postcond_aux="def helper := 1"),
            lambda c: c["clauses"][0].update(expr="True"),
            lambda c: c["clauses"][2].update(expr="True"),
            lambda c: c["clauses"][0].update(requirement="req~replacement~1"),
            lambda c: c["clauses"].reverse(),
            lambda c: c["clauses"].pop(),
        ):
            candidate = copy.deepcopy(CANDIDATE)
            change(candidate)
            self.assertNotEqual(
                outside_lean_clauses(json.dumps(CANDIDATE), {POST}),
                outside_lean_clauses(json.dumps(candidate), {POST}),
            )

    # [utest->req~ib-repair-lean-clauses~1]
    def test_ambiguous_missing_and_invalid_candidates_fail_closed(self):
        for change in (
            lambda c: c.update(extra="ignored"),
            lambda c: c.update(clauses=[]),
            lambda c: c.update(imports=None),
            lambda c: c["clauses"].pop(1),
            lambda c: c["clauses"].append(c["clauses"][0]),
            lambda c: c["clauses"][1].update(expr=" "),
            lambda c: c["clauses"][1].update(expr=None),
            lambda c: c["clauses"][1].update(requirement="R2"),
            lambda c: c["clauses"][1].update(extra="ignored"),
        ):
            candidate = copy.deepcopy(CANDIDATE)
            change(candidate)
            with self.assertRaises(CheckError):
                outside_lean_clauses(json.dumps(candidate), {POST})
        for text in (
            "{}",
            "null",
            "[1]",
            "{",
            json.dumps(CANDIDATE).replace('"imports": ""', '"imports": "", "imports": "hidden"'),
        ):
            with self.assertRaises(CheckError):
                outside_lean_clauses(text, {POST})

    # [utest->req~ib-repair-lean-clauses~1]
    # [utest->req~ib-repair-boundaries~1]
    def test_proposal_cannot_expand_from_failed_target_to_other_selected_clause(self):
        with tempfile.TemporaryDirectory() as temp:
            session = object.__new__(Session)
            session.out = Path(temp) / "out"
            session.out.mkdir()
            session.work = Path(temp) / "work"
            session.work.mkdir()
            source = json.dumps(CANDIDATE)
            (session.work / "candidate.json").write_text(source)
            candidate = copy.deepcopy(CANDIDATE)
            candidate["clauses"][0]["expr"] = "True"
            candidate["clauses"][1]["expr"] = "result = n + 1"
            session.policy = {
                "edits": [
                    {
                        "path": "candidate.json",
                        "format": "lean-clauses-v1",
                        "requirements": [PRE, POST],
                    }
                ]
            }
            session.result = {"repairs": 0}
            with patch.object(
                session,
                "adapter",
                return_value={
                    "proposal": {
                        "targets": [POST],
                        "reason": "repair output",
                        "files": {"candidate.json": json.dumps(candidate)},
                    }
                },
            ):
                session.propose([{"case": {"requirements": [POST]}}])
            self.assertEqual(session.result["loop_status"], "rejected")
            self.assertEqual(session.result["repairs"], 0)
            self.assertEqual((session.work / "candidate.json").read_text(), source)

    # [utest->req~ib-repair-lean-clauses~1]
    # [utest->req~ib-repair-policy~1]
    def test_opt_in_and_existing_path_protections(self):
        value = {
            "schema_version": 1,
            "requirements": [POST],
            "edits": [
                {"path": "candidate.json", "format": "lean-clauses-v1", "requirements": [POST]}
            ],
            "adapter": {"command": ["/python", "/adapter.py"], "inputs": {"/adapter.py": "a" * 64}},
            "regression": {
                "test_path": "tests/test_new.py",
                "data_path": "tests/new.json",
                "links_path": "tests/links.json",
                "checks": ["utest~new~1"],
            },
            "limits": {"seconds": 120, "repairs": 2, "cases": 10},
        }
        scope = {
            "inputs": ["candidate.json", "candidate.py", "tests"],
            "specification_paths": [],
            "test_paths": ["tests"],
            "tests": {"execution_links": {"format": "junit-properties-v1"}},
        }
        plan = {
            "declaration": {
                "requirements": {"preserve": [POST]},
                "checks": ["utest~old~1"],
                "protected_paths": [],
            }
        }
        self.assertEqual(policy(value, scope, plan), value)
        for key in ("specification_paths", "test_paths"):
            changed = copy.deepcopy(scope)
            changed[key].append("candidate.json")
            with self.assertRaises(CheckError):
                policy(value, changed, plan)
        protected = copy.deepcopy(plan)
        protected["declaration"]["protected_paths"] = ["candidate.json"]
        with self.assertRaises(CheckError):
            policy(value, scope, protected)
        for edit in (
            {"path": "candidate.json", "symbol": "f", "requirements": [POST]},
            {"path": "candidate.json", "format": "lean-clauses-v2", "requirements": [POST]},
            {"path": "candidate.py", "format": "lean-clauses-v1", "requirements": [POST]},
        ):
            with self.assertRaises(CheckError):
                policy({**value, "edits": [edit]}, scope, plan)
        python = {
            **value,
            "edits": [{"path": "candidate.py", "symbol": "f", "requirements": [POST]}],
        }
        self.assertEqual(policy(python, scope, plan), python)
