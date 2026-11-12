"""D3's finite challenges, pinned interpretation and portable retained tests."""

import hashlib
import inspect
import json
from pathlib import Path

import observation
import reference_insertion
import references

ROOT = Path(__file__).resolve().parent
ALL_REQUIREMENTS = sorted(
    f"req~export-{name}~1" for name in ("text", "order", "errors", "json", "stream")
)
REQUIREMENTS = sorted([references.ORDER, references.ERRORS])
REGRESSION = {
    "test_path": "tests/test_cli_ordering_regression.py",
    "data_path": "tests/cli_ordering_cases.json",
    "links_path": "tests/links.json",
    "checks": ["utest~d3-ordering-regression~1", "utest~d3-errors-regression~1"],
}
LINKS = {
    "test_cli_ordering_regression.Regression.test_order": [REGRESSION["checks"][0]],
    "test_cli_ordering_regression.Regression.test_errors": [REGRESSION["checks"][1]],
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def validate_contract(source):
    path = source / "requirements.md"
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = json.loads((ROOT / "retention.json").read_text())
    if sha != manifest["requirements_sha256"]:
        raise ValueError("unresolved_requirement_interpretation")
    return references.clauses(source, sha)


def generate(stage):
    rows = []
    for case in references.generate(stage):
        expected = reference_insertion.export_model(case["input"], 2)
        if not references.contract_accepts(case["input"], expected):
            raise ValueError("conflicting_cli_references")
        rows.append(
            {
                "id": case["id"],
                "kind": case["kind"],
                "input": case["input"],
                "requirements": case["targets"],
                "accepted": [canonical(observation.decode(case["input"], expected))],
                "label": {
                    "status": "confirmed",
                    "method": "D2 insertion reference agrees with D3 grouping/invariant checker",
                    "sources": [
                        str(ROOT / name)
                        for name in (
                            "reference_insertion.py",
                            "references.py",
                            "observation.py",
                            "retention.json",
                            "fixture/requirements.md",
                        )
                    ],
                },
            }
        )
    return rows


def qualify():
    validate_contract(ROOT / "fixture")
    rows = generate("initial") + generate("adversarial")
    semantic = [{k: v for k, v in row.items() if k != "label"} for row in rows]
    manifest = json.loads((ROOT / "retention.json").read_text())
    assert len(rows) == len({row["id"] for row in rows}) == 280
    assert hashlib.sha256(canonical(semantic).encode()).hexdigest() == manifest["semantic_sha256"]
    assert all(case in semantic for case in manifest["minimal_tie"])
    negatives = references.negative_outputs(rows)
    assert len(negatives) == 4
    assert all(not references.contract_accepts(c["input"], c["output"]) for c in negatives)
    return {
        "cases": len(rows),
        "initial": 20,
        "adversarial": 260,
        "negative_outputs": 4,
        "minimal_tie_regressions": len(manifest["minimal_tie"]),
        "semantic_retention_matched": True,
    }


def scaffold(config):
    # Copy only neutral output parsing: neither reference model enters the candidate.
    return (
        "import json\nimport unittest\nfrom pathlib import Path\nfrom entrypoint import evaluate\n\n"
        + inspect.getsource(observation.decode)
        + """

class Regression(unittest.TestCase):
    def check_cases(self, requirement):
        cases = json.loads(Path(__file__).with_name(%r).read_text())
        cases = [c for c in cases if requirement in c['requirements']]
        self.assertTrue(cases)
        for case in cases:
            with self.subTest(case=case['id']):
                actual = json.dumps(decode(case['input'], evaluate(case['input'])), sort_keys=True, separators=(',', ':'), allow_nan=False)
                self.assertIn(actual, case['accepted'])

    # [utest~d3-ordering-regression~1->req~export-order~1]
    def test_order(self):
        self.check_cases('req~export-order~1')

    # [utest~d3-errors-regression~1->req~export-errors~1]
    def test_errors(self):
        self.check_cases('req~export-errors~1')
"""
        % Path(config["data_path"]).name
    )
