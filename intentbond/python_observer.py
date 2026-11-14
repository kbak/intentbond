"""One trusted local Python observation in a fresh interpreter, not an OS sandbox."""

import importlib.util
import inspect
import json
import math
import sys
from pathlib import Path


def finite_json(value, depth=0):
    if depth > 32:
        raise ValueError("JSON nesting limit")
    if value is None or type(value) in (bool, int, str):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for item in value:
            finite_json(item, depth + 1)
        return
    if type(value) is dict and all(type(k) is str for k in value):
        for item in value.values():
            finite_json(item, depth + 1)
        return
    raise ValueError("Unsupported non-JSON observation")


# [impl->req~ib-python-comparison-observations~1]
def observe(request):
    root = Path(request["root"])
    path = root / request["path"]
    sys.path[:0] = [str(root), str(path.parent)]
    spec = importlib.util.spec_from_file_location("_ib_comparison_target", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    function = getattr(module, request["symbol"])
    if not inspect.isfunction(function) or inspect.iscoroutinefunction(function):
        raise ValueError("Select a synchronous Python function")
    arguments = request["arguments"]
    inspect.signature(function).bind(**arguments)
    before = json.dumps(arguments, sort_keys=True, allow_nan=False)
    try:
        value = function(**arguments)
    except Exception as exc:
        result = {"kind": "raised", "type": type(exc).__module__ + "." + type(exc).__qualname__}
    else:
        finite_json(value)
        result = {"kind": "returned", "value": value}
    if json.dumps(arguments, sort_keys=True, allow_nan=False) != before:
        raise ValueError("Function mutated an argument; pure functions only")
    return result


def main():
    request, response = map(Path, sys.argv[1:])
    try:
        result = observe(json.loads(request.read_bytes()))
        encoded = json.dumps(result, allow_nan=False)
        if len(encoded.encode()) > 1024 * 1024:
            raise ValueError("Observation byte limit")
    except Exception as exc:
        encoded = json.dumps(
            {"kind": "unresolved", "error": type(exc).__name__ + ": " + str(exc)[:500]}
        )
    response.write_text(encoded, encoding="utf-8")


if __name__ == "__main__":
    main()
