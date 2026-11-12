"""Finite CLI challenges derived from maintained promises, never candidate labels."""

import itertools
import re

from observation import decode

ORDER = "req~export-order~1"
ERRORS = "req~export-errors~1"
PROMISE = "Every format sorts rows by name ascending, preserving input order among equal names; never drop duplicates."


def clauses(source, digest):
    text = (source / "requirements.md").read_text()
    sections = re.findall(r"### ([^\n]+)\n(.*?)(?=### |\Z)", text, re.S)
    result = []
    for name, section in sections:
        ref = re.search(r"`(req~[^`]+)`", section).group(1)
        offset = text.index("### " + name)
        result.append(
            {
                "requirement": ref,
                "text": section.strip(),
                "source": {
                    "path": "requirements.md",
                    "sha256": digest,
                    "line": text[:offset].count("\n") + 1,
                },
            }
        )
    order = next((r for r in result if r["requirement"] == ORDER), None)
    if not order or PROMISE not in order["text"]:
        raise ValueError("unresolved requirement interpretation: stable-order promise changed")
    order["temporary_clauses"] = [
        {"id": "order.ascending", "meaning": "names are nondecreasing"},
        {"id": "order.stable", "meaning": "equal-name rows retain original sequence"},
        {
            "id": "order.multiplicity",
            "meaning": "all rows, including duplicates, survive",
        },
    ]
    return result


def generate(phase):
    if phase == "initial":
        groups = [
            [],
            [("a", 1)],
            [("b", 1), ("a", 2)],
            [("same", 2), ("same", 1)],
            [("a", 2), ("a", 1), ("a", 2)],
        ]
    elif phase == "adversarial":
        atoms = [("a", 0), ("a", 1), ("b", 0), ("b", 1)]
        groups = [list(rows) for n in range(4) for rows in itertools.product(atoms, repeat=n)]
    else:
        raise ValueError("unknown challenge phase")
    cases = []
    for rows in groups:
        for args in ([], ["--json"], ["--stream"]):
            cases.append(
                {
                    "id": f"{phase}-{len(cases):03}",
                    "targets": [ORDER],
                    "kind": "positive",
                    "input": {
                        "args": args,
                        "rows": [{"name": n, "qty": q} for n, q in rows],
                    },
                }
            )
    for args in (
        ["--bad"],
        ["--json", "--stream"],
        ["--stream", "--json"],
        ["--json", "--json"],
        ["--stream", "--stream"],
    ):
        cases.append(
            {
                "id": f"{phase}-{len(cases):03}",
                "targets": [ERRORS],
                "kind": "negative_input",
                "input": {"args": args, "rows": []},
            }
        )
    return cases


def contract_accepts(case, outcome):
    """Second checker: grouping/invariant checks, independent of the insertion reference."""
    try:
        args = case["args"]
        if args not in ([], ["--json"], ["--stream"]):
            return outcome == {"code": 2, "out": "", "err": "invalid options\n"}
        normalized = decode(case, outcome)
        if normalized["code"] != 0 or normalized["err"] != "":
            return False
        original = case["rows"]
        if args == []:
            # Group each name in original encounter order; order only the distinct names.
            expected = "".join(
                f"{row['name']}\t{row['qty']}\n"
                for name in sorted({r["name"] for r in original})
                for row in original
                if row["name"] == name
            )
            return normalized["out"] == expected
        observed = normalized["out"]
        if not isinstance(observed, list) or len(observed) != len(original):
            return False
        if any(
            set(row) != {"name", "qty"}
            or not isinstance(row["name"], str)
            or type(row["qty"]) is not int
            for row in observed
        ):
            return False
        names = [row["name"] for row in observed]
        if names != sorted(names) or set(names) != {r["name"] for r in original}:
            return False
        return all(
            [r for r in observed if r["name"] == name] == [r for r in original if r["name"] == name]
            for name in names
        )
    except (ValueError, TypeError, KeyError):
        return False


def negative_outputs(cases):
    """Invalid proposed results test checker sensitivity, not candidate behavior."""
    rows = [{"name": "same", "qty": 2}, {"name": "same", "qty": 1}]
    case = {"args": [], "rows": rows}
    return [
        {
            "targets": [ORDER],
            "input": case,
            "output": {"code": 0, "out": "same\t1\nsame\t2\n", "err": ""},
        },
        {
            "targets": [ORDER],
            "input": case,
            "output": {"code": 0, "out": "same\t2\n", "err": ""},
        },
        {
            "targets": [ORDER],
            "input": case,
            "output": {"code": 2, "out": "", "err": "duplicates forbidden\n"},
        },
        {
            "targets": [ERRORS],
            "input": {"args": ["--bad"], "rows": []},
            "output": {"code": 0, "out": "", "err": ""},
        },
    ]
