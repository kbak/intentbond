"""Reviewed-contract failures drive real bounded repair and retained native tests."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_validation_contract import contract as nested_contract
from test_validation_contract import valid_options

from intentbond.change_guard import prepare
from intentbond.common import CheckError, digest, read_json, write_json
from intentbond.oft import default_jar
from intentbond.repair import repair
from intentbond.runner import check
from intentbond.validation_repair import (
    answer,
    encoded,
    load_config,
    observe_case,
    prepare_validation_repair,
    repair_cases,
)

REQ = "req~timeout-validation~1"
OLD = "utest~timeout-interior~1"
NEW = "utest~timeout-contract~1"
GOOD = "    if type(value) is not int or not 1 <= value <= 7000:\n        raise ValueError('timeout')\n    return value\n"
ALTERNATIVE = "    if type(value) is int and value > 0 and value < 7001:\n        return value\n    raise ValueError('choose an integer')\n"
HEADER = "# [impl->req~timeout-validation~1]\ndef validate(value):\n"
TAIL = "\n\ndef marker():\n    return 'preserved'\n"
ACTOR = """import json, sys
from pathlib import Path
mode, request, response = sys.argv[1:]
q = json.loads(Path(request).read_text())
if mode == 'partial': sys.exit(0)
source = Path(q['worktree'])/'settings.py'
before = source.read_text()
body = {good!r} if mode != 'alternative' else {alternative!r}
text = before.split('def validate(value):\\n')[0] + 'def validate(value):\\n' + body + before[before.index('\\n\\ndef marker'):]
if mode == 'collateral': text += '\\nUNWANTED = True\\n'
files = {{'settings.py': text}}
if mode == 'old-test': files['tests/test_settings.py'] = ''
if mode == 'restore': files['settings.py'] = text.replace('<= 7000', '<= 6000')
r = {{'source_sha256':q['source_sha256'], 'proposal':{{'targets':[{req!r}], 'reason':'Repair the declared validation failure', 'files':files}}}}
Path(response).write_text(json.dumps(r))
""".format(good=GOOD, alternative=ALTERNATIVE, req=REQ)


def scalar_contract():
    return {
        "schema_version": 1,
        "requirement": REQ,
        "preserve_input": True,
        "output": "normalized",
        "rejection": "ValueError",
        "input": {"type": "integer", "nullable": False, "min": 1, "max": 7000},
    }


class ValidationAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.contract = self.root / "contract.json"
        write_json(self.contract, scalar_contract())
        self.actor = self.root / "actor.py"
        self.actor.write_text("raise RuntimeError('Preparation must not execute an actor')\n")

    def configure(self, **kwargs):
        return prepare_validation_repair(
            self.contract,
            kwargs.pop("pin", digest(self.contract.read_bytes())),
            module="not_imported",
            function="validate",
            proposer={
                "command": [sys.executable, str(self.actor)],
                "inputs": {str(self.actor): digest(self.actor.read_bytes())},
            },
            out=self.root / "prepared",
            max_cases=kwargs.pop("max_cases", 16),
            **kwargs,
        )

    def config(self):
        adapter = self.configure()
        return load_config(*adapter["command"][-2:])

    def test_freezes_once_splits_without_duplicating_and_refuses_changed_cases(self):
        # [utest->req~ib-validation-repair-preparation~1]
        config = self.config()
        request = {
            "schema_version": 1,
            "source_sha256": "source",
            "requirements": [REQ],
            "phase": "generate",
            "stage": "initial",
            "cases": [],
        }
        first = answer(config, request)["cases"]
        second = answer(config, {**request, "stage": "adversarial", "cases": first})["cases"]
        self.assertEqual(first + second, repair_cases(config))
        self.assertEqual(len({c["id"] for c in first + second}), len(config["cases"]))
        self.assertTrue(any(c["kind"] == "positive" for c in first))
        self.assertTrue(any(c["kind"] == "negative_input" for c in first))
        for changed in (first[:-1], first + first[:1], []):
            with self.assertRaises(CheckError):
                answer(config, {**request, "stage": "adversarial", "cases": changed})
        with self.assertRaises(CheckError):
            answer(config, {**request, "requirements": ["req~other~1"]})

    def test_stale_contract_config_actor_and_insufficient_cap_refuse(self):
        # [utest->req~ib-validation-repair-preparation~1]
        for options in (
            {"pin": "0" * 64},
            {"max_cases": 2},
            {"max_cases": 1001},
            {"max_cases": True},
        ):
            with self.subTest(options=options), self.assertRaises(CheckError):
                self.configure(**options)
            self.assertFalse((self.root / "prepared").exists())
        adapter = self.configure()
        path, sha = adapter["command"][-2:]
        for file in (Path(path), self.contract, self.actor):
            original = file.read_bytes()
            try:
                file.write_bytes(original + b" ")
                with self.assertRaises(CheckError):
                    load_config(path, sha)
            finally:
                file.write_bytes(original)

    def test_independent_nested_validators_and_mutation_on_rejection(self):
        # [utest->req~ib-validation-repair-execution~1]
        write_json(self.contract, nested_contract())
        adapter = self.configure(max_cases=512)
        config = load_config(*adapter["command"][-2:])
        for target in (valid_options, lambda v: dict(reversed(list(valid_options(v).items())))):
            for case in repair_cases(config):
                observed = observe_case(target, case)
                self.assertEqual(observed["status"], "returned")
                self.assertIn(encoded(observed["value"]), [encoded(v) for v in case["accepted"]])
        row = next(
            c
            for c in repair_cases(config)
            if c["input"]["value"] == {} and c["kind"] == "negative_input"
        )

        def mutating(v):
            v["new"] = 1
            raise ValueError("bad")

        self.assertNotIn(
            encoded(observe_case(mutating, row)["value"]), [encoded(v) for v in row["accepted"]]
        )

    def test_proposer_alias_cannot_redirect_execution_past_its_pin(self):
        # [utest->req~ib-validation-repair-preparation~1]
        original = self.actor
        alias = self.root / "actor-alias.py"
        alias.symlink_to(original)
        self.actor = alias
        adapter = self.configure()
        other = self.root / "other.py"
        other.write_text("raise RuntimeError('unreviewed actor')\n")
        alias.unlink()
        alias.symlink_to(other)
        with self.assertRaises(CheckError):
            load_config(*adapter["command"][-2:])

    def test_wrong_types_unexpected_exceptions_and_async_cannot_pass(self):
        # [utest->req~ib-validation-repair-execution~1]
        rows = repair_cases(self.config())
        positive = next(c for c in rows if c["kind"] == "positive")

        class IntSubclass(int):
            pass

        for target in (lambda v: True, lambda v: float(v), lambda v: IntSubclass(v)):
            self.assertNotIn(
                encoded(observe_case(target, positive)["value"]),
                [encoded(v) for v in positive["accepted"]],
            )
        rejected = next(c for c in rows if c["input"]["value"] is None)

        def unexpected(v):
            raise TypeError("wrong exception")

        self.assertEqual(observe_case(unexpected, rejected)["value"]["outcome"], "exception")

        async def asynchronous(v):
            return v

        self.assertEqual(observe_case(asynchronous, positive)["status"], "unknown")


class NativeValidationRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ib-validation-repair-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.repo = cls.root / "repo"
        cls.repo.mkdir()
        (cls.repo / "tests").mkdir()
        (cls.repo / "requirements.md").write_text(
            f"### Timeout\n`{REQ}`\n\nAccept strict integers 1 through 7000 inclusive, reject other values with ValueError, return accepted values unchanged and preserve inputs. Keep marker behavior. The implementation still has the previous 6000 limit; restoring it does not satisfy the requested 7000 limit.\n\nNeeds: impl, utest\n"
        )
        cls.stale = HEADER + GOOD.replace("<= 7000", "<= 6000") + TAIL
        (cls.repo / "settings.py").write_text(cls.stale)
        (cls.repo / "tests/test_settings.py").write_text(
            f"import unittest\nfrom settings import validate, marker\n# [{OLD}->{REQ}]\nclass Interior(unittest.TestCase):\n    def test_value(self):\n        self.assertEqual(validate(1000),1000)\n        self.assertEqual(marker(),'preserved')\n"
        )
        write_json(cls.repo / "tests/links.json", {"test_settings.Interior.test_value": [OLD]})
        (cls.repo / "run_tests.py").write_text(
            "from intentbond.unittest_junit import main\nraise SystemExit(main(['--start','tests','--links','tests/links.json','--report','test-results.xml']))\n"
        )
        cls.scope = cls.root / "scope.json"
        write_json(
            cls.scope,
            {
                "schema_version": 1,
                "name": "validation-repair",
                "inputs": ["requirements.md", "settings.py", "tests", "run_tests.py"],
                "specification_paths": ["requirements.md"],
                "test_paths": ["tests", "run_tests.py"],
                "review_paths": ["settings.py"],
                "required_coverage": {"req": ["impl", "utest"]},
                "policy": {"allow_skipped_tests": False},
                "tests": {
                    "format": "junit",
                    "command": [sys.executable, "-B", "run_tests.py"],
                    "report": "test-results.xml",
                    "timeout_seconds": 8,
                    "execution_links": {
                        "format": "junit-properties-v1",
                        "artifact_types": ["utest"],
                    },
                },
            },
        )

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
        result = check(cls.repo, cls.scope, cls.base, cls.base, cls.root / "baseline", cls.jar)
        assert result["status"] == "passed", result
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
        cls.actor = cls.root / "actor.py"
        cls.actor.write_text(ACTOR)
        cls.contract = cls.root / "contract.json"
        write_json(cls.contract, scalar_contract())

    def run_case(self, mode="repair", source=None, repairs=1, seconds=30, case_cap=16):
        folder = Path(tempfile.mkdtemp(prefix="case-", dir=self.root))
        adapter = prepare_validation_repair(
            self.contract,
            digest(self.contract.read_bytes()),
            module="settings",
            function="validate",
            proposer={
                "command": [sys.executable, "-B", str(self.actor), mode],
                "inputs": {str(self.actor): digest(self.actor.read_bytes())},
            },
            out=folder / "prepared",
            max_cases=16,
        )
        policy = {
            "schema_version": 1,
            "requirements": [REQ],
            "edits": [{"path": "settings.py", "symbol": "validate", "requirements": [REQ]}],
            "adapter": adapter,
            "regression": {
                "test_path": "tests/test_generated.py",
                "data_path": "tests/validation_cases.json",
                "links_path": "tests/links.json",
                "checks": [NEW],
            },
            "limits": {"seconds": seconds, "repairs": repairs, "cases": case_cap},
        }
        write_json(folder / "policy.json", policy)
        (self.repo / "settings.py").write_text(self.stale if source is None else source)
        before = (self.repo / "settings.py").read_bytes()
        try:
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
            self.assertEqual((self.repo / "settings.py").read_bytes(), before)
        finally:
            (self.repo / "settings.py").write_text(self.stale)
        return result, folder / "out"

    def test_new_requirement_repairs_localized_and_retains_regression(self):
        # [utest->req~ib-validation-repair-execution~1]
        result, out = self.run_case()
        self.assertEqual(result["loop_status"], "passed", result)
        self.assertEqual(result["status"], "review_required")
        self.assertEqual(result["repairs"], 1)
        self.assertEqual(result["regression_execution"], {NEW: "passed"})
        self.assertEqual(result["verification"]["status"], "matched")
        request = read_json(next(out.glob("adapter-*-propose/request.json")))
        failure = request["failures"][0]
        self.assertEqual(failure["case"]["input"]["value"], 7000)
        self.assertEqual(
            failure["case"]["accepted"], [{"outcome": "accept", "value": 7000, "input": 7000}]
        )
        self.assertEqual(failure["observed"]["value"], {"outcome": "reject", "input": 7000})
        self.assertEqual(
            (out / "frozen/requirements.md").read_bytes(),
            (self.repo / "requirements.md").read_bytes(),
        )
        self.assertEqual(
            (out / "frozen/tests/test_settings.py").read_bytes(),
            (self.repo / "tests/test_settings.py").read_bytes(),
        )
        self.assertEqual((out / "frozen/settings.py").read_text(), HEADER + GOOD + TAIL)
        self.assertEqual(
            len(read_json(out / "frozen/tests/validation_cases.json")), result["cases"]
        )
        later = out.parent / "later"
        shutil.copytree(out / "frozen", later)
        (later / "settings.py").write_text(self.stale)
        rerun = subprocess.run(
            [sys.executable, "-B", "run_tests.py"], cwd=later, capture_output=True
        )
        self.assertNotEqual(rerun.returncode, 0)
        self.assertIn(b"7000", rerun.stdout + rerun.stderr)

    def test_legitimate_alternatives_pass_without_repair_and_valid_repair_passes(self):
        # [utest->req~ib-validation-repair-execution~1]
        for body in (GOOD, ALTERNATIVE):
            result, out = self.run_case(source=HEADER + body + TAIL)
            self.assertEqual(result["loop_status"], "passed", result)
            self.assertEqual(result["repairs"], 0)
            self.assertFalse(list(out.glob("adapter-*-propose")))
        result, _ = self.run_case(mode="alternative")
        self.assertEqual(result["loop_status"], "passed", result)

    def test_unwanted_changes_and_baseline_restoration_do_not_pass(self):
        # [utest->req~ib-validation-repair-execution~1]
        for mode in ("collateral", "old-test", "restore"):
            result, _ = self.run_case(mode=mode)
            self.assertEqual(result["loop_status"], "rejected", result)
            self.assertEqual(result["reason"], "repair_scope_violation")

    def test_reserved_boundary_failure_triggers_repair_and_is_retained(self):
        # [utest->req~ib-validation-repair-execution~1]
        source = HEADER + GOOD.replace("not 1 <= value <= 7000", "value < 1") + TAIL
        result, out = self.run_case(source=source)
        self.assertEqual(result["loop_status"], "passed", result)
        self.assertEqual(result["repairs"], 1)
        self.assertEqual(result["adversarial_passes"], 1)
        self.assertEqual(read_json(out / "failures-0-0.json"), [])
        failures = read_json(out / "failures-0-1.json")
        self.assertEqual([f["case"]["input"]["value"] for f in failures], [7001])
        retained = read_json(out / "frozen/tests/validation_cases.json")
        self.assertIn(failures[0]["case"], retained)
        self.assertEqual(result["regression_execution"], {NEW: "passed"})

    def test_partial_unknown_and_exhausted_budgets_never_complete(self):
        # [utest->req~ib-validation-repair-execution~1]
        controls = [
            {"mode": "partial"},
            {"repairs": 0},
            {"seconds": 0.000001},
            {"case_cap": 2},
            {
                "source": HEADER
                + "    return async_value(value) if value == 1 else value\n"
                + TAIL
                + "\nasync def async_value(value):\n    return value\n"
            },
        ]
        for options in controls:
            result, out = self.run_case(**options)
            self.assertIn(result["loop_status"], ("unresolved", "rejected"), result)
            self.assertEqual(result["repairs"], 0)
            if options.get("mode") != "partial":
                self.assertFalse(list(out.glob("adapter-*-propose")))


if __name__ == "__main__":
    unittest.main()
