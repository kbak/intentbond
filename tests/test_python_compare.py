"""Real Python observations of preserved requirements and permitted changes."""

import copy
import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from intentbond.cli import main, parser
from intentbond.common import CheckError, digest
from intentbond.python_compare import Comparison, compare_python, domain_values, validate_policy

REQ = "req~expiry~1"
BASE = """def state(seconds):
    return {"expired": seconds >= 1800, "label": "Sign in"}
"""


class PythonComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")
        (self.repo / "subject.py").write_text(BASE)
        self.git("add", ".")
        self.git("commit", "-qm", "accepted baseline")
        self.base = self.git("rev-parse", "HEAD").strip()
        self.policy = {
            "schema_version": 1,
            "baseline": self.base,
            "functions": [
                {
                    "id": "expiry",
                    "path": "subject.py",
                    "symbol": "state",
                    "arguments": {
                        "seconds": {
                            "type": "integer",
                            "min": 1799,
                            "max": 1801,
                            "boundaries": [1800],
                        }
                    },
                    "observations": [{"requirement": REQ, "path": ["expired"]}],
                }
            ],
            "limits": {"seconds": 30, "call_seconds": 1, "cases": 30, "shrink_steps": 0},
        }
        self.policy_path = self.root / "policy.json"
        self.count = 0

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True)

    def pin(self):
        self.policy_path.write_text(json.dumps(self.policy))
        return digest(self.policy_path.read_bytes())

    def compare(self, source=None, **kwargs):
        if source is not None:
            (self.repo / "subject.py").write_text(source)
        self.count += 1
        out = self.root / ("result-" + str(self.count))
        result = compare_python(self.repo, self.policy_path, self.pin(), out, **kwargs)
        self.assertTrue(result["execution_copies_removed"])
        self.assertFalse(result["semantic_approval"])
        self.assertFalse(list(out.glob("execution-*")))
        if source is not None:
            self.assertEqual((self.repo / "subject.py").read_text(), source)
        return result, out

    # [utest->req~ib-python-comparison-observations~1]
    def test_expiry_boundary_and_dropped_field_are_real_regressions(self):
        for source in (
            BASE.replace(">= 1800", "> 1800"),
            'def state(seconds):\n    return {"label": "Continue"}\n',
            'def state(seconds):\n    raise ValueError("broken")\n',
        ):
            result, out = self.compare(source)
            self.assertEqual(result["status"], "regression")
            self.assertTrue(result["complete"])
            cases = json.loads((out / "regressions.json").read_text())["cases"]
            self.assertTrue(cases)
            self.assertTrue(any(c["arguments"] == {"seconds": 1800} for c in cases))
            self.assertTrue(
                all(
                    row["requirements"] == [REQ]
                    for row in result["observations"]
                    if row["requirements"]
                )
            )

    # [utest->req~ib-python-comparison-observations~1]
    def test_legitimate_refactor_and_authorized_label_change_pass(self):
        result, out = self.compare(
            'def state(seconds):\n    return {"label": "Continue", "expired": not seconds < 1800}\n'
        )
        self.assertEqual(result["status"], "no_difference")
        self.assertTrue(result["complete"])
        self.assertFalse(result["counterexamples"])
        self.assertEqual(json.loads((out / "regressions.json").read_text())["cases"], [])
        # The same label change is rejected if the caller explicitly preserves it.
        self.policy["functions"][0]["observations"].append(
            {"requirement": "req~label~1", "path": ["label"]}
        )
        result, _ = self.compare()
        self.assertEqual(result["status"], "regression")
        self.assertTrue(all(r["requirements"] == ["req~label~1"] for r in result["observations"]))

    # [utest->req~ib-python-comparison-policy~1]
    def test_policy_pin_paths_schema_and_generation_bounds(self):
        pin = self.pin()
        with self.assertRaisesRegex(CheckError, "pin mismatch"):
            compare_python(self.repo, self.policy_path, "0" * 64, self.root / "bad")
        with self.assertRaisesRegex(CheckError, "outside source"):
            compare_python(self.repo, self.policy_path, pin, self.repo / "evidence")
        for mutate in (
            lambda p: p.update(baseline="HEAD"),
            lambda p: p.update(extra=True),
            lambda p: p.update(schema_version=True),
            lambda p: p["functions"][0].update(path="../outside.py"),
            lambda p: p["functions"][0].update(observations=[]),
            lambda p: p["functions"][0]["observations"][0].update(path=[-1]),
            lambda p: p["limits"].update(cases=1),
            lambda p: p["limits"].update(seconds=float("nan")),
            lambda p: p["functions"][0]["arguments"]["seconds"].update(min=True),
            lambda p: p["functions"][0].update(arguments={"x": {"type": "enum", "values": [1, 1]}}),
        ):
            changed = copy.deepcopy(self.policy)
            mutate(changed)
            with self.assertRaises((CheckError, ValueError)):
                validate_policy(changed)
        self.policy_path.write_text('{"schema_version":1,"schema_version":1}')
        with self.assertRaisesRegex(CheckError, "Duplicate JSON key"):
            compare_python(
                self.repo,
                self.policy_path,
                digest(self.policy_path.read_bytes()),
                self.root / "duplicate",
            )

    # [utest->req~ib-python-comparison-observations~1]
    def test_unicode_name_regression_and_equivalent_normalization(self):
        baseline = 'def state(name):\n    return {"valid": bool(name.strip()), "display": name}\n'
        (self.repo / "subject.py").write_text(baseline)
        self.git("add", ".")
        self.git("commit", "-qm", "accepted Unicode names")
        self.policy["baseline"] = self.git("rev-parse", "HEAD").strip()
        function = self.policy["functions"][0]
        function.update(
            arguments={"name": {"type": "enum", "values": ["", " ", "\u00a0", "\t", "Zoë"]}},
            observations=[{"requirement": "req~valid-name~1", "path": ["valid"]}],
        )
        result, out = self.compare(baseline.replace("name.strip()", 'name.strip(" ")'))
        self.assertEqual(result["status"], "regression")
        cases = json.loads((out / "regressions.json").read_text())["cases"]
        self.assertEqual({c["arguments"]["name"] for c in cases}, {"\u00a0", "\t"})
        legitimate = 'def state(name):\n    clean = name.strip()\n    return {"valid": clean != "", "display": clean}\n'
        result, _ = self.compare(legitimate)
        self.assertEqual(result["status"], "no_difference")

    # [utest->req~ib-python-comparison-policy~1]
    # [utest->req~ib-python-comparison-observations~1]
    def test_cartesian_interaction_and_nested_projection(self):
        baseline = 'def state(age, mode):\n    return {"access": [age >= 18 and mode == "full"], "label": "old"}\n'
        (self.repo / "subject.py").write_text(baseline)
        self.git("add", ".")
        self.git("commit", "-qm", "accepted access rule")
        self.policy["baseline"] = self.git("rev-parse", "HEAD").strip()
        self.policy["functions"][0].update(
            arguments={
                "age": {"type": "integer", "min": 17, "max": 19, "boundaries": [18]},
                "mode": {"type": "enum", "values": ["guest", "full"]},
            },
            observations=[{"requirement": "req~access~1", "path": ["access", 0]}],
        )
        result, out = self.compare(baseline.replace(">= 18", "> 18"))
        self.assertEqual(result["status"], "regression")
        self.assertEqual(result["scheduled_cases"], 6)
        cases = json.loads((out / "regressions.json").read_text())["cases"]
        self.assertEqual([c["arguments"] for c in cases], [{"age": 18, "mode": "full"}])
        result, _ = self.compare(baseline.replace('"old"', '"new"'))
        self.assertEqual(result["status"], "no_difference")

    # [utest->req~ib-python-comparison-retention~1]
    def test_retention_and_replay_preserve_json_type_distinctions(self):
        baseline = "def state(value):\n    return value\n"
        (self.repo / "subject.py").write_text(baseline)
        self.git("add", ".")
        self.git("commit", "-qm", "accepted identity")
        self.policy["baseline"] = self.git("rev-parse", "HEAD").strip()
        self.policy["functions"][0].update(
            arguments={"value": {"type": "enum", "values": [True, 1, 1.0]}},
            observations=[{"requirement": "req~identity~1", "path": []}],
        )
        result, out = self.compare("def state(value):\n    return None\n")
        self.assertEqual(result["status"], "regression")
        cases = json.loads((out / "regressions.json").read_text())["cases"]
        self.assertEqual([type(c["arguments"]["value"]) for c in cases], [bool, int, float])
        replay, _ = self.compare(
            baseline, replay=out / "regressions.json", replay_sha256=result["regressions_sha256"]
        )
        self.assertEqual(replay["status"], "no_difference")
        self.assertEqual(replay["scheduled_cases"], 3)

    # [utest->req~ib-python-comparison-observations~1]
    def test_argument_mutation_is_unresolved(self):
        baseline = "def state(values):\n    return len(values)\n"
        (self.repo / "subject.py").write_text(baseline)
        self.git("add", ".")
        self.git("commit", "-qm", "accepted list input")
        self.policy["baseline"] = self.git("rev-parse", "HEAD").strip()
        self.policy["functions"][0].update(
            arguments={"values": {"type": "enum", "values": [[1, 2]]}},
            observations=[{"requirement": "req~length~1", "path": []}],
        )
        result, _ = self.compare(
            "def state(values):\n    values.append(3)\n    return len(values)\n"
        )
        self.assertEqual(result["status"], "unresolved")
        self.assertFalse(result["complete"])
        self.assertIn("mutated an argument", " ".join(result["diagnostics"]))

    # [utest->req~ib-python-comparison-retention~1]
    def test_deadline_during_reduction_keeps_known_failure_incomplete(self):
        self.policy["limits"]["shrink_steps"] = 10
        minimize = Comparison.minimize

        def expire(comparison, function, original):
            comparison.deadline = 0
            return minimize(comparison, function, original)

        with patch.object(Comparison, "minimize", expire):
            result, out = self.compare(BASE.replace(">= 1800", "> 1800"))
        self.assertEqual(result["status"], "unresolved")
        self.assertFalse(result["complete"])
        self.assertIn("deadline exhausted", " ".join(result["diagnostics"]))
        cases = json.loads((out / "regressions.json").read_text())["cases"]
        self.assertEqual([c["arguments"] for c in cases], [{"seconds": 1800}])

    # [utest->req~ib-python-comparison-observations~1]
    def test_unavailable_invalid_and_timeout_observations_do_not_pass(self):
        for source, fragment in (
            ("async def state(seconds):\n    return {}\n", "Unresolved Python"),
            ('def state(seconds):\n    return float("nan")\n', "Unresolved Python"),
            ("def state(seconds):\n    while True: pass\n", "timed out"),
            ("def other(seconds):\n    return {}\n", "Unresolved Python"),
        ):
            result, _ = self.compare(source)
            self.assertEqual(result["status"], "unresolved")
            self.assertFalse(result["complete"])
            self.assertIn(fragment, " ".join(result["diagnostics"]))

    # [utest->req~ib-python-comparison-observations~1]
    def test_file_and_directory_prefix_accepts_edits_but_still_detects_tampering(self):
        (self.repo / "subject").mkdir()
        (self.repo / "subject/helper.py").write_text("flag = True\n")
        self.git("add", ".")
        self.git("commit", "-qm", "module and directory with matching prefix")
        self.policy["baseline"] = self.git("rev-parse", "HEAD").strip()
        result, _ = self.compare(BASE.replace("Sign in", "Continue"))
        self.assertEqual(result["status"], "no_difference")
        self.assertTrue(result["complete"])
        result, _ = self.compare(BASE.replace(">= 1800", "> 1800"))
        self.assertEqual(result["status"], "regression")
        result, _ = self.compare(
            BASE.replace(
                "def state(seconds):",
                'from pathlib import Path\ndef state(seconds):\n    Path("subject/helper.py").write_text("flag = False\\n")',
            )
        )
        self.assertEqual(result["status"], "unresolved")
        self.assertFalse(result["complete"])
        self.assertIn("Executed source changed", result["diagnostics"])
        self.assertEqual((self.repo / "subject/helper.py").read_text(), "flag = True\n")

    # [utest->req~ib-python-comparison-observations~1]
    def test_cleanup_failure_cannot_leave_a_completed_result(self):
        class FailedCleanup(tempfile.TemporaryDirectory):
            def cleanup(self):
                super().cleanup()
                raise OSError("Execution-copy cleanup failed")

        with patch("intentbond.python_compare.tempfile.TemporaryDirectory", FailedCleanup):
            result, _ = self.compare()
        self.assertEqual(result["status"], "unresolved")
        self.assertFalse(result["complete"])
        self.assertIn("Execution-copy cleanup failed", result["diagnostics"])

    # [utest->req~ib-python-comparison-observations~1]
    def test_nondeterministic_baseline_and_source_mutation_are_unresolved(self):
        (self.repo / "subject.py").write_text(
            'import time\ndef state(seconds):\n    return {"expired": time.time_ns()}\n'
        )
        self.git("add", ".")
        self.git("commit", "-qm", "unstable control")
        self.policy["baseline"] = self.git("rev-parse", "HEAD").strip()
        result, _ = self.compare()
        self.assertEqual(result["status"], "unresolved")
        self.assertIn("Unstable", " ".join(result["diagnostics"]))
        self.policy["baseline"] = self.base
        result, _ = self.compare(
            'from pathlib import Path\ndef state(seconds):\n    Path("added.txt").write_text("changed")\n    return {"expired": seconds >= 1800}\n'
        )
        self.assertEqual(result["status"], "unresolved")
        self.assertIn("Executed source changed", result["diagnostics"])
        self.assertFalse((self.repo / "added.txt").exists())

    # [utest->req~ib-python-comparison-observations~1]
    def test_baseline_exception_and_missing_projection_are_unresolved(self):
        for source in (
            'def state(seconds):\n    raise ValueError("unsupported domain")\n',
            "def state(seconds):\n    return {}\n",
        ):
            (self.repo / "subject.py").write_text(source)
            self.git("add", ".")
            self.git("commit", "-qm", "baseline control")
            self.policy["baseline"] = self.git("rev-parse", "HEAD").strip()
            result, _ = self.compare(BASE)
            self.assertEqual(result["status"], "unresolved")
            self.assertIn("Baseline cannot establish", " ".join(result["diagnostics"]))

    # [utest->req~ib-python-comparison-retention~1]
    def test_retained_cases_replay_reject_stale_labels_and_detect_reintroduction(self):
        bad = BASE.replace(">= 1800", "> 1800")
        result, out = self.compare(bad)
        replay = out / "regressions.json"
        options = {"replay": replay, "replay_sha256": result["regressions_sha256"]}
        fixed, fixed_out = self.compare(BASE, **options)
        self.assertEqual(fixed["status"], "no_difference")
        self.assertEqual(fixed["mode"], "replay")
        self.assertEqual(fixed["shrink_evaluations"], 0)
        self.assertEqual(
            json.loads(replay.read_text()), json.loads((fixed_out / "regressions.json").read_text())
        )
        again, _ = self.compare(bad, **options)
        self.assertEqual(again["status"], "regression")
        with self.assertRaisesRegex(CheckError, "pin mismatch"):
            self.compare(BASE, replay=replay, replay_sha256="0" * 64)
        forged = json.loads(replay.read_text())
        forged["cases"][0]["expected"][0]["value"] = False
        fake = self.root / "forged.json"
        fake.write_text(json.dumps(forged))
        answer, _ = self.compare(BASE, replay=fake, replay_sha256=digest(fake.read_bytes()))
        self.assertEqual(answer["status"], "unresolved")
        self.assertIn("Retained expectation differs", " ".join(answer["diagnostics"]))

    # [utest->req~ib-python-comparison-retention~1]
    def test_reduction_keeps_reproducing_failure_without_global_minimum_claim(self):
        self.policy["functions"][0]["arguments"]["seconds"] = {
            "type": "integer",
            "min": 0,
            "max": 100,
            "boundaries": [],
        }
        self.policy["limits"]["shrink_steps"] = 30
        # Independent expected counterexample: the threshold is five, not a generated seed.
        (self.repo / "subject.py").write_text(BASE.replace("1800", "5"))
        self.git("add", ".")
        self.git("commit", "-qm", "threshold five")
        self.policy["baseline"] = self.git("rev-parse", "HEAD").strip()
        result, out = self.compare('def state(seconds):\n    return {"expired": False}\n')
        self.assertEqual(result["status"], "regression")
        self.assertEqual(result["counterexamples"][0]["reduced"]["arguments"], {"seconds": 5})
        self.assertIn("no global minimum", result["counterexamples"][0]["minimality"])
        self.assertLessEqual(result["shrink_evaluations"], 30)
        self.assertTrue(
            any(
                c["arguments"] == {"seconds": 5}
                for c in json.loads((out / "regressions.json").read_text())["cases"]
            )
        )

    # [utest->req~ib-python-comparison-policy~1]
    # [utest->req~ib-python-comparison-observations~1]
    def test_real_cli_is_opt_in_and_existing_parser_defaults_stay_unchanged(self):
        (self.repo / "subject.py").write_text(BASE.replace(">= 1800", "> 1800"))
        pin = self.pin()
        args = [
            "compare-python",
            "--repo",
            str(self.repo),
            "--policy",
            str(self.policy_path),
            "--policy-sha256",
            pin,
            "--out",
            str(self.root / "cli"),
        ]
        with redirect_stdout(io.StringIO()) as text:
            status = main(args)
        self.assertEqual(status, 1)
        self.assertEqual(json.loads(text.getvalue())["status"], "regression")
        old = parser().parse_args(["check"])
        self.assertEqual(old.action, "check")
        self.assertEqual(old.candidate, "worktree")
        self.assertFalse(hasattr(old, "policy_sha256"))

    # [utest->req~ib-python-comparison-policy~1]
    def test_integer_generation_has_independently_stated_boundaries(self):
        actual = domain_values({"type": "integer", "min": -5, "max": 20, "boundaries": [10]})
        self.assertTrue({-5, -4, 0, 9, 10, 11, 19, 20} <= set(actual))
        self.assertEqual(len(actual), len(set(actual)))
        self.assertTrue(all(-5 <= n <= 20 for n in actual))

    # [utest->req~ib-python-comparison-observations~1]
    def test_changed_original_source_and_trusted_policy_cannot_complete(self):
        observe = Comparison.observe
        for target in ("source", "policy"):

            def change(session, source, function, arguments):
                result = observe(session, source, function, arguments)
                if source is session.sources["candidate"]:
                    if target == "source":
                        (self.repo / "new.txt").write_text("external concurrent edit")
                    else:
                        self.policy_path.write_text(self.policy_path.read_text() + " ")
                return result

            with patch.object(Comparison, "observe", change):
                result, _ = self.compare()
            self.assertEqual(result["status"], "unresolved")
            self.assertFalse(result["complete"])


if __name__ == "__main__":
    unittest.main()
