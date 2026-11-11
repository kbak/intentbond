"""Exercise the real subprocess handoff, including edits it must not silently hide."""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/async-lifecycle"
ACTOR = """import json, os, sys, time
from pathlib import Path
mode, target, authorized, foreign, request, response = sys.argv[1:]
q = json.loads(Path(request).read_text())
root = Path(q['worktree'])
assert Path.cwd() == root
prompt = Path(q['prompt']).read_text()
assert 'retained-example' in prompt
assert authorized in prompt and foreign not in prompt
p = root/target
p.write_text(p.read_text().replace('return False', 'return True'))
if mode == 'collateral':
    (root/'requirements.md').write_text('')
    (root/'extra.py').write_text('unwanted = True\\n')
if mode == 'delete': (root/'requirements.md').unlink()
if mode == 'mode': p.chmod(0o755)
if mode == 'symlink':
    p.unlink(); p.symlink_to(root/'requirements.md')
if mode == 'timeout': time.sleep(10)
if mode == 'malformed': Path(response).write_text('not json'); sys.exit()
Path(response).write_text(json.dumps({
    'status': 'partial' if mode == 'partial' else 'completed',
    'source_sha256': 'wrong' if mode == 'stale' else q['source_sha256']}))
if mode == 'exit': sys.exit(1)
"""


class AgentAdapterExampleTests(unittest.TestCase):
    example = EXAMPLE
    target = "client/controller.py"
    authorized = "Form.validate"
    foreign = "Service.batch"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        (self.source / self.target).parent.mkdir(parents=True)
        (self.source / self.target).write_text("def validate():\n    return False\n")
        (self.source / "requirements.md").write_text("Keep the accepted promise.\n")
        self.actor = self.root / "actor.py"
        self.actor.write_text(ACTOR)

    def run_adapter(self, mode, *, bad_pin=False):
        folder = self.root / mode
        folder.mkdir()
        config = self.root / (mode + ".json")
        config.write_text(
            json.dumps(
                {
                    "command": [
                        sys.executable,
                        "-B",
                        str(self.actor),
                        mode,
                        self.target,
                        self.authorized,
                        self.foreign,
                    ],
                    "inputs": {
                        str(self.actor): "bad"
                        if bad_pin
                        else hashlib.sha256(self.actor.read_bytes()).hexdigest()
                    },
                    "seconds": 0.2 if mode == "timeout" else 5,
                }
            )
        )
        q = {
            "phase": "propose",
            "worktree": str(self.source),
            "source_sha256": "source-id",
            "requirements": ["req~example~1"],
            "failure_count": 1,
            "round": 1,
            "remaining_seconds": 10,
            "failures": [{"case": {"id": "retained-example", "requirements": ["req~example~1"]}}],
        }
        request, response = folder / "request.json", folder / "response.json"
        request.write_text(json.dumps(q))
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(self.example / "agent_adapter.py"),
                str(config),
                str(request),
                str(response),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertIn("return False", (self.source / self.target).read_text())
        self.assertEqual(
            (self.source / "requirements.md").read_text(), "Keep the accepted promise.\n"
        )
        return result, response, folder

    def test_completed_agent_edit_is_a_proposal_from_a_separate_copy(self):
        # [utest->req~ib-repair-boundaries~1]
        result, response, folder = self.run_adapter("repair")
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(response.read_text())
        self.assertEqual(value["source_sha256"], "source-id")
        self.assertEqual(value["proposal"]["targets"], ["req~example~1"])
        self.assertEqual(
            value["proposal"]["files"],
            {self.target: "def validate():\n    return True\n"},
        )
        self.assertTrue((folder / "agent/prompt.txt").is_file())
        self.assertTrue((folder / "agent/execution.json").is_file())

    def test_collateral_and_dropped_requirement_edits_reach_the_guard(self):
        # [utest->req~ib-repair-boundaries~1]
        result, response, _ = self.run_adapter("collateral")
        self.assertEqual(result.returncode, 0, result.stderr)
        files = json.loads(response.read_text())["proposal"]["files"]
        self.assertEqual(set(files), {self.target, "requirements.md", "extra.py"})
        self.assertEqual(files["requirements.md"], "")

    def test_unrepresentable_edits_are_not_lost_from_the_proposal(self):
        # [utest->req~ib-repair-boundaries~1]
        for mode in ("delete", "mode", "symlink"):
            with self.subTest(mode=mode):
                result, response, folder = self.run_adapter(mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("unsupported_agent_", result.stderr)
                self.assertFalse(response.exists())
                self.assertTrue((folder / "agent/work").is_dir())

    def test_partial_stale_failed_and_invalid_responses_cannot_succeed(self):
        # [utest->req~ib-repair-loop~1]
        for mode in ("partial", "stale", "exit", "malformed"):
            with self.subTest(mode=mode):
                result, response, folder = self.run_adapter(mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(response.exists())
                self.assertIn("return True", (folder / "agent/work" / self.target).read_text())

    def test_timeout_retains_partial_work_without_a_success_response(self):
        # [utest->req~ib-repair-loop~1]
        result, response, folder = self.run_adapter("timeout")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("agent_timeout", result.stderr)
        self.assertFalse(response.exists())
        self.assertEqual(
            json.loads((folder / "agent/execution.json").read_text())["status"], "timeout"
        )

    def test_changed_agent_pin_stops_before_execution(self):
        # [utest->req~ib-repair-policy~1]
        result, response, folder = self.run_adapter("pin", bad_pin=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("agent_input_changed", result.stderr)
        self.assertFalse(response.exists())
        self.assertFalse((folder / "agent").exists())

    def test_agent_demo_refuses_in_checkout_output(self):
        output = self.example / "must-not-be-created"
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(self.example / "agent_demo.py"),
                "--out",
                str(output),
                "--agent-config",
                str(self.root / "absent"),
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("outside the source checkout", result.stderr)
        self.assertFalse(output.exists())


class ReservationAgentAdapterExampleTests(AgentAdapterExampleTests):
    example = EXAMPLE.parent / "reservation"
    target = "service.py"
    authorized = "Service.batch"
    foreign = "Form.validate"
