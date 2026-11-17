"""Opt-in, finite acceptance tests from a caller-reviewed validation contract."""

import copy
import inspect
import keyword
import pprint
import re
from pathlib import Path

from .common import CheckError, canonical, digest, parse_json

MAX_BYTES = 65536
MAX_CASES = 1024


def _fields(value, required, optional=()):
    if type(value) is not dict or not set(required) <= value.keys():
        raise CheckError(f"Expected object with fields {sorted(required)}")
    if value.keys() - set(required) - set(optional):
        raise CheckError("Unsupported contract fields")


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise CheckError(f"Expected integer in [{low}, {high}]")


def _schema(node, depth=0, count=None):
    count = [0] if count is None else count
    count[0] += 1
    if depth > 5 or count[0] > 64:
        raise CheckError("Contract exceeds schema depth/node limit")
    _fields(
        node,
        {"type", "nullable"},
        {
            "min",
            "max",
            "min_length",
            "max_length",
            "alphabet",
            "initial",
            "properties",
            "keys",
            "values",
        },
    )
    kind = node["type"]
    extras = {
        "integer": {"min", "max"},
        "boolean": set(),
        "string": {"min_length", "max_length"},
        "object": {"properties"},
        "map": {"keys", "values"},
    }
    if type(kind) is not str or kind not in extras or type(node["nullable"]) is not bool:
        raise CheckError("Unsupported type or missing explicit null semantics")
    _fields(
        node,
        {"type", "nullable"} | extras[kind],
        {"alphabet", "initial"} if kind == "string" else (),
    )
    if kind == "integer":
        _integer(node["min"], -(10**9), 10**9)
        _integer(node["max"], node["min"], 10**9)
    elif kind == "string":
        _integer(node["min_length"], 0, 256)
        _integer(node["max_length"], max(1, node["min_length"]), 256)
        if "alphabet" in node or "initial" in node:
            for field in ("alphabet", "initial"):
                chars = node.get(field)
                if (
                    type(chars) is not str
                    or not chars
                    or len(chars) > 95
                    or len(set(chars)) != len(chars)
                    or any(not 32 <= ord(c) <= 126 for c in chars)
                ):
                    raise CheckError("Alphabet and initial must be nonempty unique printable ASCII")
            if not set(node["initial"]) <= set(node["alphabet"]):
                raise CheckError("Initial characters must belong to alphabet")
    elif kind == "object":
        props = node["properties"]
        if type(props) is not dict or not 1 <= len(props) <= 16:
            raise CheckError("Objects require 1–16 declared properties")
        for name, prop in props.items():
            if type(name) is not str or not name or len(name) > 80:
                raise CheckError("Invalid property name")
            _fields(prop, {"required", "schema"}, {"default"})
            if type(prop["required"]) is not bool or (prop["required"] and "default" in prop):
                raise CheckError("Required fields cannot also declare defaults")
            _schema(prop["schema"], depth + 1, count)
            if "default" in prop:
                try:
                    _normalize(prop["schema"], prop["default"])
                except ValueError as exc:
                    raise CheckError("Default violates its schema") from exc
    elif kind == "map":
        _schema(node["keys"], depth + 1, count)
        _schema(node["values"], depth + 1, count)
        if node["keys"]["type"] != "string" or node["keys"]["nullable"]:
            raise CheckError("Map keys must be non-null strings")


def _normalize(node, value):
    """Interpret only declared semantics; never consult candidate code."""
    if value is None:
        if node["nullable"]:
            return None
        raise ValueError("null")
    kind = node["type"]
    if kind == "integer":
        if type(value) is not int or not node["min"] <= value <= node["max"]:
            raise ValueError("integer range/type")
    elif kind == "boolean":
        if type(value) is not bool:
            raise ValueError("boolean type")
    elif kind == "string":
        if type(value) is not str or not node["min_length"] <= len(value) <= node["max_length"]:
            raise ValueError("string length/type")
        if "alphabet" in node and value:
            if value[0] not in node["initial"] or any(c not in node["alphabet"] for c in value):
                raise ValueError("string alphabet/initial")
    elif kind == "object":
        props = node["properties"]
        if type(value) is not dict or value.keys() - props.keys():
            raise ValueError("closed object")
        result = {}
        for name, prop in props.items():
            if name in value:
                result[name] = _normalize(prop["schema"], value[name])
            elif prop["required"]:
                raise ValueError("required field")
            elif "default" in prop:
                result[name] = _normalize(prop["schema"], copy.deepcopy(prop["default"]))
        return result
    elif kind == "map":
        if type(value) is not dict:
            raise ValueError("map type")
        return {
            _normalize(node["keys"], k): _normalize(node["values"], v) for k, v in value.items()
        }
    return value


