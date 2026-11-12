"""Two caller-selected maintenance checks; preservation is checked separately.

These finite checks reuse the qualified follow-up requests. They do not interpret
arbitrary natural-language requests. The caller must select the matching checker.
"""

import ast
import json
import sys
from pathlib import Path
from unittest.mock import patch


def check(source, domain):
    if not __debug__:
        raise ValueError("Completion assertions require Python without -O")
    if domain not in {"reservation", "async-lifecycle"}:
        raise ValueError("Unknown completion profile")
    sys.path.insert(0, str(source))
    errors = []
    try:
        if domain == "async-lifecycle":
            tree = ast.parse((source / "client/controller.py").read_text())
            cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Form")
            method = next(
                n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "validate"
            )
            helpers = [
                n for n in method.body if isinstance(n, ast.FunctionDef) and n.name == "settle"
            ]
            assert len(helpers) == 1, "missing synchronous settle helper"
            helper = helpers[0]
            writes = {
                n.attr
                for n in ast.walk(helper)
                if isinstance(n, ast.Attribute)
                and isinstance(n.ctx, ast.Store)
                and isinstance(n.value, ast.Name)
                and n.value.id == "self"
            }
            assert {"error", "pending"} <= writes, "settle must own both response updates"
            assert any(
                isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "settle"
                for n in ast.walk(method)
            ), "settle is not called"
            outside = [
                n
                for statement in method.body
                if statement is not helper
                for n in ast.walk(statement)
            ]
            assert not any(
                isinstance(n, ast.Attribute)
                and isinstance(n.ctx, ast.Store)
                and isinstance(n.value, ast.Name)
                and n.value.id == "self"
                and n.attr == "error"
                for n in outside
            ), "error write outside settle"
        else:
            import copy

            import service
            import store

            live = store.Store(8)
            owner = service.Service(live)
            created = []
            original = service.Service.__init__

            def counted(obj, s):
                created.append(s)
                original(obj, s)

            with (
                patch.object(
                    copy, "deepcopy", side_effect=AssertionError("generic deep-copy forbidden")
                ),
                patch.object(service.Service, "__init__", counted),
            ):
                result = owner.batch([{"key": "a", "qty": 1}, {"key": "b", "qty": 2}])
            assert result["status"] == 200 and len(created) == 1 and created[0] is not live, (
                "one separate reusable staged service required"
            )
            tree = ast.parse((source / "service.py").read_text())
            method = next(
                n
                for c in tree.body
                if isinstance(c, ast.ClassDef) and c.name == "Service"
                for n in c.body
                if isinstance(n, ast.FunctionDef) and n.name == "batch"
            )
            calls = {
                n.func.attr
                for n in ast.walk(method)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            }
            assert {"state", "restore"} <= calls, "use public state/restore interface"
    except Exception as exc:
        errors.append(type(exc).__name__ + ": " + str(exc))
    return {"status": "failed" if errors else "passed", "errors": errors}


def main():
    domain, request, response = sys.argv[1:]
    q = json.loads(Path(request).read_text())
    result = check(Path(q["worktree"]), domain)
    Path(response).write_text(
        json.dumps(
            {
                "schema_version": 1,
                **{k: q[k] for k in ("source_sha256", "request_sha256", "checker_sha256")},
                **result,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
