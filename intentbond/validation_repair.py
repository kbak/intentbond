"""Opt-in adapter from reviewed validation contracts to the existing repair protocol."""

import copy
import importlib
import inspect
import json
import keyword
import os
import sys
from pathlib import Path

from . import common, validation_contract
from .common import CheckError, digest, parse_json, relative_path, write_json
from .validation_contract import generate_validation_cases

MAX_BYTES = 16 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise CheckError(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def plain_json(value):
    """Do not coerce tuples, subclasses or non-string keys into accepted values."""
    if type(value) is dict:
        return all(type(k) is str and plain_json(v) for k, v in value.items())
    if type(value) is list:
        return all(plain_json(v) for v in value)
    return type(value) in (type(None), bool, int, float, str)


def checked_json(path, expected=None):
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    require(len(raw) <= MAX_BYTES, "Oversized validation adapter input")
    if expected is not None:
        require(digest(raw) == expected, "Validation adapter pin mismatch")
    value = parse_json(raw)
    encoded(value)
    return value


def target_names(module, function):
    for name in (module, function):
        require(
            isinstance(name, str)
            and name
            and all(
                part.isidentifier() and not keyword.iskeyword(part) for part in name.split(".")
            ),
            "Target must use Python identifiers",
        )
    require("." not in function, "Select a module-level function")


# [impl->req~ib-validation-repair-preparation~1]
def prepare_validation_repair(
    contract_path, expected_sha256, *, module, function, proposer, out, max_cases
):
    """Freeze cases once and return an adapter policy; grant no edit/review authority.

    Supply the existing repair policy's case limit, a caller-pinned proposal
    command, and a fresh directory outside candidate source and repair output.
    Preparation does not run candidate code or the proposal command.
    """
    target_names(module, function)
    require(type(max_cases) is int and 2 <= max_cases <= 1000, "Use the existing repair case limit")
    require(
        isinstance(proposer, dict) and set(proposer) == {"command", "inputs"}, "Pin the proposer"
    )
    command, inputs = proposer["command"], proposer["inputs"]
    require(
        isinstance(command, list)
        and command
        and all(isinstance(arg, str) and arg for arg in command)
        and Path(command[0]).is_absolute()
        and isinstance(inputs, dict)
        and inputs
        and any(arg in inputs for arg in command),
        "Proposer needs an absolute executable and pinned entry point",
    )
    pins = {}
    for name, sha in inputs.items():
        require(isinstance(name, str) and Path(name).is_absolute(), "Pin absolute proposer inputs")
        require(digest(Path(name).read_bytes()) == sha, "Proposer input pin mismatch")
        pins[name] = sha
    contract_path = Path(contract_path).resolve()
    bundle = generate_validation_cases(contract_path, expected_sha256, max_cases=max_cases)
    require(len(bundle["cases"]) >= 2, "Need positive and reserved boundary cases")
    # The native loop requires a nonempty second batch. Reserve one generated
    # rejection case; do not duplicate cases or claim adaptive adversarial search.
    reserved = next(
        i for i, case in reversed(list(enumerate(bundle["cases"]))) if case["outcome"] == "reject"
    )
    cases = [case for i, case in enumerate(bundle["cases"]) if i != reserved]
    cases.append(bundle["cases"][reserved])
    require(any(case["outcome"] == "accept" for case in cases[:-1]), "Missing positive control")
    for file in (
        contract_path,
        Path(__file__),
        Path(__file__).with_name("__init__.py"),
        Path(common.__file__),
        Path(validation_contract.__file__),
    ):
        name, sha = str(file.resolve()), digest(file.read_bytes())
        require(name not in pins or pins[name] == sha, "Conflicting trusted input pins")
        pins[name] = sha
    require(pins[str(contract_path)] == expected_sha256, "Contract changed during preparation")
    config = {
        "schema_version": 1,
        "contract": str(contract_path),
        "requirement": bundle["requirement"],
        "module": module,
        "function": function,
        "cases": cases,
        "proposer": copy.deepcopy(proposer),
        "inputs": pins,
        "semantic_approval": False,
    }
    content = json.dumps(config, indent=2, sort_keys=True, allow_nan=False) + "\n"
    require(len(content.encode("utf-8")) <= MAX_BYTES, "Oversized frozen validation suite")
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    config_path = out / "validation-adapter.json"
    config_path.write_text(content, encoding="utf-8")
    config_sha = digest(config_path.read_bytes())
    return {
        "command": [sys.executable, "-B", "-m", __name__, str(config_path), config_sha],
        "inputs": {**pins, str(config_path): config_sha},
    }


def repair_cases(config):
    rows = []
    for case in config["cases"]:
        expected = {"outcome": case["outcome"]}
        if case["outcome"] == "accept":
            expected["value"] = case["expected"]
        if case["preserve_input"]:
            expected["input"] = case["input"]
        rows.append(
            {
                "id": case["id"],
                "requirements": [config["requirement"]],
                "kind": "positive" if case["outcome"] == "accept" else "negative_input",
                "input": {"value": case["input"], "preserve_input": case["preserve_input"]},
                "accepted": [expected],
                "label": {
                    "status": "confirmed",
                    "method": "Caller-reviewed validation contract: " + case["boundary"],
                    "sources": [config["contract"]],
                },
            }
        )
    return rows


# [impl->req~ib-validation-repair-execution~1]
def observe_case(target, case):
    """Observe trusted synchronous code; expectations are never read from it."""
    argument = copy.deepcopy(case["input"]["value"])
    try:
        result = target(argument)
        if inspect.isawaitable(result):
            if inspect.iscoroutine(result):
                result.close()
            return {
                "id": case["id"],
                "status": "unknown",
                "reason": "unsupported asynchronous result",
            }
        value = {"outcome": "accept", "value": result}
    except ValueError:
        value = {"outcome": "reject"}
    except Exception as exc:
        value = {"outcome": "exception", "type": type(exc).__name__}
    if case["input"]["preserve_input"]:
        value["input"] = argument
    try:
        if not plain_json(value):
            raise ValueError("non-JSON observation")
        encoded(value)
    except (ValueError, TypeError, RecursionError):
        value = {"outcome": "non_json_observation"}
    return {"id": case["id"], "status": "returned", "value": value}


def scaffold(config, regression):
    test, data = (Path(relative_path(regression[key])) for key in ("test_path", "data_path"))
    checks = regression["checks"]
    require(
        test.parent == data.parent and test.stem.isidentifier(),
        "Use sibling regression test/data files",
    )
    require(len(checks) == 1, "Select one named validation regression check")
    source = f"""import importlib
import json
import unittest
from pathlib import Path
from intentbond.validation_repair import observe_case
TARGET = getattr(importlib.import_module({config["module"]!r}), {config["function"]!r})
# [{checks[0]}->{config["requirement"]}]
class ValidationRegression(unittest.TestCase):
    def test_cases(self):
        cases = json.loads(Path(__file__).with_name({data.name!r}).read_text())
        self.assertTrue(cases)
        for case in cases:
            with self.subTest(case=case['id']):
                observation = observe_case(TARGET, case)
                self.assertEqual(observation['status'], 'returned')
                actual = json.dumps(observation['value'], sort_keys=True, allow_nan=False)
                expected = [json.dumps(v, sort_keys=True, allow_nan=False) for v in case['accepted']]
                self.assertIn(actual, expected)
"""
    return {"test": source, "links": {test.stem + ".ValidationRegression.test_cases": checks}}


def load_config(path, sha):
    config = checked_json(path, sha)
    require(
        config.get("schema_version") == 1 and config.get("semantic_approval") is False,
        "Invalid adapter configuration",
    )
    for name, expected in config["inputs"].items():
        require(
            digest(Path(name).read_bytes()) == expected, "Validation adapter input changed: " + name
        )
    return config


# [impl->req~ib-validation-repair-execution~1]
def answer(config, request):
    require(request["schema_version"] == 1, "Unsupported repair request")
    require(
        request["requirements"] == [config["requirement"]],
        "Select the contract's single requirement",
    )
    rows = repair_cases(config)
    phase = request["phase"]
    response = {"source_sha256": request["source_sha256"]}
    if phase == "generate":
        stage = request["stage"]
        require(stage in ("initial", "adversarial"), "Unknown generation stage")
        require(
            encoded(request["cases"]) == encoded([] if stage == "initial" else rows[:-1]),
            "Changed retained cases",
        )
        response["cases"] = rows[:-1] if stage == "initial" else rows[-1:]
    elif phase in ("observe", "regression"):
        require(
            encoded(request["cases"]) in (encoded(rows[:-1]), encoded(rows)),
            "Changed or incomplete retained cases",
        )
        if phase == "regression":
            response.update(scaffold(config, request["regression"]))
        else:
            work = Path(request["worktree"]).resolve()
            sys.path.insert(0, str(work))
            module = importlib.import_module(config["module"])
            require(
                Path(module.__file__).resolve().is_relative_to(work),
                "Target module is outside candidate",
            )
            target = getattr(module, config["function"])
            require(callable(target), "Target is not callable")
            response["observations"] = [observe_case(target, case) for case in request["cases"]]
    else:
        raise CheckError("Unsupported validation adapter phase")
    return response


def main():
    config_path, sha, request_path, response_path = sys.argv[1:]
    config = load_config(config_path, sha)
    request = checked_json(request_path)
    if request["phase"] == "propose":
        require(request["requirements"] == [config["requirement"]], "Unmapped proposal requirement")
        frozen = {case["id"]: case for case in repair_cases(config)}
        failures = request["failures"]
        require(
            failures
            and all(encoded(frozen.get(f["case"]["id"])) == encoded(f["case"]) for f in failures),
            "Unrecognized proposal case",
        )
        # Replace this process: the existing runner still owns the same process
        # group, deadline, source checks and proposal validation. No retry/budget.
        command = config["proposer"]["command"]
        os.execv(command[0], [*command, request_path, response_path])
    write_json(Path(response_path), answer(config, request))


if __name__ == "__main__":
    main()
