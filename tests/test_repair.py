"""Bounded repair properties and real native checking of an opt-in repair session."""

import contextlib
import copy
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hypothesis import given
from hypothesis import strategies as st

from intentbond.change_guard import prepare
from intentbond.cli import main, parser
from intentbond.common import CheckError, digest, read_json, write_json
from intentbond.oft import default_jar
from intentbond.repair import Session, outside_symbol, policy, repair
from intentbond.runner import check

REQ = "req~absolute-value~1"
OLD = "utest~positive-value~1"
NEW = "utest~negative-value~1"


class BoundaryTests(unittest.TestCase):
    def test_cli_only_dispatches_repair_on_explicit_opt_in(self):
        # [utest->req~ib-repair-policy~1]
        self.assertEqual(parser().parse_args(["check"]).action, "check")
        self.assertEqual(
            parser().parse_args(["verify", "--evidence", "/tmp/evidence"]).action, "verify"
        )
        for status, code in [
            ("passed", 0),
            ("review_required", 4),
            ("rejected", 1),
            ("unresolved", 5),
        ]:
            with (
                patch("intentbond.repair.repair", return_value={"status": status}) as call,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                actual = main(
                    [
                        "repair",
                        "run",
                        "--plan",
                        "/plan",
                        "--plan-sha256",
                        "a" * 64,
                        "--policy",
                        "/policy",
                        "--policy-sha256",
                        "b" * 64,
                        "--out",
                        "/output",
                    ]
                )
            self.assertEqual(actual, code)
            self.assertEqual(call.call_count, 1)

    # [utest->req~ib-repair-boundaries~1]
    @given(st.integers(), st.text(alphabet="αβé漢字", min_size=1, max_size=10))
    def test_body_changes_preserve_surrounding_bytes_including_unicode(self, value, name):
        prefix = f"# {name}\n@decorator\nasync def work(x: str = '{name}'):\n    "
        old = prefix + "return x\n\ndef other():\n    return 7\n"
        new = prefix + f"return {value}\n\ndef other():\n    return 7\n"
        self.assertEqual(outside_symbol(old, "work"), outside_symbol(new, "work"))
        self.assertNotEqual(
            outside_symbol(old, "work"), outside_symbol(new + "EXTRA = 1\n", "work")
        )
        self.assertNotEqual(
            outside_symbol(old, "work"), outside_symbol(new.replace("x: str", "x: int"), "work")
        )

    def test_named_method_and_ambiguous_or_missing_symbol(self):
        # [utest->req~ib-repair-boundaries~1]
        text = "class Store:\n    def batch(self):\n        return 1\n"
        self.assertEqual(
            outside_symbol(text, "Store.batch"),
            outside_symbol(text.replace("return 1", "return 2"), "Store.batch"),
        )
        for symbol in ("Store", "missing", "Store.missing"):
            with self.assertRaises(CheckError):
                outside_symbol(text, symbol)
        with self.assertRaises(CheckError):
            outside_symbol("def x(): pass\ndef x(): pass\n", "x")


class CaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.session = object.__new__(Session)
        self.session.out = Path(self.temp.name)
        self.session.cases = []
        self.session.policy = {
            "requirements": [REQ],
            "limits": {"cases": 5},
            "adapter": {"inputs": {"/reference": "a" * 64}},
        }
        self.row = {
            "id": "one",
            "requirements": [REQ],
            "kind": "positive",
            "input": 1,
            "accepted": [1, 1.0],
            "label": {
                "status": "confirmed",
                "method": "independent reference",
                "sources": ["/reference"],
            },
        }

    def generate(self, rows, stage="initial"):
        with patch.object(self.session, "adapter", return_value={"cases": rows}):
            self.session.generate(stage)

    def test_conflicting_unknown_unmapped_and_empty_labels_do_not_pass(self):
        # [utest->req~ib-repair-cases~1]
        for change, reason in (
            ({"label": {"status": "conflict"}}, "unresolved_reference"),
            ({"label": {"status": "unknown"}}, "unresolved_reference"),
            (
                {"label": {"status": "confirmed", "method": "guess", "sources": ["/untrusted"]}},
                "unpinned",
            ),
            ({"requirements": ["req~other~1"]}, "unmapped"),
            ({"accepted": []}, "empty_accepted"),
            ({"kind": "negative_input"}, "no_positive"),
        ):
            with self.subTest(change=change), self.assertRaisesRegex(CheckError, reason):
                self.generate([{**self.row, **change}])
        with self.assertRaisesRegex(CheckError, "empty_case"):
            self.generate([])

    def test_retains_cases_without_accepting_duplicates_or_exceeding_budget(self):
        # [utest->req~ib-repair-cases~1]
        self.generate([self.row])
        with self.assertRaisesRegex(CheckError, "duplicate"):
            self.generate([self.row], "adversarial")
        with self.assertRaisesRegex(CheckError, "case_budget"):
            self.generate([{**self.row, "id": str(i)} for i in range(5)], "adversarial")
        self.assertEqual(read_json(self.session.out / "cases.json"), [self.row])

    def test_all_accepted_values_are_legal_but_unknown_is_never_success(self):
        # [utest->req~ib-repair-cases~1]
        self.generate([self.row])
        self.session.result = {"repairs": 0, "adversarial_passes": 0}
        for value in (1, 1.0):
            with patch.object(
                self.session,
                "adapter",
                return_value={
                    "observations": [{"id": "one", "status": "returned", "value": value}]
                },
            ):
                self.assertEqual(self.session.observe(), [])
        for status in ("unknown", "timeout"):
            with patch.object(
                self.session,
                "adapter",
                return_value={"observations": [{"id": "one", "status": status}]},
            ):
                with self.assertRaisesRegex(CheckError, "unresolved_observation"):
                    self.session.observe()
        with patch.object(
            self.session,
            "adapter",
            return_value={"observations": [{"id": "one", "status": "candidate_exception"}]},
        ):
            self.assertEqual(len(self.session.observe()), 1)


ADAPTER = r"""
import json
from pathlib import Path
import sys
control, request, response = sys.argv[1:]
sys.dont_write_bytecode = True
q = json.loads(Path(request).read_text())
r = {'source_sha256':q['source_sha256']}
if q['phase'] == 'generate':
    values = [1,-1] if q['stage'] == 'initial' else [-2,0]
    r['cases'] = [{'id':q['stage']+str(x),'requirements':['req~absolute-value~1'],'kind':'positive','input':x,'accepted':[abs(x)],
                  'label':{'status':'confirmed','method':'integer absolute value','sources':[str(Path(__file__).resolve())]}} for x in values]
    if control == 'unknown': r['cases'][0]['label']['status'] = 'unknown'
elif q['phase'] == 'observe':
    sys.path.insert(0,q['worktree'])
    from value import absolute
    r['observations'] = [{'id':c['id'],'status':'returned','value':absolute(c['input'])} for c in q['cases']]
elif q['phase'] == 'regression':
    r['test'] = "import json\nimport unittest\nfrom pathlib import Path\nfrom value import absolute\n# [utest~negative-value~1->req~absolute-value~1]\nclass Regression(unittest.TestCase):\n    def test_values(self):\n        for c in json.loads(Path(__file__).with_name('repair_cases.json').read_text()):\n            with self.subTest(case=c['id']):\n                self.assertIn(absolute(c['input']),c['accepted'])\n"
    r['links'] = {'test_repair.Regression.test_values':['utest~negative-value~1']}
elif q['phase'] == 'propose':
    text = (Path(q['worktree'])/'value.py').read_text()
    expression = 'abs(x)' if control != 'alternative' else 'x if x >= 0 else -x'
    if control == 'two-rounds' and q['round'] == 1: expression = '-x if x == -1 else x'
    if control == 'no-progress': expression = 'x + 0'
    if control == 'old-check-regression': expression = 'abs(x) if x < 0 else 0'
    if control == 'two-rounds' and q['round'] == 2: text = text.replace('-x if x == -1 else x','x')
    files = {'value.py':text.replace('return x\n','return '+expression+'\n')}
    if control == 'collateral': files['value.py'] += '\nSIDE_EFFECT = True\n'
    if control == 'weaken': files['tests/links.json'] = '{}'
    r['proposal'] = {'targets':['req~absolute-value~1'],'reason':'negative input counterexample','files':files}
Path(response).write_text(json.dumps(r))
"""


class RepairWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ib-repair-test-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.repo = cls.root / "original"
        cls.repo.mkdir()
        (cls.repo / "tests").mkdir()
        (cls.repo / "requirements.md").write_text(
            "### Absolute value\n`req~absolute-value~1`\n\nReturn the nonnegative absolute value of an integer.\n\nNeeds: impl, utest\n"
        )
        (cls.repo / "value.py").write_text(
            "# [impl->req~absolute-value~1]\ndef absolute(x):\n    return x\n"
        )
        (cls.repo / "tests/test_value.py").write_text(
            "import unittest\nfrom value import absolute\n# [utest~positive-value~1->req~absolute-value~1]\nclass Positive(unittest.TestCase):\n    def test_positive(self):\n        self.assertEqual(absolute(1), 1)\n"
        )
        write_json(cls.repo / "tests/links.json", {"test_value.Positive.test_positive": [OLD]})
        (cls.repo / "run_tests.py").write_text(
            "from intentbond.unittest_junit import main\nraise SystemExit(main(['--start','tests','--links','tests/links.json','--report','test-results.xml']))\n"
        )
        cls.scope = cls.root / "scope.json"
        scope = {
            "schema_version": 1,
            "name": "repair-fixture",
            "inputs": ["requirements.md", "value.py", "tests", "run_tests.py"],
            "specification_paths": ["requirements.md"],
            "test_paths": ["tests", "run_tests.py"],
            "review_paths": ["value.py"],
            "required_coverage": {"req": ["impl", "utest"]},
            "policy": {"allow_skipped_tests": False},
            "tests": {
                "format": "junit",
                "command": [sys.executable, "run_tests.py"],
                "report": "test-results.xml",
                "timeout_seconds": 8,
                "execution_links": {"format": "junit-properties-v1", "artifact_types": ["utest"]},
            },
        }
        write_json(cls.scope, scope)

        def git(*args):
            return subprocess.check_output(
                [
                    "git",
                    "-c",
                    "core.hooksPath=/dev/null",
                    "-c",
                    "init.templateDir=",
                    "-C",
                    str(cls.repo),
                    *args,
                ],
                text=True,
            ).strip()

        git("init", "-q")
        git("add", ".")
        git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@invalid.example",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "Fixture",
        )
        cls.base = git("rev-parse", "HEAD")
        cls.jar = default_jar()
        baseline = check(cls.repo, cls.scope, cls.base, cls.base, cls.root / "baseline", cls.jar)
        assert baseline["status"] == "passed", baseline
        write_json(
            cls.root / "declaration.json",
            {
                "schema_version": 1,
                "requirements": {"preserve": [REQ], "change": [], "add": [], "remove": []},
                "protected_paths": [],
                "checks": [OLD],
                "check_support_paths": ["run_tests.py"],
            },
        )
        cls.guard = prepare(
            cls.root / "baseline/evidence.json",
            cls.root / "declaration.json",
            cls.root / "guard",
            cls.repo,
            cls.base,
            cls.jar,
            scope_path=cls.scope,
        )
        cls.adapter = cls.root / "adapter.py"
        cls.adapter.write_text(ADAPTER)

    def run_repair(self, control, seconds=30, repairs=2):
        folder = self.root / f"{self._testMethodName}-{control}"
        folder.mkdir()
        value = {
            "schema_version": 1,
            "requirements": [REQ],
            "edits": [{"path": "value.py", "symbol": "absolute", "requirements": [REQ]}],
            "adapter": {
                "command": [sys.executable, str(self.adapter), control],
                "inputs": {str(self.adapter): digest(self.adapter.read_bytes())},
            },
            "regression": {
                "test_path": "tests/test_repair.py",
                "data_path": "tests/repair_cases.json",
                "links_path": "tests/links.json",
                "checks": [NEW],
            },
            "limits": {"seconds": seconds, "repairs": repairs, "cases": 10},
        }
        write_json(folder / "policy.json", value)
        result = repair(
            self.repo,
            self.scope,
            Path(self.guard["plan"]),
            self.guard["plan_sha256"],
            folder / "policy.json",
            digest((folder / "policy.json").read_bytes()),
            folder / "out",
            self.jar,
        )
        self.assertTrue(result["original_unchanged"])
        return result, folder / "out"

    def test_repairs_and_legitimate_alternatives_leave_review_pending(self):
        # [utest->req~ib-repair-loop~1]
        # [utest->req~ib-repair-regressions~1]
        for control in ("repair", "alternative", "two-rounds"):
            with self.subTest(control=control):
                result, out = self.run_repair(control)
                self.assertEqual(result["loop_status"], "passed", result)
                self.assertEqual(result["status"], "review_required")
                self.assertEqual(result["repairs"], 2 if control == "two-rounds" else 1)
                self.assertEqual(result["adversarial_passes"], 1)
                self.assertEqual(result["verification"]["status"], "matched")
                self.assertEqual(result["regression_execution"], {NEW: "passed"})
                self.assertEqual(len(read_json(out / "frozen/tests/repair_cases.json")), 4)
                self.assertEqual(
                    (out / "frozen/tests/test_value.py").read_bytes(),
                    (self.repo / "tests/test_value.py").read_bytes(),
                )
                self.assertIn(
                    "test_value.Positive.test_positive", read_json(out / "frozen/tests/links.json")
                )

    def test_scope_violations_and_repair_budget_reject(self):
        # [utest->req~ib-repair-boundaries~1]
        # [utest->req~ib-repair-loop~1]
        for control in ("collateral", "weaken", "no-progress", "old-check-regression"):
            with self.subTest(control=control):
                result, _ = self.run_repair(control, repairs=1)
                self.assertEqual(result["loop_status"], "rejected", result)
                self.assertLessEqual(result["repairs"], 1)
                if control == "old-check-regression":
                    self.assertEqual(result["reason"], "preservation_failed")

    def test_unknown_reference_and_aggregate_timeout_are_unresolved(self):
        # [utest->req~ib-repair-cases~1]
        # [utest->req~ib-repair-loop~1]
        for control, seconds in (("unknown", 30), ("repair", 0.000001)):
            result, _ = self.run_repair(control, seconds=seconds)
            self.assertEqual(result["loop_status"], "unresolved", result)
            self.assertEqual(result["repairs"], 0)

    def test_policy_rejects_wider_authority_and_requires_retained_checks(self):
        # [utest->req~ib-repair-policy~1]
        result, out = self.run_repair("unknown")
        value, plan, scope = (
            read_json(out / "policy.json"),
            read_json(Path(self.guard["plan"])),
            read_json(out / "scope.json"),
        )
        for mutate in (
            lambda v: v["requirements"].append("req~unaccepted~1"),
            lambda v: v["edits"][0].update(path="tests/test_value.py"),
            lambda v: v["limits"].update(repairs=3),
            lambda v: v["limits"].update(seconds=601),
            lambda v: v["adapter"].update(inputs={}),
            lambda v: v["regression"].update(checks=[OLD]),
        ):
            candidate = copy.deepcopy(value)
            mutate(candidate)
            with self.assertRaises(CheckError):
                policy(candidate, scope, plan)
        with self.assertRaisesRegex(CheckError, "pin mismatch"):
            repair(
                self.repo,
                self.scope,
                Path(self.guard["plan"]),
                "0" * 64,
                out / "policy.json",
                digest((out / "policy.json").read_bytes()),
                self.root / "bad-pin",
                self.jar,
            )

    def test_changed_policy_scope_plan_and_adapter_are_detected_between_phases(self):
        # [utest->req~ib-repair-policy~1]
        _, out = self.run_repair("unknown")
        policy_path = out.parent / "policy.json"
        session = Session(
            self.repo,
            self.scope,
            Path(self.guard["plan"]),
            self.guard["plan_sha256"],
            policy_path,
            digest(policy_path.read_bytes()),
            out.parent / "pin-check",
            self.jar,
            "java",
        )
        for path, message in (
            (policy_path, "repair_policy_changed"),
            (Path(self.guard["plan"]), "guard_plan_changed"),
            (self.adapter, "adapter_input_changed"),
            (self.scope, "checking_policy_changed"),
            (session.out / "scope.json", "copied_checking_policy_changed"),
        ):
            saved = path.read_bytes()
            try:
                if "scope" in path.name:
                    scope = read_json(path)
                    scope["name"] += "-changed"
                    write_json(path, scope)
                else:
                    path.write_bytes(saved + b"\n")
                with self.subTest(path=str(path)), self.assertRaisesRegex(CheckError, message):
                    session.pins()
            finally:
                path.write_bytes(saved)

    def test_input_bytes_are_rechecked_before_and_after_commands(self):
        # [utest->req~ib-repair-policy~1]
        _, out = self.run_repair("unknown")
        policy_path = out.parent / "policy.json"
        value = read_json(policy_path)
        reference, command_input = out.parent / "reference.bin", out.parent / "command.bin"
        reference.write_bytes(b"reference" * 100_000)
        command_input.write_bytes(b"")
        for path in (reference, command_input):
            value["adapter"]["inputs"][str(path)] = digest(path.read_bytes())
        write_json(policy_path, value)
        session = Session(
            self.repo,
            self.scope,
            Path(self.guard["plan"]),
            self.guard["plan_sha256"],
            policy_path,
            digest(policy_path.read_bytes()),
            out.parent / "command-pins",
            self.jar,
            "java",
        )
        outcome = {"status": "passed", "exit_code": 0}
        with patch("intentbond.repair.run", return_value=outcome) as command:
            self.assertEqual(session.command(["trusted-command"], "unchanged"), outcome)
            command.assert_called_once()
        for path in (self.adapter, reference, command_input):
            saved, metadata = path.read_bytes(), path.stat()

            def tamper(*args, **kwargs):
                # Large reference changes only at EOF; nonempty files retain size and mtime.
                path.write_bytes(saved[:-1] + bytes([saved[-1] ^ 1]) if saved else b"x")
                os.utime(path, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
                if saved:
                    self.assertEqual(path.stat().st_size, metadata.st_size)
                self.assertEqual(path.stat().st_mtime_ns, metadata.st_mtime_ns)
                return outcome

            try:
                with self.subTest(path=path.name, boundary="before"):
                    tamper()
                    with patch("intentbond.repair.run") as command:
                        with self.assertRaisesRegex(CheckError, "adapter_input_changed"):
                            session.command(["trusted-command"], "before")
                        command.assert_not_called()
                path.write_bytes(saved)
                with self.subTest(path=path.name, boundary="after"):
                    with patch("intentbond.repair.run", side_effect=tamper) as command:
                        with self.assertRaisesRegex(CheckError, "adapter_input_changed"):
                            session.command(["trusted-command"], "after")
                        command.assert_called_once()
            finally:
                path.write_bytes(saved)
                os.utime(path, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
            session.pins()


if __name__ == "__main__":
    unittest.main()
