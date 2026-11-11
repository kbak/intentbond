"""Qualify finite reference labels, retention and generator completeness."""

import copy
import hashlib
import itertools
import json

import legacy_reference
import lifecycle
import reference_history
import reference_state
from runtime import ROOT


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def semantic_digest(rows):
    values = [{k: v for k, v in row.items() if k != "label"} for row in rows]
    return hashlib.sha256(canonical(values).encode()).hexdigest()


def qualify():
    rows = lifecycle.generate("initial") + lifecycle.generate("adversarial")
    old = json.loads((ROOT / "fixture/tests/repair_cases.json").read_text())
    manifest = json.loads((ROOT / "retention.json").read_text())
    assert len(rows) == 136 and len(old) == 618
    assert len({row["id"] for row in old + rows}) == 754
    assert len({canonical(row["input"]) for row in rows}) == 136
    assert semantic_digest(old) == manifest["old_semantic_sha256"]
    assert semantic_digest(rows) == manifest["new_semantic_sha256"]
    for row in old:
        first = canonical(legacy_reference.expected(row["input"]))
        second = canonical(legacy_reference.expected(row["input"], history=True))
        assert first == second and row["accepted"] == [first], row["id"]
    negative_count = 0
    for row in rows:
        first = reference_state.expected(row["input"])
        assert first == reference_history.expected(row["input"])
        assert row["accepted"] == [canonical(first)] and row["label"]["status"] == "confirmed"
        for kind in ("pending", "error", "wire", "label"):
            wrong = copy.deepcopy(first)
            if kind == "pending":
                wrong["states"][0]["pending"] = not wrong["states"][0]["pending"]
            elif kind == "error":
                wrong["states"][-1]["error"] = (
                    "required" if wrong["states"][-1]["error"] is None else None
                )
            elif kind == "wire":
                wrong["requests"][0] = {"renamed": next(iter(wrong["requests"][0].values()))}
            else:
                wrong["component"]["label"] = "Go"
            assert wrong != first and wrong != reference_history.expected(row["input"])
            negative_count += 1
    for old_case in json.loads((ROOT / "regressions.json").read_text()):
        row = next(r for r in rows if r["id"] == "d10-" + old_case["id"])
        assert row["input"] == old_case["input"] and row["accepted"] == [
            canonical(old_case["expected"])
        ]
    counts = []
    for n in (1, 2, 3):
        atoms = [(action, i) for i in range(n) for action in ("start", "complete")]
        independent = {
            order
            for order in itertools.permutations(atoms)
            if [i for action, i in order if action == "start"] == list(range(n))
            and all(order.index(("start", i)) < order.index(("complete", i)) for i in range(n))
        }
        assert independent == {tuple(s) for s in lifecycle.schedules(n)}
        counts.append(len(independent))
    assert counts == [1, 3, 15]
    malformed = [
        [],
        [{"complete": 0}],
        [{"start": "Ada"}],
        [{"start": "Ada"}, {"complete": 0}, {"complete": 0}],
        [{"start": "Ada"}, {"complete": True}],
        [{"start": "Ada", "complete": 0}],
        [{"start": "Ada"}, {"complete": 1}],
        [{"start": "Ada"}, {"complete": -1}],
        None,
    ]
    for events in malformed:
        for model in (reference_state, reference_history):
            try:
                model.expected({"events": events})
            except ValueError:
                pass
            else:
                raise AssertionError("malformed schedule accepted")
    return {
        "old_cases": 618,
        "new_cases": 136,
        "total_cases": 754,
        "negative_output_controls": negative_count,
        "malformed_schedules": len(malformed),
        "schedules": counts,
        "exact_regressions": 2,
        "semantic_retention_matched": True,
    }
