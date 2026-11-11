"""Keep D4's labels and rollback/idempotency counterexamples executable."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/reservation"


class ReservationExampleTests(unittest.TestCase):
    def test_retained_labels_and_negative_outputs(self):
        # [utest->req~ib-repair-cases~1]
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-c",
                "import json,sys; sys.path.insert(0,sys.argv[1]); import reservation_profile as p; print(json.dumps(p.qualify()))",
                str(EXAMPLE),
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value["cases"], 527)
        self.assertEqual(value["negative_outputs"], 6)
        self.assertEqual(value["rollback_regressions"], 7)
        self.assertEqual(value["idempotency_regressions"], 11)

    def test_retained_scaffold_catches_rollback_and_history_loss_but_accepts_alternatives(self):
        # [utest->req~ib-repair-regressions~1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            shutil.copytree(EXAMPLE / "fixture", source)
            generate = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-c",
                    """import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import reservation_profile as p
root = Path(sys.argv[2])
(root/p.REGRESSION['test_path']).write_text(p.scaffold(p.REGRESSION))
(root/p.REGRESSION['data_path']).write_text(json.dumps(p.generate('initial')+p.generate('adversarial')))
""",
                    str(EXAMPLE),
                    str(source),
                ],
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertEqual(generate.returncode, 0, generate.stderr)
            path = source / "service.py"
            faulty = path.read_text()
            deep = faulty.replace("copy.copy(self.store)", "copy.deepcopy(self.store)")
            explicit = faulty.replace(
                "staged = copy.copy(self.store)",
                "staged = copy.copy(self.store)\n        staged.active = dict(self.store.active)\n        staged.seen = dict(self.store.seen)",
            )
            erased = deep.replace(
                "self.store.restore(staged.state())",
                "staged.seen = dict(staged.active)\n        self.store.restore(staged.state())",
            )
            for name, text, passes in (
                ("shallow", faulty, False),
                ("deep", deep, True),
                ("explicit", explicit, True),
                ("history-loss", erased, False),
            ):
                with self.subTest(variant=name):
                    path.write_text(text)
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-B",
                            "-m",
                            "unittest",
                            "discover",
                            "-s",
                            "tests",
                            "-p",
                            "test_d4_rollback_regression.py",
                        ],
                        cwd=source,
                        capture_output=True,
                        text=True,
                        timeout=20,
                    )
                    self.assertEqual(result.returncode == 0, passes, result.stderr[-2000:])
                    cases = json.loads((source / "tests/reservation_cases.json").read_text())
                    inputs = root / "inputs.json"
                    inputs.write_text(
                        json.dumps([{"id": c["id"], "input": c["input"]} for c in cases])
                    )
                    observed = subprocess.run(
                        [
                            sys.executable,
                            "-I",
                            "-B",
                            str(EXAMPLE / "worker.py"),
                            str(source),
                            str(inputs),
                        ],
                        capture_output=True,
                        text=True,
                        timeout=20,
                    )
                    self.assertEqual(observed.returncode, 0, observed.stderr)
                    rows = [json.loads(line) for line in observed.stdout.splitlines()]
                    self.assertEqual([r["id"] for r in rows], [c["id"] for c in cases])
                    self.assertEqual(
                        all(
                            r["status"] == "returned" and r["value"] in c["accepted"]
                            for c, r in zip(cases, rows)
                        ),
                        passes,
                    )

    def test_qualification_cannot_disable_assertions(self):
        result = subprocess.run(
            [
                sys.executable,
                "-O",
                "-B",
                str(EXAMPLE / "agent_demo.py"),
                "--out",
                "/tmp/unused-reservation-example",
                "--agent-config",
                "/absent",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("without -O", result.stderr)