def _word(node, length, last=False):
    if not length:
        return ""
    index = -1 if last else 0
    return node.get("initial", "ab")[index] + node.get("alphabet", "ab")[index] * (length - 1)


def _map_keys(node):
    keys = []
    for length in (node["min_length"], node["max_length"]):
        for last in (False, True):
            key = _word(node, length, last)
            if key not in keys:
                keys.append(key)
    return keys[:2]


def _seed(node):
    kind = node["type"]
    if kind == "integer":
        return node["min"]
    if kind == "boolean":
        return False
    if kind == "string":
        return _word(node, max(1, node["min_length"]))
    if kind == "object":
        return {name: _seed(prop["schema"]) for name, prop in node["properties"].items()}
    return {_map_keys(node["keys"])[0]: _seed(node["values"])}


def _samples(node, path=()):
    seed = _seed(node)
    yield path, "present", seed
    # JSON-valued wrong-type probes, including bool/int confusion.
    for value in (None, False, True, 0, 1, 1.0, "", [], {}):
        yield path, "type-or-empty", value
    kind = node["type"]
    if kind == "integer":
        for value in (node["min"] - 1, node["min"], node["max"], node["max"] + 1):
            yield path, "range", value
        yield path, "in-range-float", float(node["min"])
    elif kind == "string":
        for length in sorted(
            {
                max(0, node["min_length"] - 1),
                node["min_length"],
                node["max_length"],
                node["max_length"] + 1,
            }
        ):
            for last in (False, True):
                yield path, "length", _word(node, length, last)
        for char in ("é", "\n", "\x00", *node.get("alphabet", "")):
            # For an alphabet, probe each allowed initial and interior character too.
            yield path, "initial-character", char + seed[1:]
            if len(seed) < node["max_length"]:
                yield path, "interior-character", seed + char
            elif len(seed) > 1:
                yield path, "interior-character", seed[:-1] + char
    elif kind == "object":
        props = node["properties"]
        yield path, "only-required", {k: v for k, v in seed.items() if props[k]["required"]}
        unknown = "unknown"
        while unknown in props:
            unknown += "_"
        yield path, "unknown-field", {**seed, unknown: 1}
        for name, prop in props.items():
            yield (*path, name), "missing-field", {k: v for k, v in seed.items() if k != name}
            for child_path, label, value in _samples(prop["schema"], (*path, name)):
                candidate = {**seed, name: value}
                yield child_path, label, candidate
                # A nullable sibling must not disable validation of other fields.
                for sibling, other in props.items():
                    if sibling != name and other["schema"]["nullable"]:
                        yield child_path, "null-sibling/" + label, {**candidate, sibling: None}
    elif kind == "map":
        keys = _map_keys(node["keys"])
        value = _seed(node["values"])
        for child_path, label, key in _samples(node["keys"], (*path, "<key>")):
            if type(key) is str:
                yield child_path, label, {key: value}
        for child_path, label, item in _samples(node["values"], (*path, "<value>")):
            yield child_path, label, {keys[0]: item}
            if node["values"]["nullable"] and len(keys) > 1:
                yield child_path, "mixed-null/" + label, {keys[0]: None, keys[1]: item}
                yield child_path, "mixed-null-reversed/" + label, {keys[0]: item, keys[1]: None}


