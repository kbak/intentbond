"""Neutral output normalization; contains no expected results or reference model."""

import json


def decode(case, outcome):
    """Semantic JSON comparison permits formatting choices; text/errors stay exact."""
    if set(outcome) != {"code", "out", "err"}:
        raise ValueError("invalid observation fields")
    if type(outcome["code"]) is not int or not all(
        isinstance(outcome[k], str) for k in ("out", "err")
    ):
        raise ValueError("invalid observation types")
    args = case["args"]
    if outcome["code"] or args == []:
        return outcome
    out = outcome["out"]
    if args == ["--json"]:
        if not out.endswith("\n"):
            raise ValueError("missing final newline")
        trailing_whitespace = out[len(out.rstrip(" \t\r\n")) :]
        if trailing_whitespace.count("\n") != 1:
            raise ValueError("expected one final newline")
        rows = json.loads(out)
    elif args == ["--stream"]:
        if out and not out.endswith("\n"):
            raise ValueError("missing final newline")
        rows = [json.loads(line) for line in out.splitlines()]
    else:
        raise ValueError("invalid options returned success")
    return {**outcome, "out": rows}
