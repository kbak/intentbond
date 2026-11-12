"""Requested changes need their own source-bound evidence, even when behavior passes."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import test_repair as fixtures
from test_repair import NEW, REQ

from intentbond.common import CheckError, digest, read_json, write_json
from intentbond.repair import Session, identity, policy

CHECKER = r"""
import json, sys, time
from pathlib import Path
mode, request, response = sys.argv[1:]
q = json.loads(Path(request).read_text())
source = Path(q['worktree'])/'value.py'
passed = 'result =' in source.read_text()
r = {'schema_version':1, **{k:q[k] for k in ('source_sha256','request_sha256','checker_sha256')},
     'status':'passed' if passed else 'failed', 'errors':[] if passed else ['Use a local result before returning it.']}
if mode in ('source_sha256','request_sha256','checker_sha256'): r[mode] = 'stale'
if mode == 'missing': sys.exit()
if mode == 'malformed': Path(response).write_text('not json'); sys.exit()
if mode == 'partial': r['status'] = 'partial'
if mode == 'empty_failure': r.update(status='failed', errors=[])
if mode == 'contradiction': r.update(status='passed', errors=['not done'])
if mode == 'schema_bool': r['schema_version'] = True
if mode == 'exit': sys.exit(1)
if mode == 'timeout': time.sleep(5)
if mode == 'mutate_source': source.write_text(source.read_text()+'\nCHANGED = True\n')
if mode == 'mutate_request': Path(q['request']).write_text('Changed authority')
Path(response).write_text(json.dumps(r))
"""


class CompletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.RepairWorkflowTests.setUpClass.__func__(cls)
        # Behavior is already correct. Only the requested refactor is missing.
        p = cls.repo / "value.py"
        p.write_text(p.read_text().replace("return x", "return abs(x)"))
        cls.adapter.write_text(
            cls.adapter.read_text().replace(
                "text.replace('return x\\n','return '+expression+'\\n')",
                "text.replace('return abs(x)\\n', 'result = abs(x)\\n    return result\\n')",
            )
        )
        cls.checker = cls.root / "completion.py"
        cls.checker.write_text(CHECKER)
        cls.request = cls.root / "CHANGE.txt"
        cls.request.write_text("Use a local result before returning it; preserve absolute values.")

    def session(self, mode="normal", *, control="repair", enabled=True, repairs=2):
        folder = self.root / f"{self._testMethodName}-{mode}-{control}"
        folder.mkdir()
        value = {
            "schema_version": 1,
            "requirements": [REQ],
            "edits": [{"path": "value.py", "symbol": "absolute", "requirements": [REQ]}],
            "adapter": {
                "command": [sys.executable, "-B", str(self.adapter), control],
                "inputs": {str(self.adapter): digest(self.adapter.read_bytes())},
            },
            "regression": {
                "test_path": "tests/test_repair.py",
                "data_path": "tests/repair_cases.json",
                "links_path": "tests/links.json",
                "checks": [NEW],
            },
            "limits": {"seconds": 30, "repairs": repairs, "cases": 10},
        }
        if enabled:
            value["completion"] = {
                "request": str(self.request),
                "command": [sys.executable, "-B", str(self.checker), mode],
                "inputs": {str(p): digest(p.read_bytes()) for p in (self.request, self.checker)},
            }
        path = folder / "policy.json"
        write_json(path, value)
        return Session(
            self.repo,
            self.scope,
            Path(self.guard["plan"]),
            self.guard["plan_sha256"],
            path,
            digest(path.read_bytes()),
            folder / "out",
            self.jar,
            "java",
        )

    def test_noop_is_repaired_and_bound_to_the_final_source(self):
        # [utest->req~ib-repair-completion~1]
        session = self.session()
        result = session.execute()
        self.assertEqual(result["loop_status"], "passed", result)
        self.assertEqual(result["status"], "review_required")
        self.assertEqual(result["repairs"], 1)
        self.assertEqual(result["completion"]["status"], "passed")
        self.assertEqual(result["completion"]["source_sha256"], result["candidate"]["sha256"])
        self.assertEqual(result["verification"]["status"], "matched")
        first = read_json(session.out / "completion-0/response.json")
        self.assertEqual(first["status"], "failed")
        requests = list(session.out.glob("adapter-*-propose/request.json"))
        self.assertEqual(len(requests), 1)
        feedback = read_json(requests[0])["failures"][0]
        self.assertEqual(feedback["case"]["input"]["request"], self.request.read_text())
        self.assertTrue(result["original_unchanged"])
        self.assertLess(result["elapsed_seconds"], 30)

    def test_no_repair_budget_rejects_ignored_request(self):
        # [utest->req~ib-repair-completion~1]
        result = self.session(repairs=0).execute()
        self.assertEqual(result["loop_status"], "rejected")
        self.assertEqual(result["reason"], "repair_budget_exhausted")
        self.assertEqual(result["completion"]["status"], "failed")
        self.assertEqual(result["repairs"], 0)

    def test_omitted_option_keeps_the_original_behavior_and_schema(self):
        # [utest->req~ib-repair-completion~1]
        session = self.session(enabled=False)
        result = session.execute()
        self.assertEqual(result["loop_status"], "passed")
        self.assertEqual(result["repairs"], 0)
        self.assertNotIn("completion", result)
        self.assertFalse(list(session.out.glob("completion-*")))

    def test_completion_feedback_does_not_authorize_other_paths(self):
        # [utest->req~ib-repair-completion~1]
        result = self.session(control="collateral").execute()
        self.assertEqual(result["loop_status"], "rejected")
        self.assertEqual(result["reason"], "repair_scope_violation")
        self.assertEqual(result["repairs"], 0)

    def test_bad_or_stale_completion_evidence_remains_unresolved(self):
        # [utest->req~ib-repair-completion~1]
        for mode in (
            "source_sha256",
            "request_sha256",
            "checker_sha256",
            "missing",
            "malformed",
            "partial",
            "empty_failure",
            "contradiction",
            "schema_bool",
            "exit",
            "timeout",
            "mutate_source",
            "mutate_request",
        ):
            with self.subTest(mode=mode):
                session = self.session(mode)
                shutil.copytree(self.repo, session.work)
                session.expected_source = identity(session.work)["sha256"]
                if mode == "timeout":
                    session.deadline = session.started + 0.2
                try:
                    with self.assertRaises((CheckError, ValueError)):
                        session.completion(0)
                    self.assertEqual(session.result["completion"]["status"], "unresolved")
                finally:
                    self.request.write_text(
                        "Use a local result before returning it; preserve absolute values."
                    )

    def test_completion_policy_requires_pinned_external_authority(self):
        # [utest->req~ib-repair-completion~1]
        session = self.session()
        original = read_json(session.policy_path)
        for key in ("request", "command", "inputs"):
            with self.subTest(missing=key):
                value = read_json(session.policy_path)
                del value["completion"][key]
                with self.assertRaises(CheckError):
                    policy(value, session.scope, session.plan)
        value = read_json(session.policy_path)
        del value["completion"]["inputs"][str(self.request)]
        with self.assertRaises(CheckError):
            policy(value, session.scope, session.plan)
        for path in (self.request, self.checker):
            old = path.read_bytes()
            try:
                path.write_bytes(old + b"\n")
                with self.assertRaisesRegex(CheckError, "completion_input_changed"):
                    session.pins()
            finally:
                path.write_bytes(old)
        self.assertEqual(session.policy, original)

    def test_valid_absolute_request_spelling_keeps_its_declared_pin(self):
        # [utest->req~ib-repair-completion~1]
        session = self.session()
        value = read_json(session.policy_path)
        config = value["completion"]
        spelling = str(self.request.parent) + "//" + self.request.name
        config["request"] = spelling
        config["inputs"][spelling] = config["inputs"].pop(str(self.request))
        write_json(session.policy_path, value)
        session.policy = value
        session.policy_hash = digest(session.policy_path.read_bytes())
        shutil.copytree(self.repo, session.work)
        session.expected_source = identity(session.work)["sha256"]
        failures = session.completion(0)
        self.assertEqual(len(failures), 1)
        self.assertEqual(session.result["completion"]["status"], "failed")
        self.assertEqual(
            session.result["completion"]["request_sha256"], digest(self.request.read_bytes())
        )


class MaintenanceCheckerTests(unittest.TestCase):
    def test_both_profiles_reject_noops_and_allow_refactor_alternatives(self):
        # [utest->req~ib-repair-completion~1]
        examples = Path(__file__).resolve().parents[1] / "examples"
        for domain in ("reservation", "async-lifecycle"):
            with self.subTest(profile=domain), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                source = root / "source"
                shutil.copytree(examples / domain / "fixture", source)
                target = source / (
                    "service.py" if domain == "reservation" else "client/controller.py"
                )
                original = target.read_text().replace(
                    "copy.copy(self.store)", "copy.deepcopy(self.store)"
                )
                q = {k: k for k in ("source_sha256", "request_sha256", "checker_sha256")}
                q["worktree"] = str(source)
                request, response = root / "request.json", root / "response.json"
                write_json(request, q)
                for kind in ("noop", "good", "alternative"):
                    text = original
                    if kind != "noop":
                        if domain == "reservation":
                            text = text.replace(
                                "staged = copy.deepcopy(self.store)",
                                "staged = type(self.store)(self.store.capacity)\n"
                                "        staged.restore(self.store.state())\n"
                                "        worker = Service(staged)",
                            )
                            text = text.replace(
                                "Service(staged).reserve(item", "worker.reserve(item"
                            )
                            if kind == "alternative":
                                text = text.replace(
                                    "worker = Service(staged)", "reserve = Service(staged).reserve"
                                ).replace("worker.reserve(", "reserve(")
                        else:
                            text = text.replace(
                                "        response = await request(payload(value))\n",
                                "        def settle(response):\n",
                            )
                            text = text.replace(
                                "        if serial == self.serial:",
                                "            if serial == self.serial:",
                            )
                            text = text.replace(
                                "            self.error =", "                self.error ="
                            ).replace(
                                "            self.pending = False",
                                "                self.pending = False",
                            )
                            text += "        settle(await request(payload(value)))\n"
                            if kind == "alternative":
                                text = text.replace(
                                    "self.serial += 1", "self.serial = object()"
                                ).replace("serial == self.serial", "serial is self.serial")
                    target.write_text(text)
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-B",
                            str(examples / "request_completion.py"),
                            domain,
                            str(request),
                            str(response),
                        ],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    value = read_json(response)
                    self.assertEqual(
                        value["status"], "failed" if kind == "noop" else "passed", value
                    )
                    for key in ("source_sha256", "request_sha256", "checker_sha256"):
                        self.assertEqual(value[key], q[key])


if __name__ == "__main__":
    unittest.main()
