"""D4 reservation cases and retained native tests, with explicit reference agreement."""

import hashlib
import json
from pathlib import Path

import reference_history
import references

ROOT = Path(__file__).resolve().parent
REQUIREMENTS = sorted(references.ALL)
REGRESSION = {
    "test_path": "tests/test_d4_rollback_regression.py",
    "data_path": "tests/reservation_cases.json",
    "links_path": "tests/links.json",
    "checks": ["utest~d4-rollback-regression~1", "utest~d4-idempotency-regression~1"],
}
LINKS = {
    "test_d4_rollback_regression.Regression.test_rollback": [REGRESSION["checks"][0]],
    "test_d4_rollback_regression.Regression.test_idempotency": [REGRESSION["checks"][1]],
}


def generate(stage):
    rows = []
    for case in references.generate(stage):
        expected = reference_history.reservation_model(case["input"], 2)
        if not references.contract_accepts(case["input"], expected):
            raise ValueError("conflicting_reservation_references")
        rows.append(
            {
                "id": case["id"],
                "kind": case["kind"],
                "input": case["input"],
                "requirements": case["targets"],
                "accepted": [references.decode(case["input"], expected)],
                "label": {
                    "status": "confirmed",
                    "method": "D2 event-log model agrees with D4 transition checker",
                    "sources": [str(ROOT / "reference_history.py"), str(ROOT / "references.py")],
                },
            }
        )
    return rows


def qualify():
    rows = generate("initial") + generate("adversarial")
    semantic = [{k: v for k, v in r.items() if k != "label"} for r in rows]
    value = references.decode(None, semantic)
    manifest = json.loads((ROOT / "retention.json").read_text())
    assert len(rows) == len({r["id"] for r in rows}) == 527
    assert hashlib.sha256(value.encode()).hexdigest() == manifest["semantic_sha256"]
    negatives = references.negative_outputs(rows)
    assert len(negatives) == 6
    assert all(not references.contract_accepts(c["input"], c["output"]) for c in negatives)
    # Preserve D4's exact seven rollback and eleven idempotency regression outcomes.
    for key in ("rollback", "idempotency"):
        for case in manifest[key]:
            matches = [r for r in rows if r["input"] == case["input"]]
            assert matches and all(r["accepted"] == case["accepted"] for r in matches)
    return {
        "cases": len(rows),
        "initial": 17,
        "adversarial": 510,
        "negative_outputs": len(negatives),
        "rollback_regressions": len(manifest["rollback"]),
        "idempotency_regressions": len(manifest["idempotency"]),
        "semantic_retention_matched": True,
    }


def scaffold(config):
    return (
        """import json
import unittest
from pathlib import Path
from api import execute


class Regression(unittest.TestCase):
    def cases(self):
        return json.loads(Path(__file__).with_name(%r).read_text())

    # [utest~d4-rollback-regression~1->req~reservation-atomic~1]
    def test_rollback(self):
        for case in self.cases():
            with self.subTest(case=case['id']):
                actual = json.dumps(execute(case['input']), sort_keys=True, separators=(',', ':'), allow_nan=False)
                self.assertIn(actual, case['accepted'])

    # [utest~d4-idempotency-regression~1->req~reservation-idempotency~1]
    def test_idempotency(self):
        cases = [c for c in self.cases() if 'req~reservation-idempotency~1' in c['requirements']]
        self.assertTrue(cases)
        for case in cases:
            with self.subTest(case=case['id']):
                actual = json.dumps(execute(case['input']), sort_keys=True, separators=(',', ':'), allow_nan=False)
                self.assertIn(actual, case['accepted'])
"""
        % Path(config["data_path"]).name
    )
