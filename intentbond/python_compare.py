"""Opt-in differential checks of caller-declared preserved Python observations."""

import itertools
import math
import os
import re
import sys
import tempfile
import time
from pathlib import Path

from .change_guard import IDENTIFIER
from .common import CheckError, canonical, digest, read_json, relative_path, run, write_json
from .python_observer import finite_json
from .snapshot import read_entry, repository, resolve_commit, snapshot

EXIT_CODES = {"no_difference": 0, "regression": 1, "unresolved": 5}
MAX_BYTES = 1024 * 1024
LIMITATION = (
    "Finite preservation observations against a caller-accepted baseline; not proof, "
    "new-request validation, causal attribution, or semantic approval. Trusted local code; "
    "fresh processes are not an OS security sandbox."
)


def require(condition, message):
    if not condition:
        raise CheckError(message)


def encoded(value):
    finite_json(value)
    data = canonical(value)
    require(len(data) <= MAX_BYTES, "Comparison JSON byte limit")
    return data


def integer(value):
    return type(value) is int and -(2**63) <= value < 2**63


def domain_values(domain):
    require(type(domain) is dict, "Invalid argument domain")
    if domain.get("type") == "enum":
        require(set(domain) == {"type", "values"}, "Invalid enum domain fields")
        values = domain["values"]
        require(type(values) is list and 1 <= len(values) <= 32, "Select 1–32 enum values")
        require(len({encoded(x) for x in values}) == len(values), "Duplicate enum values")
        return values
    require(
        domain.get("type") == "integer" and set(domain) == {"type", "min", "max", "boundaries"},
        "Select an integer or enum domain",
    )
    lo, hi, boundaries = domain["min"], domain["max"], domain["boundaries"]
    require(integer(lo) and integer(hi) and lo <= hi, "Invalid integer interval")
    require(
        type(boundaries) is list
        and len(boundaries) <= 32
        and all(integer(x) and lo <= x <= hi for x in boundaries),
        "Boundaries must be integers in the declared domain",
    )
    values = [lo, hi, 0, (lo + hi) // 2, lo + 1, hi - 1]
    for value in boundaries:
        values.extend((value, value - 1, value + 1))
    return list(dict.fromkeys(x for x in values if lo <= x <= hi))


def in_domain(value, domain):
    if domain["type"] == "enum":
        return encoded(value) in {encoded(x) for x in domain["values"]}
    return integer(value) and domain["min"] <= value <= domain["max"]


# [impl->req~ib-python-comparison-policy~1]
def validate_policy(policy):
    encoded(policy)
    require(
        type(policy) is dict
        and set(policy) == {"schema_version", "baseline", "functions", "limits"},
        "Invalid comparison policy fields",
    )
    require(
        type(policy["schema_version"]) is int and policy["schema_version"] == 1,
        "Unsupported comparison schema",
    )
    require(
        type(policy["baseline"]) is str
        and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", policy["baseline"]),
        "Pin the full accepted baseline commit",
    )
    limits = policy["limits"]
    require(
        type(limits) is dict
        and set(limits) == {"cases", "seconds", "call_seconds", "shrink_steps"},
        "Invalid comparison limits",
    )
    require(
        type(limits["cases"]) is int and 1 <= limits["cases"] <= 1000, "Case limit must be 1–1000"
    )
    require(
        type(limits["shrink_steps"]) is int and 0 <= limits["shrink_steps"] <= 1000,
        "Invalid shrink limit",
    )
    for key, bound in (("seconds", 600), ("call_seconds", 60)):
        require(
            type(limits[key]) in (int, float)
            and math.isfinite(limits[key])
            and 0 < limits[key] <= bound,
            "Invalid time limit: " + key,
        )
    functions = policy["functions"]
    require(type(functions) is list and 1 <= len(functions) <= 16, "Select 1–16 functions")
    ids, planned = set(), 0
    for function in functions:
        require(
            type(function) is dict
            and set(function) == {"id", "path", "symbol", "arguments", "observations"},
            "Invalid function fields",
        )
        name = function["id"]
        require(
            type(name) is str
            and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", name)
            and name not in ids,
            "Invalid or duplicate function ID",
        )
        ids.add(name)
        require(relative_path(function["path"]).endswith(".py"), "Select a Python source file")
        require(
            type(function["symbol"]) is str and function["symbol"].isidentifier(),
            "Select a top-level function",
        )
        arguments = function["arguments"]
        require(
            type(arguments) is dict
            and len(arguments) <= 8
            and all(k.isidentifier() for k in arguments),
            "Declare up to eight keyword argument domains",
        )
        planned += math.prod(len(domain_values(d)) for d in arguments.values())
        observations = function["observations"]
        require(
            type(observations) is list and 1 <= len(observations) <= 16,
            "Select 1–16 preserved observations",
        )
        seen = set()
        for observation in observations:
            require(
                type(observation) is dict and set(observation) == {"requirement", "path"},
                "Invalid observation fields",
            )
            ref, path = observation["requirement"], observation["path"]
            require(
                type(ref) is str and IDENTIFIER.fullmatch(ref),
                "Use maintained requirement references",
            )
            require(
                type(path) is list
                and len(path) <= 16
                and all(type(x) is str or (type(x) is int and x >= 0) for x in path),
                "Observation paths contain object keys or nonnegative list indices",
            )
            require(encoded(observation) not in seen, "Duplicate preserved observation")
            seen.add(encoded(observation))
    require(planned <= limits["cases"], "Generated boundary product exceeds case budget")
    return policy


def generated(function):
    arguments = function["arguments"]
    for values in itertools.product(*(domain_values(d) for d in arguments.values())):
        yield dict(zip(arguments, values, strict=True))


def projected(observation, selectors):
    if observation["kind"] == "raised":
        return [{"kind": "raised", "type": observation["type"]} for _ in selectors]
    result = []
    for selector in selectors:
        value = observation["value"]
        for key in selector["path"]:
            if type(value) is dict and type(key) is str and key in value:
                value = value[key]
            elif type(value) is list and type(key) is int and 0 <= key < len(value):
                value = value[key]
            else:
                result.append({"kind": "missing"})
                break
        else:
            result.append({"kind": "returned", "value": value})
    return result


def manifest(root):
    rows = []
    for path in root.rglob("*"):
        if path.is_symlink() or path.is_file():
            name = path.relative_to(root).as_posix()
            mode, data = read_entry(root, name)
            rows.append({"path": name, "mode": mode, "sha256": digest(data)})
    return sorted(rows, key=lambda row: row["path"])


class Comparison:
    def __init__(self, repo, policy_path, policy_sha256, out, candidate, replay, replay_sha256):
        self.repo = repository(repo)
        self.policy_path, self.out = policy_path.resolve(), out.resolve()
        require(not policy_path.is_symlink(), "Policy cannot be a symlink")
        for path in (self.policy_path, self.out):
            require(
                not path.is_relative_to(self.repo), "Policy and evidence must be outside source"
            )
        require(not self.policy_path.is_relative_to(self.out), "Policy cannot be inside output")
        require(not self.out.exists(), "Comparison output must be a new directory")
        require(self.policy_path.stat().st_size <= MAX_BYTES, "Policy byte limit")
        require(digest(self.policy_path.read_bytes()) == policy_sha256, "Policy pin mismatch")
        self.policy = validate_policy(read_json(self.policy_path))
        require(
            resolve_commit(self.repo, self.policy["baseline"]) == self.policy["baseline"],
            "Baseline commit mismatch",
        )
        self.pins = {
            self.policy_path: policy_sha256,
            Path(__file__).with_name("python_observer.py"): digest(
                Path(__file__).with_name("python_observer.py").read_bytes()
            ),
        }
        self.candidate = candidate
        self.replay = None
        require(
            (replay is None) == (replay_sha256 is None),
            "Replay requires its caller-retained digest",
        )
        if replay is not None:
            require(not replay.is_symlink(), "Replay cannot be a symlink")
            replay = replay.resolve()
            require(
                not replay.is_relative_to(self.repo) and not replay.is_relative_to(self.out),
                "Replay must be outside source and output",
            )
            require(
                replay.stat().st_size <= MAX_BYTES and digest(replay.read_bytes()) == replay_sha256,
                "Replay pin mismatch or size limit",
            )
            self.replay = read_json(replay)
            encoded(self.replay)
            require(
                set(self.replay) == {"schema_version", "policy_sha256", "baseline_sha256", "cases"}
                and type(self.replay["schema_version"]) is int
                and self.replay["schema_version"] == 1,
                "Invalid retained cases",
            )
            require(
                self.replay["policy_sha256"] == policy_sha256
                and type(self.replay["cases"]) is list,
                "Retained policy mismatch",
            )
            self.pins[replay] = replay_sha256
        self.out.mkdir(parents=True)
        self.deadline = time.monotonic() + self.policy["limits"]["seconds"]
        self.result = {
            "schema_version": 1,
            "mode": "replay" if replay else "discover",
            "status": "unresolved",
            "complete": False,
            "policy_sha256": policy_sha256,
            "semantic_approval": False,
            "limitation": LIMITATION,
            "observations": [],
            "counterexamples": [],
            "diagnostics": [],
            "calls": 0,
            "shrink_evaluations": 0,
        }
        self.retained = []
        write_json(self.out / "policy.json", self.policy)

    def integrity(self):
        for path, expected in self.pins.items():
            require(
                not path.is_symlink() and digest(path.read_bytes()) == expected,
                "Trusted input changed",
            )
        for source in self.sources.values():
            require(manifest(source.root) == source.manifest, "Executed source changed")

    def remaining(self):
        value = self.deadline - time.monotonic()
        require(value > 0, "Comparison deadline exhausted")
        return value

    # [impl->req~ib-python-comparison-observations~1]
    def observe(self, source, function, arguments):
        values = []
        for repeat in range(2):
            self.integrity()
            folder = self.out / ("call-%04d" % self.result["calls"])
            folder.mkdir()
            self.result["calls"] += 1
            request, response = folder / "request.json", folder / "response.json"
            write_json(
                request,
                {
                    "root": str(source.root),
                    "path": function["path"],
                    "symbol": function["symbol"],
                    "arguments": arguments,
                },
            )
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            execution = run(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    str(Path(__file__).with_name("python_observer.py")),
                    str(request),
                    str(response),
                ],
                source.root,
                folder / "process.log",
                timeout=min(self.remaining(), self.policy["limits"]["call_seconds"]),
                env=env,
            )
            write_json(folder / "execution.json", execution)
            self.integrity()
            self.remaining()
            require(
                execution["status"] == "passed" and response.is_file(),
                "Observation process unavailable or timed out",
            )
            require(
                not response.is_symlink() and response.stat().st_size <= MAX_BYTES,
                "Invalid observation response",
            )
            value = read_json(response)
            encoded(value)
            require(
                type(value) is dict and value.get("kind") in ("returned", "raised"),
                "Unresolved Python observation: "
                + str(
                    value.get("error", "invalid response")
                    if type(value) is dict
                    else "invalid response"
                ),
            )
            require(
                set(value)
                == ({"kind", "value"} if value["kind"] == "returned" else {"kind", "type"}),
                "Malformed observation",
            )
            values.append(projected(value, function["observations"]))
        require(encoded(values[0]) == encoded(values[1]), "Unstable preserved observation")
        return values[0]

    def evaluate(self, function, arguments):
        expected = self.observe(self.sources["baseline"], function, arguments)
        require(
            all(x["kind"] == "returned" for x in expected),
            "Baseline cannot establish the selected expected return",
        )
        observed = self.observe(self.sources["candidate"], function, arguments)
        refs = sorted(
            {
                selector["requirement"]
                for selector, a, b in zip(function["observations"], expected, observed, strict=True)
                if encoded(a) != encoded(b)
            }
        )
        return {
            "function": function["id"],
            "arguments": arguments,
            "expected": expected,
            "observed": observed,
            "requirements": refs,
        }

    def schedule(self):
        by_id = {f["id"]: f for f in self.policy["functions"]}
        rows, seen = [], set()
        if self.replay is not None:
            require(
                self.replay["baseline_sha256"] == self.sources["baseline"].sha256,
                "Retained baseline mismatch",
            )
            for row in self.replay["cases"]:
                require(
                    type(row) is dict
                    and set(row) == {"function", "arguments", "expected"}
                    and row["function"] in by_id,
                    "Invalid retained case",
                )
                function = by_id[row["function"]]
                require(
                    type(row["expected"]) is list
                    and len(row["expected"]) == len(function["observations"]),
                    "Invalid retained expectation",
                )
                require(
                    type(row["arguments"]) is dict
                    and set(row["arguments"]) == set(function["arguments"]),
                    "Retained argument mismatch",
                )
                require(
                    all(
                        in_domain(v, function["arguments"][k]) for k, v in row["arguments"].items()
                    ),
                    "Retained input outside declared domain",
                )
                key = encoded([row["function"], row["arguments"]])
                require(key not in seen, "Duplicate retained case")
                seen.add(key)
                rows.append((function, row["arguments"], row["expected"]))
            require(
                1
                <= len(rows)
                <= self.policy["limits"]["cases"] + self.policy["limits"]["shrink_steps"],
                "Empty or oversized retained case set",
            )
            return rows
        for function in by_id.values():
            for arguments in generated(function):
                key = encoded([function["id"], arguments])
                if key not in seen:
                    seen.add(key)
                    rows.append((function, arguments, None))
        require(
            len(rows) <= self.policy["limits"]["cases"],
            "Retained plus generated cases exceed budget",
        )
        return rows

    # [impl->req~ib-python-comparison-retention~1]
    def retain(self, row):
        case = {k: row[k] for k in ("function", "arguments", "expected")}
        if encoded(case) not in {encoded(saved) for saved in self.retained}:
            self.retained.append(case)
        value = {
            "schema_version": 1,
            "policy_sha256": self.result["policy_sha256"],
            "baseline_sha256": self.sources["baseline"].sha256,
            "cases": self.retained,
        }
        encoded(value)
        write_json(self.out / "regressions.json", value)

    def minimize(self, function, original):
        current = original
        for name, domain in function["arguments"].items():
            while self.result["shrink_evaluations"] < self.policy["limits"]["shrink_steps"]:
                value = current["arguments"][name]
                if domain["type"] == "integer":
                    target = min(domain["max"], max(domain["min"], 0))
                    distance = value - target
                    candidates = (
                        [
                            target,
                            target + abs(distance) // 2 * (1 if distance >= 0 else -1),
                            value - (1 if distance > 0 else -1),
                        ]
                        if distance
                        else []
                    )
                    candidates = list(
                        dict.fromkeys(
                            v
                            for v in candidates
                            if domain["min"] <= v <= domain["max"]
                            and abs(v - target) < abs(distance)
                        )
                    )
                else:
                    index = next(
                        i for i, v in enumerate(domain["values"]) if encoded(v) == encoded(value)
                    )
                    candidates = domain["values"][:index]
                changed = False
                for replacement in candidates:
                    if self.result["shrink_evaluations"] >= self.policy["limits"]["shrink_steps"]:
                        break
                    self.result["shrink_evaluations"] += 1
                    row = self.evaluate(function, {**current["arguments"], name: replacement})
                    if set(original["requirements"]) <= set(row["requirements"]):
                        current = row
                        self.retain(row)
                        changed = True
                        break
                if not changed:
                    break
        return current

    def execute(self):
        started = time.monotonic()
        try:
            with tempfile.TemporaryDirectory(prefix="execution-", dir=self.out) as temporary:
                root = Path(temporary)
                self.sources = {
                    "baseline": snapshot(self.repo, self.policy["baseline"], root / "baseline"),
                    "candidate": snapshot(self.repo, self.candidate, root / "candidate"),
                }
                for name, source in self.sources.items():
                    self.result[name] = source.identity()
                    write_json(self.out / (name + "-manifest.json"), source.manifest)
                    for function in self.policy["functions"]:
                        path = source.root / function["path"]
                        require(
                            path.is_file()
                            and not path.is_symlink()
                            and all(
                                not p.is_symlink()
                                for p in path.parents
                                if p.is_relative_to(source.root)
                            ),
                            "Function source missing or symlinked",
                        )
                self.integrity()
                schedule = self.schedule()
                self.result["scheduled_cases"] = len(schedule)
                self.retain_empty()
                first = {}
                for function, arguments, retained_expected in schedule:
                    row = self.evaluate(function, arguments)
                    require(
                        retained_expected is None
                        or encoded(row["expected"]) == encoded(retained_expected),
                        "Retained expectation differs from accepted baseline",
                    )
                    self.result["observations"].append(row)
                    if retained_expected is not None:
                        self.retain(row)
                    if row["requirements"]:
                        self.retain(row)
                        first.setdefault(function["id"], (function, row))
                for function, original in first.values():
                    minimized = (
                        self.minimize(function, original) if self.replay is None else original
                    )
                    self.result["counterexamples"].append(
                        {
                            "original": original,
                            "reduced": minimized,
                            "minimality": "bounded search; no global minimum claim",
                        }
                    )
                self.integrity()
                current = snapshot(self.repo, self.candidate, root / "final-source")
                require(
                    current.identity() == self.sources["candidate"].identity(),
                    "Original candidate changed during comparison",
                )
                self.remaining()
            self.result.update(status="regression" if first else "no_difference", complete=True)
        except (CheckError, OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
            self.result["diagnostics"].append(str(exc))
        self.result["execution_copies_removed"] = not any(self.out.glob("execution-*"))
        self.result["seconds"] = time.monotonic() - started
        if (self.out / "regressions.json").exists():
            self.result["regressions_sha256"] = digest((self.out / "regressions.json").read_bytes())
        write_json(self.out / "comparison.json", self.result)
        return self.result

    def retain_empty(self):
        write_json(
            self.out / "regressions.json",
            {
                "schema_version": 1,
                "policy_sha256": self.result["policy_sha256"],
                "baseline_sha256": self.sources["baseline"].sha256,
                "cases": [],
            },
        )


def compare_python(
    repo, policy, policy_sha256, out, candidate="worktree", replay=None, replay_sha256=None
):
    return Comparison(
        Path(repo),
        Path(policy),
        policy_sha256,
        Path(out),
        candidate,
        None if replay is None else Path(replay),
        replay_sha256,
    ).execute()