# [impl->req~ib-validation-contract-generation~1]
def generate_validation_cases(contract_path, expected_sha256, *, max_cases=512):
    """Return a deterministic reviewable bundle, or refuse the entire generation.

    The digest is supplied separately after caller review. It binds bytes, not
    semantic approval. Nothing executes here and no partial bundle is returned.
    """
    _integer(max_cases, 1, MAX_CASES)
    try:
        with Path(contract_path).open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
    except OSError as exc:
        raise CheckError(f"Cannot read validation contract: {exc}") from exc
    if len(raw) > MAX_BYTES or not re.fullmatch(r"[0-9a-f]{64}", str(expected_sha256)):
        raise CheckError("Invalid contract size or caller digest")
    if digest(raw) != expected_sha256:
        raise CheckError("Validation contract differs from caller-reviewed bytes")
    try:
        contract = parse_json(raw)
    except (ValueError, RecursionError) as exc:
        raise CheckError("Invalid contract JSON") from exc
    _fields(
        contract,
        {"schema_version", "requirement", "preserve_input", "output", "rejection", "input"},
    )
    if (
        type(contract["schema_version"]) is not int
        or contract["schema_version"] != 1
        or type(contract["preserve_input"]) is not bool
        or contract["output"] != "normalized"
        or contract["rejection"] != "ValueError"
        or not isinstance(contract["requirement"], str)
        or not re.fullmatch(r"req~[a-zA-Z0-9_.-]+~[1-9][0-9]*", contract["requirement"])
    ):
        raise CheckError("Unsupported contract semantics or requirement reference")
    _schema(contract["input"])
    cases, seen = [], set()
    # Bound traversal as well as saved case count; deduplication cannot hide cost.
    for attempts, (path, boundary, value) in enumerate(_samples(contract["input"]), 1):
        if attempts > MAX_CASES * 64:
            raise CheckError("Contract exceeds generation traversal limit")
        identity = canonical(value)
        if identity in seen:
            continue
        seen.add(identity)
        if len(cases) >= max_cases:
            raise CheckError("Case limit would omit generated obligations; no suite returned")
        case = {
            "id": f"case-{len(cases) + 1:04d}",
            "path": list(path),
            "boundary": boundary,
            "input": copy.deepcopy(value),
            "preserve_input": contract["preserve_input"],
        }
        try:
            case["expected"] = _normalize(contract["input"], value)
            case["outcome"] = "accept"
        except ValueError:
            case["outcome"] = "reject"
        cases.append(case)
    return {
        "schema_version": 1,
        "contract_sha256": expected_sha256,
        "requirement": contract["requirement"],
        "semantic_approval": False,
        "cases": cases,
    }


def _same(left, right):
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(_same(left[k], right[k]) for k in left)
    if type(left) is list:
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    return left == right


# [impl->req~ib-validation-contract-execution~1]
def assert_validation_case(target, case):
    """Execute one generated case against a trusted synchronous callable."""
    argument = copy.deepcopy(case["input"])
    label = f"{case['id']} {case['path']} {case['boundary']}"
    rejected = False
    try:
        result = target(argument)
        if inspect.isawaitable(result):
            if inspect.iscoroutine(result):
                result.close()
            raise AssertionError(f"{label}: asynchronous validators are unsupported")
    except ValueError:
        rejected = True
    finally:
        if case["preserve_input"] and not _same(argument, case["input"]):
            raise AssertionError(f"{label}: validator changed its input")
    if case["outcome"] == "reject":
        if not rejected:
            raise AssertionError(f"{label}: expected ValueError")
    elif case["outcome"] == "accept":
        if rejected or not _same(result, case["expected"]):
            raise AssertionError(f"{label}: expected declared normalized result")
    else:
        raise CheckError("Unsupported case outcome")


# [impl->req~ib-validation-contract-generation~1]
# [impl->req~ib-validation-contract-execution~1]
def render_validation_tests(contract_path, expected_sha256, *, module, function, max_cases=512):
    """Render unittest source without importing the target or executing code."""
    for name in (module, function):
        if (
            type(name) is not str
            or not name
            or any(not p.isidentifier() or keyword.iskeyword(p) for p in name.split("."))
        ):
            raise CheckError("Target must use Python identifiers")
    if "." in function:
        raise CheckError("Target function must be a module-level callable")
    bundle = generate_validation_cases(contract_path, expected_sha256, max_cases=max_cases)
    lines = [
        '"""Generated finite tests; review the contract and cases before adoption."""',
        "import importlib",
        "import unittest",
        "from intentbond.validation_contract import assert_validation_case",
        "",
        f"BUNDLE = {pprint.pformat(bundle, width=100, sort_dicts=False)}",
        f"TARGET = getattr(importlib.import_module({module!r}), {function!r})",
        "",
        "class ValidationContractTests(unittest.TestCase):",
    ]
    for index, case in enumerate(bundle["cases"]):
        lines += [
            f"    # [utest->{bundle['requirement']}]",
            f"    def test_{index + 1:04d}(self):",
            f"        {str(case['path']) + ': ' + case['boundary']!r}",
            f"        assert_validation_case(TARGET, BUNDLE['cases'][{index}])",
            "",
        ]
    return "\n".join(lines) + '\nif __name__ == "__main__":\n    unittest.main()\n'
