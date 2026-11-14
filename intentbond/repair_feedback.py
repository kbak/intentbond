"""Structured diagnostics for trusted completion checkers; never repair authority."""

import json

from .change_guard import IDENTIFIER
from .common import CheckError, digest

FORMAT = "counterexamples-v1"


def require(condition, message):
    if not condition:
        raise CheckError(message)


def encoded(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise CheckError("Feedback must contain finite JSON") from exc


# [impl->req~ib-repair-feedback~1]
def validate_failures(rows, requirements):
    """Validate attribution and representation, not the checker's semantic judgment."""
    encoded(rows)
    require(isinstance(rows, list) and len(rows) <= 1000, "Invalid feedback failure list")
    seen = set()
    for row in rows:
        require(
            isinstance(row, dict)
            and set(row) == {"id", "requirements", "input", "expected", "observed"},
            "Invalid feedback failure",
        )
        name, refs = row["id"], row["requirements"]
        require(
            isinstance(name, str) and name.strip() and name not in seen,
            "Invalid or duplicate feedback ID",
        )
        seen.add(name)
        require(
            isinstance(refs, list)
            and refs
            and all(isinstance(r, str) and IDENTIFIER.fullmatch(r) for r in refs)
            and len(refs) == len(set(refs))
            and set(refs) <= set(requirements),
            "Unmapped feedback requirement",
        )
    return rows


# [impl->req~ib-repair-feedback~1]
def python_comparison_failures(result, *, source_sha256, policy_sha256, requirements):
    """Convert a trusted, completed compare_python result into completion failures.

    Pass identities retained by the caller, not copied from an untrusted report.
    This does not authenticate saved JSON, rerun checks, or establish a new request.
    Use original observations so every discovered requirement remains represented.
    """
    require(
        all(
            isinstance(sha, str) and len(sha) == 64 and all(c in "0123456789abcdef" for c in sha)
            for sha in (source_sha256, policy_sha256)
        ),
        "Invalid Python feedback identity",
    )
    encoded(result)
    require(
        isinstance(result, dict)
        and type(result.get("schema_version")) is int
        and result["schema_version"] == 1
        and result.get("complete") is True
        and result.get("execution_copies_removed") is True
        and result.get("semantic_approval") is False
        and result.get("status") in {"no_difference", "regression"}
        and result.get("diagnostics") == [],
        "Unresolved Python comparison feedback",
    )
    require(
        isinstance(result.get("candidate"), dict)
        and result["candidate"].get("sha256") == source_sha256
        and result.get("policy_sha256") == policy_sha256,
        "Stale Python comparison feedback",
    )
    rows = result.get("observations")
    require(
        isinstance(rows, list)
        and type(result.get("scheduled_cases")) is int
        and 0 < len(rows) == result["scheduled_cases"],
        "Incomplete Python comparison observations",
    )
    failures, seen = [], set()
    for row in rows:
        require(
            isinstance(row, dict)
            and set(row) == {"function", "arguments", "expected", "observed", "requirements"}
            and isinstance(row["function"], str)
            and row["function"]
            and isinstance(row["arguments"], dict)
            and isinstance(row["expected"], list)
            and isinstance(row["observed"], list)
            and 0 < len(row["expected"]) == len(row["observed"])
            and isinstance(row["requirements"], list),
            "Invalid Python comparison observation",
        )
        key = encoded([row["function"], row["arguments"]])
        require(key not in seen, "Duplicate Python comparison observation")
        seen.add(key)
        for value in row["expected"]:
            require(
                isinstance(value, dict)
                and set(value) == {"kind", "value"}
                and value["kind"] == "returned",
                "Unresolved Python comparison expectation",
            )
        for value in row["observed"]:
            require(
                isinstance(value, dict)
                and (
                    (set(value) == {"kind", "value"} and value["kind"] == "returned")
                    or (set(value) == {"kind"} and value["kind"] == "missing")
                    or (
                        set(value) == {"kind", "type"}
                        and value["kind"] == "raised"
                        and isinstance(value["type"], str)
                    )
                ),
                "Unresolved Python comparison observation",
            )
        different = encoded(row["expected"]) != encoded(row["observed"])
        require(bool(row["requirements"]) == different, "Contradictory Python feedback")
        if different:
            failures.append(
                {
                    "id": "python-" + digest(key.encode()),
                    "requirements": row["requirements"],
                    "input": {"function": row["function"], "arguments": row["arguments"]},
                    "expected": row["expected"],
                    "observed": row["observed"],
                }
            )
    require(bool(failures) == (result["status"] == "regression"), "Contradictory Python feedback")
    return validate_failures(failures, requirements)
