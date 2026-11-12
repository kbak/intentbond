"""Opt-in, caller-adapted repair in an isolated Git copy; never an approval service."""

import ast
import io
import json
import sys
import tempfile
import time
import tokenize
from concurrent.futures import ThreadPoolExecutor
from hashlib import file_digest
from pathlib import Path

from .change_guard import IDENTIFIER
from .common import CheckError, canonical, digest, read_json, relative_path, run, within, write_json
from .config import load_baseline_scope, load_scope
from .snapshot import repository, resolve_commit, snapshot

LIMIT = "Finite caller-supplied checks, not proof, authenticated provenance, or semantic approval."
MAX_RESPONSE = 16 * 1024 * 1024


def input_digest(path):
    with Path(path).open("rb") as source:
        return file_digest(source, "sha256").hexdigest()


def require(condition, message):
    if not condition:
        raise CheckError(message)


def json_value(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise CheckError("Repair values must be finite JSON") from exc


def identity(repo):
    with tempfile.TemporaryDirectory(prefix="ib-repair-source-") as temp:
        return snapshot(repo, "worktree", Path(temp) / "source").identity()


def outside(path, repo):
    path = path.resolve()
    require(
        not path.is_relative_to(repo), "Repair policy, adapters and output must be outside source"
    )
    return path


# [impl->req~ib-repair-policy~1]
def policy(value, scope, plan):
    require(
        isinstance(value, dict)
        and set(value) - {"completion"}
        == {"schema_version", "requirements", "edits", "adapter", "regression", "limits"}
        and type(value["schema_version"]) is int
        and value["schema_version"] == 1,
        "Unsupported repair policy",
    )
    refs = value["requirements"]
    require(
        isinstance(refs, list)
        and refs
        and len(refs) == len(set(refs))
        and all(isinstance(r, str) and IDENTIFIER.fullmatch(r) for r in refs),
        "Select distinct maintained requirement references",
    )
    require(
        set(refs) <= set(plan["declaration"]["requirements"]["preserve"]),
        "Repair requirements must be preserved by the caller's guard",
    )
    require(plan["declaration"]["checks"], "Select retained checks in the guard declaration")
    edits = value["edits"]
    require(isinstance(edits, list) and edits, "Declare Python function edit boundaries")
    paths = []
    for edit in edits:
        require(
            isinstance(edit, dict) and set(edit) == {"path", "symbol", "requirements"},
            "Invalid repair boundary",
        )
        paths.append(relative_path(edit["path"]))
        require(
            within(edit["path"], scope["inputs"])
            and edit["path"].endswith(".py")
            and isinstance(edit["symbol"], str)
            and all(p.isidentifier() for p in edit["symbol"].split(".")),
            "Repair boundaries select named Python functions",
        )
        require(
            edit["requirements"] and set(edit["requirements"]) <= set(refs),
            "Repair boundary must reference selected requirements",
        )
        require(
            not within(
                edit["path"],
                scope["specification_paths"]
                + scope["test_paths"]
                + plan["declaration"]["protected_paths"],
            ),
            "Repair boundary overlaps a specification, test or protected path",
        )
    require(len(paths) == len(set(paths)), "Select one function per editable file")
    regression = value["regression"]
    require(
        isinstance(regression, dict)
        and set(regression) == {"test_path", "data_path", "links_path", "checks"},
        "Invalid regression policy",
    )
    for key in ("test_path", "data_path", "links_path"):
        path = relative_path(regression[key])
        require(
            within(path, scope["test_paths"]) and within(path, scope["inputs"]),
            "Regression artifacts must be selected test inputs",
        )
        require(
            not within(path, plan["declaration"]["protected_paths"]), "Protected regression path"
        )
    require(
        len({regression[k] for k in ("test_path", "data_path", "links_path")}) == 3,
        "Regression paths must be distinct",
    )
    require(
        regression["test_path"].endswith(".py") and regression["data_path"].endswith(".json"),
        "Regression scaffold is Python with retained JSON cases",
    )
    checks = regression["checks"]
    require(
        isinstance(checks, list)
        and checks
        and len(checks) == len(set(checks))
        and all(isinstance(c, str) and IDENTIFIER.fullmatch(c) for c in checks),
        "Declare distinct new executed regression identities",
    )
    require(
        not set(checks) & set(plan["declaration"]["checks"]),
        "New regression checks reuse retained IDs",
    )
    require(scope["tests"].get("execution_links"), "Repair needs native execution links")
    adapter = value["adapter"]
    require(
        isinstance(adapter, dict) and set(adapter) == {"command", "inputs"},
        "Invalid adapter policy",
    )
    require(
        isinstance(adapter["command"], list)
        and adapter["command"]
        and all(isinstance(arg, str) and arg for arg in adapter["command"])
        and Path(adapter["command"][0]).is_absolute(),
        "Adapter command needs an absolute executable",
    )
    require(
        isinstance(adapter["inputs"], dict) and adapter["inputs"], "Pin adapter/reference inputs"
    )
    for name, sha in adapter["inputs"].items():
        require(
            Path(name).is_absolute() and isinstance(sha, str) and len(sha) == 64,
            "Adapter inputs require absolute paths and SHA-256",
        )
    require(
        any(arg in adapter["inputs"] for arg in adapter["command"]), "Pin the adapter entry point"
    )
    # [impl->req~ib-repair-completion~1]
    if "completion" in value:
        completion = value["completion"]
        require(
            isinstance(completion, dict) and set(completion) == {"request", "command", "inputs"},
            "Invalid completion policy",
        )
        command, inputs = completion["command"], completion["inputs"]
        require(
            isinstance(command, list)
            and command
            and all(isinstance(arg, str) and arg for arg in command)
            and Path(command[0]).is_absolute()
            and isinstance(inputs, dict)
            and inputs,
            "Completion needs a pinned checker command",
        )
        require(
            isinstance(completion["request"], str)
            and completion["request"] in inputs
            and any(arg in inputs for arg in command),
            "Pin the completion request and checker entry point",
        )
        for name, sha in inputs.items():
            require(
                Path(name).is_absolute()
                and isinstance(sha, str)
                and len(sha) == 64
                and all(c in "0123456789abcdef" for c in sha),
                "Completion inputs require absolute paths and SHA-256",
            )
            require(
                name not in adapter["inputs"] or adapter["inputs"][name] == sha,
                "Conflicting completion and adapter pins",
            )
    limits = value["limits"]
    require(
        isinstance(limits, dict) and set(limits) == {"seconds", "repairs", "cases"},
        "Invalid repair limits",
    )
    require(
        type(limits["seconds"]) in (int, float)
        and 0 < limits["seconds"] <= 600
        and type(limits["repairs"]) is int
        and 0 <= limits["repairs"] <= 2
        and type(limits["cases"]) is int
        and 1 <= limits["cases"] <= 1000,
        "Repair limits exceed supported bounds",
    )
    return value


# [impl->req~ib-repair-boundaries~1]
def outside_symbol(text, symbol):
    """Mask only the selected body, preserving signatures, decorators and other bytes."""
    data = text.encode("utf-8")
    tree = ast.parse(text)
    for part in symbol.split("."):
        matches = [
            n
            for n in tree.body
            if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name == part
        ]
        require(len(matches) == 1, "Repair symbol missing or ambiguous: " + symbol)
        tree = matches[0]
    require(
        isinstance(tree, (ast.FunctionDef, ast.AsyncFunctionDef)),
        "Repair symbol must be a function",
    )
    lines = data.splitlines(keepends=True)
    first, last = tree.body[0], tree.body[-1]
    start = sum(map(len, lines[: first.lineno - 1])) + first.col_offset
    # The first logical newline after def ends either the header (a block
    # suite) or the inline suite. Tokenization handles multiline signatures,
    # annotations and decorators without guessing which colon opens the body.
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    header = next(
        t
        for t in tokenize.generate_tokens(io.StringIO(normalized).readline)
        if t.type == tokenize.NEWLINE and t.start[0] >= tree.lineno
    )

    def indentation(line):
        prefix = line[: len(line) - len(line.lstrip(b" \t\f"))]
        return len(prefix.split(b"\f")[-1].expandtabs(8))

    def blank(line):
        return not line.strip(b" \t\f\r\n")

    level = indentation(lines[tree.lineno - 1])

    def body_comment(line):
        return line.lstrip(b" \t\f").startswith(b"#") and indentation(line) > level

    end_line = last.end_lineno - 1
    if header.start[0] < first.lineno:
        start_line = header.end[0]
        # Comments at the enclosing indentation remain protected, even though
        # Python ignores their indentation while looking for the first statement.
        for row in range(start_line, first.lineno - 1):
            line = lines[row]
            if not blank(line) and not line.lstrip(b" \t\f").startswith(b"#"):
                break
            if not blank(line) and not body_comment(line):
                start_line = row + 1
        start = sum(map(len, lines[:start_line]))
        for row in range(end_line + 1, len(lines)):
            if body_comment(lines[row]):
                end_line = row
            elif not blank(lines[row]):
                break
    # Include inline/trailing body comments, but retain the final physical
    # newline and unanchored separator blank lines outside the body.
    end = sum(map(len, lines[:end_line])) + len(lines[end_line].rstrip(b"\r\n"))
    return data[:start] + b"<repair-body>" + data[end:]


def safe_file(root, name):
    relative_path(name)
    target = root / name
    require(
        not any(p.is_symlink() for p in (target, *target.parents) if p.is_relative_to(root)),
        "Repair paths cannot traverse symlinks",
    )
    return target


class Session:
    def __init__(
        self, repo, scope_path, plan_path, plan_sha256, policy_path, policy_sha256, out, jar, java
    ):
        self.repo = repository(repo)
        self.scope_path = scope_path.resolve() if scope_path else None
        self.plan_path, self.policy_path = (
            outside(plan_path, self.repo),
            outside(policy_path, self.repo),
        )
        self.plan_hash, self.policy_hash = plan_sha256, policy_sha256
        require(digest(self.plan_path.read_bytes()) == self.plan_hash, "Caller guard pin mismatch")
        require(
            digest(self.policy_path.read_bytes()) == self.policy_hash,
            "Caller repair policy pin mismatch",
        )
        self.plan = read_json(self.plan_path)
        self.base = resolve_commit(self.repo, self.plan["base"]["commit"])
        self.scope = (
            load_scope(self.scope_path)
            if self.scope_path
            else load_baseline_scope(self.repo, self.base)
        )
        require(
            digest(canonical(self.scope)) == self.plan["scope_sha256"],
            "Guard and repair checking policy differ",
        )
        self.policy = policy(read_json(self.policy_path), self.scope, self.plan)
        self.out = outside(out, self.repo)
        for path in (
            self.plan_path,
            self.policy_path,
            *map(Path, self.policy["adapter"]["inputs"]),
            *map(Path, self.policy.get("completion", {}).get("inputs", {})),
        ):
            require(
                not path.resolve().is_relative_to(self.out),
                "Trusted inputs cannot be inside repair output",
            )
            outside(path, self.repo)
        self.out.mkdir(parents=True, exist_ok=False)
        self.work = self.out / "work"
        self.jar, self.java = jar.resolve(), java
        self.started = time.monotonic()
        self.deadline = self.started + self.policy["limits"]["seconds"]
        self.calls, self.cases, self.scaffold = [], [], {}
        self.expected_source = None
        self.original = identity(self.repo)
        self.result = {
            "schema_version": 1,
            "status": "unresolved",
            "loop_status": "unresolved",
            "repairs": 0,
            "adversarial_passes": 0,
            "policy_sha256": policy_sha256,
            "plan_sha256": plan_sha256,
            "original": self.original,
            "limitations": [LIMIT],
        }
        if "completion" in self.policy:
            self.result["completion"] = {"status": "not_checked"}
        write_json(self.out / "policy.json", self.policy)
        write_json(self.out / "guard-plan.json", self.plan)
        write_json(self.out / "scope.json", self.scope)

    def remaining(self):
        seconds = self.deadline - time.monotonic()
        require(seconds > 0, "aggregate_budget_exhausted")
        return seconds

    def pins(self):
        self.remaining()
        require(digest(self.plan_path.read_bytes()) == self.plan_hash, "guard_plan_changed")
        require(digest(self.policy_path.read_bytes()) == self.policy_hash, "repair_policy_changed")
        scope = (
            load_scope(self.scope_path)
            if self.scope_path
            else load_baseline_scope(self.repo, self.base)
        )
        require(digest(canonical(scope)) == self.plan["scope_sha256"], "checking_policy_changed")
        require(
            digest(canonical(read_json(self.out / "scope.json"))) == self.plan["scope_sha256"],
            "copied_checking_policy_changed",
        )
        if self.expected_source is not None:
            require(
                identity(self.work)["sha256"] == self.expected_source,
                "candidate_changed_outside_repair",
            )
        inputs = self.policy["adapter"]["inputs"]
        # Rehash every byte at every boundary, with bounded parallel reads and no cache.
        # map preserves input/error order; exiting the pool joins every pending read.
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                for path, actual in zip(inputs, pool.map(input_digest, inputs)):
                    require(actual == inputs[path], "adapter_input_changed: " + path)
        except RuntimeError as exc:
            raise CheckError("adapter_input_hashing_failed: " + str(exc)) from exc
        for path, sha in self.policy.get("completion", {}).get("inputs", {}).items():
            require(not Path(path).is_symlink(), "completion_input_symlink: " + path)
            with Path(path).open("rb") as source:
                actual = file_digest(source, "sha256").hexdigest()
            require(actual == sha, "completion_input_changed: " + path)
        for path, sha in self.scaffold.items():
            require(
                digest(safe_file(self.work, path).read_bytes()) == sha,
                "regression_scaffold_changed",
            )

    def command(self, args, tag, allowed=(0,)):
        self.pins()
        outcome = run(args, self.out, self.out / (tag + ".log"), timeout=self.remaining())
        self.calls.append({"phase": tag, **outcome})
        write_json(self.out / "commands.json", self.calls)
        self.pins()
        require(
            outcome["status"] != "error" and outcome["exit_code"] in allowed,
            "command_failed_or_timed_out: " + tag,
        )
        return outcome

    def native(self, tag, regression=True):
        evidence = self.out / (tag + "-evidence") / "evidence.json"
        options = ["--repo", str(self.work), "--scope", str(self.out / "scope.json")]
        prefix = [sys.executable, "-m", "intentbond"]
        self.command(
            prefix
            + [
                "check",
                *options,
                "--base",
                self.base,
                "--out",
                str(evidence.parent),
                "--oft-jar",
                str(self.jar),
                "--java",
                self.java,
            ],
            tag + "-check",
            (0, 1, 3, 4),
        )
        self.command(
            prefix
            + [
                "guard",
                "check",
                *options,
                "--evidence",
                str(evidence),
                "--plan",
                str(self.plan_path),
                "--plan-sha256",
                self.plan_hash,
                "--oft-jar",
                str(self.jar),
                "--java",
                self.java,
                "--format",
                "json",
            ],
            tag + "-guard",
            (0, 1, 4),
        )
        guard = read_json(self.out / (tag + "-guard.log"))
        native = read_json(evidence)["predicate"]
        # New counterexample failures can drive repair; baseline preservation failures cannot.
        bad = [d for d in guard["diagnostics"] if d["code"] != "native_check_not_passing"]
        self.result["native"] = {
            "status": native["status"],
            "evidence": str(evidence),
            "guard": guard,
        }
        if bad:
            self.reject("preservation_failed")
            return False
        if regression:
            associations = native["tests"].get("execution_links", {}).get("artifacts", [])
            new = {a["id"]: a["status"] for a in associations}
            self.result["regression_execution"] = {
                c: new.get(c, "not_established") for c in self.policy["regression"]["checks"]
            }
        return native["status"] in {"passed", "review_required"}

    def adapter(self, phase, **payload):
        self.pins()
        before = identity(self.work)
        folder = self.out / f"adapter-{len(self.calls):03}-{phase}"
        folder.mkdir()
        request, response = folder / "request.json", folder / "response.json"
        write_json(
            request,
            {
                "schema_version": 1,
                "phase": phase,
                "worktree": str(self.work),
                "source_sha256": before["sha256"],
                "requirements": self.policy["requirements"],
                "remaining_seconds": self.remaining(),
                **payload,
            },
        )
        self.command([*self.policy["adapter"]["command"], str(request), str(response)], folder.name)
        require(identity(self.work) == before, "adapter_modified_candidate")
        require(
            response.is_file() and response.stat().st_size <= MAX_RESPONSE,
            "missing_or_oversized_adapter_response",
        )
        value = read_json(response)
        json_value(value)
        require(
            isinstance(value, dict) and value.get("source_sha256") == before["sha256"],
            "stale_adapter_response",
        )
        return value

    # [impl->req~ib-repair-cases~1]
    def generate(self, stage):
        answer = self.adapter("generate", stage=stage, cases=self.cases)
        rows = answer.get("cases")
        require(isinstance(rows, list) and rows, "empty_case_batch")
        require(
            len(self.cases) + len(rows) <= self.policy["limits"]["cases"], "case_budget_exhausted"
        )
        ids = {c["id"] for c in self.cases}
        for row in rows:
            require(
                isinstance(row, dict)
                and set(row) == {"id", "requirements", "kind", "input", "accepted", "label"},
                "Invalid repair case",
            )
            require(
                isinstance(row["id"], str) and row["id"] and row["id"] not in ids,
                "duplicate_case_id",
            )
            ids.add(row["id"])
            require(
                row["requirements"]
                and set(row["requirements"]) <= set(self.policy["requirements"]),
                "unmapped_case",
            )
            require(
                row["kind"] in {"positive", "negative_input", "negative_output"},
                "unknown_case_kind",
            )
            label = row["label"]
            require(
                isinstance(label, dict) and label.get("status") == "confirmed",
                "unresolved_reference_label",
            )
            require(
                label.get("method")
                and isinstance(label.get("sources"), list)
                and label["sources"]
                and set(label["sources"]) <= set(self.policy["adapter"]["inputs"]),
                "unpinned_reference_provenance",
            )
            require(
                isinstance(row["accepted"], list) and row["accepted"], "empty_accepted_outcomes"
            )
        if stage == "initial":
            require(
                set(self.policy["requirements"]) <= {r for c in rows for r in c["requirements"]},
                "uncovered_selected_requirement",
            )
            require(any(c["kind"] == "positive" for c in rows), "no_positive_control")
        self.cases.extend(rows)
        write_json(self.out / "cases.json", self.cases)

    # [impl->req~ib-repair-regressions~1]
    def regressions(self):
        config = self.policy["regression"]
        if not self.scaffold:
            answer = self.adapter("regression", regression=config, cases=self.cases)
            require(
                set(answer) == {"source_sha256", "test", "links"}
                and isinstance(answer["test"], str),
                "Invalid regression scaffold",
            )
            ast.parse(answer["test"])
            test = safe_file(self.work, config["test_path"])
            data = safe_file(self.work, config["data_path"])
            require(not test.exists() and not data.exists(), "Regression paths already exist")
            links = safe_file(self.work, config["links_path"])
            previous = read_json(links)
            additions = answer["links"]
            require(
                isinstance(previous, dict)
                and isinstance(additions, dict)
                and additions
                and not set(previous) & set(additions),
                "Regression links must be additive",
            )
            require(
                all(
                    isinstance(v, list) and v and set(v) <= set(config["checks"])
                    for v in additions.values()
                )
                and {c for v in additions.values() for c in v} == set(config["checks"]),
                "Regression links must cover declared checks",
            )
            test.parent.mkdir(parents=True, exist_ok=True)
            test.write_text(answer["test"], encoding="utf-8")
            write_json(links, {**previous, **additions})
            self.scaffold = {
                name: digest((self.work / name).read_bytes())
                for name in (config["test_path"], config["links_path"])
            }
            write_json(self.out / "regression-scaffold.json", self.scaffold)
        safe_file(self.work, config["data_path"]).parent.mkdir(parents=True, exist_ok=True)
        write_json(self.work / config["data_path"], self.cases)
        self.expected_source = identity(self.work)["sha256"]

    def observe(self):
        answer = self.adapter("observe", cases=self.cases)
        observations = answer.get("observations")
        require(
            isinstance(observations, list) and len(observations) == len(self.cases),
            "incomplete_observations",
        )
        require(
            all(isinstance(r, dict) and isinstance(r.get("id"), str) for r in observations),
            "invalid_observation",
        )
        by_id = {r["id"]: r for r in observations}
        require(
            len(by_id) == len(observations) and set(by_id) == {c["id"] for c in self.cases},
            "duplicate_or_unscheduled_observation",
        )
        failures = []
        for case in self.cases:
            row = by_id[case["id"]]
            require(
                row.get("status") in {"returned", "candidate_exception"}, "unresolved_observation"
            )
            if (
                row["status"] != "returned"
                or "value" not in row
                or json_value(row["value"]) not in {json_value(v) for v in case["accepted"]}
            ):
                failures.append({"case": case, "observed": row})
        write_json(
            self.out
            / f"failures-{self.result['repairs']}-{self.result['adversarial_passes']}.json",
            failures,
        )
        return failures

    # [impl->req~ib-repair-boundaries~1]
    def propose(self, failures):
        answer = self.adapter(
            "propose",
            failures=failures[:8],
            failure_count=len(failures),
            round=self.result["repairs"] + 1,
        )
        proposal = answer.get("proposal")
        require(proposal is not None, "no_in_scope_repair")
        attempt = self.out / f"repair-{self.result['repairs'] + 1}"
        attempt.mkdir()
        write_json(attempt / "proposal.json", proposal)
        require(
            isinstance(proposal, dict) and set(proposal) == {"targets", "reason", "files"},
            "Invalid repair proposal",
        )
        implicated = {r for f in failures for r in f["case"]["requirements"]}
        require(
            proposal["targets"]
            and set(proposal["targets"]) <= implicated
            and isinstance(proposal["reason"], str),
            "unattributed_repair",
        )
        allowed = {
            e["path"]: e
            for e in self.policy["edits"]
            if set(e["requirements"]) & set(proposal["targets"])
        }
        updates = proposal["files"]
        if not isinstance(updates, dict) or not updates or not set(updates) <= set(allowed):
            self.reject("repair_scope_violation")
            return
        try:
            for name, text in updates.items():
                require(isinstance(text, str) and len(text) <= 100000, "Invalid proposed source")
                old = safe_file(self.work, name).read_text(encoding="utf-8")
                require(
                    old != text
                    and outside_symbol(old, allowed[name]["symbol"])
                    == outside_symbol(text, allowed[name]["symbol"]),
                    "repair_scope_violation",
                )
        except (CheckError, SyntaxError):
            self.reject("repair_scope_violation")
            return
        snapshot(self.work, "worktree", attempt / "before")
        for name, text in updates.items():
            (self.work / name).write_text(text, encoding="utf-8")
        snapshot(self.work, "worktree", attempt / "after")
        self.expected_source = identity(self.work)["sha256"]
        self.result["repairs"] += 1

    def reject(self, reason):
        self.result.update(status="rejected", loop_status="rejected", reason=reason)

    # [impl->req~ib-repair-completion~1]
    def completion(self, cycle):
        """Check the requested change separately from retained behavioral cases."""
        if "completion" not in self.policy:
            return []
        config = self.policy["completion"]
        self.result["completion"] = {"status": "unresolved"}
        self.pins()
        before = identity(self.work)
        task = Path(config["request"])
        require(task.stat().st_size <= MAX_RESPONSE, "oversized_completion_request")
        text = task.read_text(encoding="utf-8")
        require(text.strip(), "empty_completion_request")
        binding = {
            "source_sha256": before["sha256"],
            "request_sha256": config["inputs"][config["request"]],
            "checker_sha256": digest(canonical(config)),
        }
        folder = self.out / f"completion-{cycle}"
        folder.mkdir()
        request, response = folder / "request.json", folder / "response.json"
        self.result["completion"].update(binding, evidence=str(response))
        write_json(
            request,
            {
                "schema_version": 1,
                **binding,
                "worktree": str(self.work),
                "request": str(task),
                "remaining_seconds": self.remaining(),
            },
        )
        self.command([*config["command"], str(request), str(response)], folder.name)
        require(identity(self.work) == before, "completion_checker_modified_candidate")
        require(
            response.is_file()
            and not response.is_symlink()
            and response.stat().st_size <= MAX_RESPONSE,
            "missing_or_oversized_completion_response",
        )
        answer = read_json(response)
        json_value(answer)
        require(
            isinstance(answer, dict)
            and set(answer) == {"schema_version", *binding, "status", "errors"}
            and type(answer["schema_version"]) is int
            and answer["schema_version"] == 1,
            "invalid_completion_response",
        )
        require(all(answer[k] == v for k, v in binding.items()), "stale_completion_response")
        errors = answer["errors"]
        require(
            answer["status"] in {"passed", "failed"}
            and isinstance(errors, list)
            and all(isinstance(e, str) and e.strip() for e in errors)
            and bool(errors) == (answer["status"] == "failed"),
            "unresolved_completion_response",
        )
        self.result["completion"].update(status=answer["status"], errors=errors)
        if answer["status"] == "passed":
            return []
        return [
            {
                "case": {
                    "id": "requested-change-completion",
                    "kind": "requested_change",
                    "requirements": self.policy["requirements"],
                    "input": {"request": text, **binding},
                    "accepted": ["passed"],
                },
                "observed": {"status": "failed", "errors": errors},
            }
        ]

    # [impl->req~ib-repair-loop~1]
    def execute(self):
        try:
            self.pins()
            snap = snapshot(self.repo, "worktree", self.work)
            # Fetch only local immutable commits; preserve the exact uncommitted source snapshot.
            git = [
                "git",
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "init.templateDir=",
                "-C",
                str(self.work),
            ]
            self.command([*git, "init", "-q"], "git-init")
            self.command(
                [*git, "fetch", "--no-tags", str(self.repo), snap.commit, self.base], "git-fetch"
            )
            self.command([*git, "reset", "--mixed", snap.commit], "git-index")
            require(identity(self.work)["sha256"] == self.original["sha256"], "source_copy_changed")
            self.expected_source = self.original["sha256"]
            if not self.native("initial", regression=False):
                self.reject("starting_native_checks_not_passing")
                return self.result
            self.generate("initial")
            self.regressions()
            for cycle in range(self.policy["limits"]["repairs"] + 2):
                failures = self.observe()
                native_pass = self.native(f"cycle-{cycle}")
                if self.result["loop_status"] == "rejected":
                    break
                failures.extend(self.completion(cycle))
                if failures:
                    if self.result["repairs"] >= self.policy["limits"]["repairs"]:
                        self.reject("repair_budget_exhausted")
                        break
                    self.propose(failures)
                    if self.result["loop_status"] == "rejected":
                        break
                    continue
                if not native_pass or any(
                    s != "passed" for s in self.result["regression_execution"].values()
                ):
                    self.reject("native_or_regression_checks_not_passing")
                    break
                if not self.result["adversarial_passes"]:
                    self.result["adversarial_passes"] = 1
                    self.generate("adversarial")
                    self.regressions()
                    continue
                evidence = self.result["native"]["evidence"]
                self.command(
                    [
                        sys.executable,
                        "-m",
                        "intentbond",
                        "verify",
                        "--repo",
                        str(self.work),
                        "--base",
                        self.base,
                        "--scope",
                        str(self.out / "scope.json"),
                        "--evidence",
                        evidence,
                        "--allow-pending-review",
                    ],
                    "final-verify",
                    (0, 4),
                )
                verification = read_json(self.out / "final-verify.log")
                require(verification["status"] == "matched", "final_evidence_mismatch")
                self.result.update(
                    status=self.result["native"]["status"],
                    loop_status="passed",
                    reason="checks_and_bounded_search_passed",
                    verification=verification,
                )
                break
            else:
                raise CheckError("iteration_budget_exhausted")
        except (CheckError, OSError, ValueError, TypeError, KeyError, SyntaxError) as exc:
            self.result.update(status="unresolved", loop_status="unresolved", reason=str(exc))
        finally:
            self.result.update(
                cases=len(self.cases), elapsed_seconds=round(time.monotonic() - self.started, 3)
            )
            if (self.work / ".git").exists():
                self.result["candidate"] = snapshot(
                    self.work, "worktree", self.out / "frozen"
                ).identity()
                completion = self.result.get("completion", {})
                if (
                    completion.get("status") == "passed"
                    and completion.get("source_sha256") != self.result["candidate"]["sha256"]
                ):
                    completion.update(status="unresolved", reason="completion_candidate_changed")
                    self.result.update(
                        status="unresolved",
                        loop_status="unresolved",
                        reason="completion_candidate_changed",
                    )
            self.result["original_unchanged"] = identity(self.repo) == self.original
            if not self.result["original_unchanged"]:
                self.result.update(
                    status="unresolved", loop_status="unresolved", reason="original_source_changed"
                )
            write_json(self.out / "result.json", self.result)
        return self.result


def repair(repo, scope, plan, plan_sha256, policy_path, policy_sha256, out, jar, java="java"):
    try:
        return Session(
            repo, scope, plan, plan_sha256, policy_path, policy_sha256, out, jar, java
        ).execute()
    except (TypeError, KeyError, ValueError) as exc:
        raise CheckError(f"Invalid repair input: {exc}") from exc
