"""Scripted proposal controls, not a model or a reference oracle."""

import ast
import json
import sys
from pathlib import Path


def replace_body(text, body):
    node = next(
        n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == "ordered"
    )
    lines = text.splitlines(keepends=True)
    return "".join(lines[: node.body[0].lineno - 1]) + body + "".join(lines[node.end_lineno :])


def proposal(text, mode, round_number):
    body = '    return sorted(rows, key=lambda row: row["name"])\n'
    if mode == "alternative":
        body = (
            '    from operator import itemgetter\n    return sorted(rows, key=itemgetter("name"))\n'
        )
    elif mode == "two-round" and round_number == 1:
        body = (
            '    if all(row["name"] in ("same", "a") for row in rows):\n'
            '        return sorted(rows, key=lambda row: row["name"])\n'
            '    return sorted(rows, key=lambda row: (row["name"], row["qty"]))\n'
        )
    elif mode == "drop-duplicates":
        body = '    return sorted({row["name"]: row for row in rows}.values(), key=lambda row: row["name"])\n'
    elif mode == "reject-duplicates":
        body = (
            '    if len({row["name"] for row in rows}) != len(rows):\n        raise ValueError("duplicates")\n'
            + body
        )
    elif mode == "quantities":
        body = (
            '    return sorted([dict(row, qty=1) for row in rows], key=lambda row: row["name"])\n'
        )
    elif mode == "json-blank-line":
        body = (
            '    globals()["array"] = lambda values: json.dumps(list(values)) + "\\n\\n"\n' + body
        )
    elif mode == "no-progress":
        body = (
            "    # Still incorrect.\n" * round_number
        ) + '    return sorted(rows, key=lambda row: (row["name"], row["qty"]))\n'
    if mode in ("drop-duplicates", "reject-duplicates", "json-blank-line"):
        body = f"    # Incorrect proposal attempt {round_number}.\n" + body
    return replace_body(text, body)


def main():
    mode, request, response = sys.argv[1:]
    q = json.loads(Path(request).read_text())
    source = Path(q["worktree"])
    # Trusted actor and reference modules must not be copied into the candidate.
    assert not any(
        (source / name).exists()
        for name in ("demo_actor.py", "references.py", "reference_insertion.py")
    )
    target = source / "formatters.py"
    target.write_text(proposal(target.read_text(), mode, q["round"]))
    if mode == "protected":
        (source / "compatibility.py").write_text('def option_error():\n    return 0, "", ""\n')
    elif mode == "old-test":
        path = source / "tests/test_export_order.py"
        path.write_text(path.read_text().replace("self.assertEqual", "self.assertNotEqual"))
    elif mode == "requirement":
        (source / "requirements.md").write_text("")
    elif mode == "unrelated":
        target.write_text(
            target.read_text().replace("def text(rows):", "def text(rows, extra=None):")
        )
    elif mode == "signature":
        target.write_text(
            target.read_text().replace("def ordered(rows):", "def ordered(rows, extra=None):")
        )
    Path(response).write_text(
        json.dumps(
            {
                "status": mode if mode in ("partial", "unknown") else "completed",
                "source_sha256": "stale" if mode == "stale" else q["source_sha256"],
            }
        )
    )


if __name__ == "__main__":
    main()
