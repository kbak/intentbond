"""Opt-in preservation checks against a caller-pinned change declaration."""

import re
import tempfile
from pathlib import Path

from .common import CheckError, canonical, digest, read_json, relative_path, within, write_json
from .config import load_baseline_scope, load_scope
from .evidence import load_bundle
from .impact import impact, key
from .runner import verify
from .snapshot import repository, resolve_commit, snapshot

LIMIT = (
    "Checks declared preservation only; no semantic approval, assertion-equivalence proof, "
    "or guarantee that all requirements or test dependencies were captured."
)
IDENTIFIER = re.compile(r"[A-Za-z]+~[A-Za-z0-9][A-Za-z0-9_.-]*~[0-9]+")


def _strings(value, name):
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) or not item for item in value)
        or len(set(value)) != len(value)
    ):
        raise CheckError(f"Guard {name} must be a list of distinct nonempty strings")
    return value


def _outside(path, repo, evidence):
    path = path.resolve()
    if path.is_relative_to(repo) or path.is_relative_to(evidence.parent):
        raise CheckError("Guard records must be outside the repository and evidence bundle")
    return path


def _policy(repo, base, scope_path):
    return load_scope(scope_path) if scope_path is not None else load_baseline_scope(repo, base)


def _source(repo, ref):
    if Path(tempfile.gettempdir()).resolve().is_relative_to(repo):
        raise CheckError("Guard temporary directory must be outside the repository")
    with tempfile.TemporaryDirectory(prefix="ib-guard-source-") as temporary:
        return snapshot(repo, ref, Path(temporary) / "source").identity()


def _requirements(artifacts, scope):
    return {
        item["id"]: item
        for item in artifacts
        if item["id"].split("~")[0] in scope["required_coverage"]
    }


# [impl->req~ib-change-guard-policy~1]
def _declaration(value, report, scope, manifest):
    fields = {"schema_version", "requirements", "protected_paths", "checks", "check_support_paths"}
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or type(value["schema_version"]) is not int
        or value["schema_version"] != 1
    ):
        raise CheckError("Unsupported guard declaration; use the documented schema version 1")
    actions = value["requirements"]
    if not isinstance(actions, dict) or set(actions) != {"preserve", "change", "remove", "add"}:
        raise CheckError("Guard requirements must declare preserve, change, remove and add lists")
    refs = []
    for name, identifiers in actions.items():
        refs += _strings(identifiers, name)
    checks = _strings(value["checks"], "checks")
    if any(not IDENTIFIER.fullmatch(ref) for ref in refs + checks):
        raise CheckError("Guard references require complete OFT IDs including revisions")
    if len({key(ref) for ref in refs}) != len(refs):
        raise CheckError("Guard requirement actions overlap or contain multiple revisions")
    baseline = _requirements(report["inspection"]["base_artifacts"], scope)
    if not baseline:
        raise CheckError("Guard requires an adopted baseline with selected requirements")
    for action in ("preserve", "change", "remove"):
        if not set(actions[action]) <= baseline.keys():
            raise CheckError(f"Guard {action} references an unknown baseline requirement/revision")
    old_keys = {key(ref) for ref in baseline}
    if any(
        key(ref) in old_keys or ref.split("~")[0] not in scope["required_coverage"]
        for ref in actions["add"]
    ):
        raise CheckError("Guard additions must name new requirements of selected types")
    for name in ("protected_paths", "check_support_paths"):
        for path in _strings(value[name], name):
            relative_path(path)
            if not any(within(entry["path"], [path]) for entry in manifest):
                raise CheckError(f"Guard {name} does not select captured baseline source: {path}")
    graph = {item["id"]: item for item in report["inspection"]["base_artifacts"]}
    kinds = scope["tests"].get("execution_links", {}).get("artifact_types", [])
    for ref in checks:
        item = graph.get(ref)
        if (
            not item
            or ref.split("~")[0] not in kinds
            or not within(item["path"], scope["test_paths"])
        ):
            raise CheckError(f"Guard check requires a named baseline execution artifact: {ref}")
    # Unmentioned baseline promises are preserved, never silently dropped from the plan.
    return {
        **value,
        "requirements": {
            **actions,
            "preserve": sorted(baseline.keys() - set(actions["change"] + actions["remove"])),
        },
    }


# [impl->req~ib-change-guard-policy~1]
def prepare(
    evidence_path, declaration_path, out, repo, base_ref, jar, java="java", scope_path=None
):
    repo = repository(repo)
    evidence_path = evidence_path.resolve()
    out = _outside(out, repo, evidence_path)
    declaration_path = _outside(declaration_path, repo, evidence_path)
    evidence_hash = digest(evidence_path.read_bytes())
    evidence, scope = load_bundle(evidence_path)
    base = _source(repo, resolve_commit(repo, base_ref))
    if base != evidence["base"]:
        raise CheckError("Guard baseline differs from the supplied evidence")
    if _policy(repo, base["commit"], scope_path) != scope:
        raise CheckError("Guard scope differs from caller-trusted checking policy")
    report = impact(evidence_path, jar, java)
    if report["trace"]["base"] != "passed":
        raise CheckError("Guard requires a passing baseline trace")
    declaration = _declaration(
        read_json(declaration_path),
        report,
        scope,
        read_json(evidence_path.parent / "base-manifest.json"),
    )
    if digest(evidence_path.read_bytes()) != evidence_hash:
        raise CheckError("Evidence changed while preparing guard")
    plan = {
        "schema_version": 1,
        "base": base,
        "scope_sha256": report["scope_sha256"],
        "declaration": declaration,
    }
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "plan.json", plan)
    return {
        "status": "prepared",
        "plan": str(out / "plan.json"),
        "plan_sha256": digest((out / "plan.json").read_bytes()),
        "base": base,
        "preserved_requirements": len(declaration["requirements"]["preserve"]),
        "limitations": ["Retain this plan digest in caller-controlled task/CI state.", LIMIT],
    }


def _diagnostic(result, code, severity, subject, message):
    result["diagnostics"].append(
        {"code": code, "severity": severity, "subject": subject, "message": message}
    )


# [impl->req~ib-change-guard-preservation~1]
def _preservation(plan, report, scope, result):
    actions = plan["declaration"]["requirements"]
    old = _requirements(report["inspection"]["base_artifacts"], scope)
    new = {
        key(ref): item
        for ref, item in _requirements(report["inspection"]["artifacts"], scope).items()
    }
    changes = {item["key"]: item for item in report["declarations"]}
    for action in ("preserve", "change", "remove", "add"):
        for ref in actions[action]:
            item = new.get(key(ref))
            change = changes.get(key(ref))
            result["requirements"].append(
                {"id": ref, "action": action, "candidate": item["id"] if item else None}
            )
            if action == "remove":
                if item:
                    _diagnostic(
                        result,
                        "removal_not_applied",
                        "review",
                        ref,
                        "Authorized removal is still present.",
                    )
                continue
            if item is None:
                _diagnostic(
                    result,
                    "requirement_missing" if action != "add" else "addition_missing",
                    "failure",
                    ref,
                    "Declared requirement is absent from the candidate.",
                )
                continue
            if action == "add" and item["id"] != ref:
                _diagnostic(
                    result,
                    "addition_revision_mismatch",
                    "failure",
                    ref,
                    "Candidate addition has a different revision.",
                )
            if action == "preserve" and change and change["classification"] != "location_only":
                _diagnostic(
                    result,
                    "requirement_changed",
                    "review",
                    ref,
                    "Preserved declaration changed; reassess its text, revision, Needs and links.",
                )
            if action == "preserve":
                linked = {test["id"] for test in item["linked_tests"]}
                if not linked.intersection(plan["declaration"]["checks"]):
                    _diagnostic(
                        result,
                        "requirement_unchecked",
                        "review",
                        ref,
                        "No selected retained check has current execution links to this requirement.",
                    )
    known = {key(ref) for ref in old} | {key(ref) for ref in actions["add"]}
    for name in sorted(new.keys() - known):
        _diagnostic(
            result,
            "undeclared_addition",
            "review",
            new[name]["id"],
            "New requirement was not declared for this change.",
        )
    for change in report["source_boundaries"]["paths"]:
        if within(change["path"], plan["declaration"]["protected_paths"]):
            _diagnostic(
                result,
                "protected_path_changed",
                "failure",
                change["path"],
                "Captured content, mode or presence changed inside a protected path.",
            )


# [impl->req~ib-change-guard-checks~1]
def _checks(plan, report, result):
    declaration = plan["declaration"]
    before = {item["id"]: item for item in report["inspection"]["base_artifacts"]}
    after = {item["id"]: item for item in report["inspection"]["artifacts"]}
    changed = {item["path"] for item in report["source_boundaries"]["paths"]}
    for ref in declaration["checks"]:
        old, new = before[ref], after.get(ref)
        roots = [old["path"], *declaration["check_support_paths"]]
        if new:
            roots.append(new["path"])
        modified = sorted(path for path in changed if within(path, roots))
        if modified:
            _diagnostic(
                result,
                "check_source_changed",
                "review",
                ref,
                "Retained check source/support changed; reassess assertions: "
                + ", ".join(modified),
            )
        if new is None:
            status = "missing"
        else:
            observation = next((item for item in new["linked_tests"] if item["id"] == ref), None)
            status = observation["status"] if observation else "not_established"
        result["checks"].append({"id": ref, "status": status, "changed_source_paths": modified})
        if status != "passed":
            _diagnostic(
                result,
                "check_unresolved",
                "failure" if status in {"failed", "mixed", "missing"} else "review",
                ref,
                f"Retained check must have passing observations; got {status}.",
            )


def _finish(result):
    levels = {item["severity"] for item in result["diagnostics"]}
    result["guard_status"] = (
        "rejected" if "failure" in levels else "review_required" if "review" in levels else "passed"
    )
    result["status"] = result["guard_status"]
    if result["recorded_check_status"] not in {"passed", "review_required"}:
        result["status"] = "rejected"
    elif result["recorded_check_status"] == "review_required" and result["status"] == "passed":
        result["status"] = "review_required"
    return result


# [impl->req~ib-change-guard-policy~1]
def check(
    evidence_path,
    plan_path,
    plan_sha256,
    repo,
    jar,
    java="java",
    scope_path=None,
    candidate_ref="worktree",
):
    repo = repository(repo)
    evidence_path = evidence_path.resolve()
    plan_path = _outside(plan_path, repo, evidence_path)
    if digest(plan_path.read_bytes()) != plan_sha256:
        raise CheckError("guard_plan_changed: plan differs from caller-pinned SHA-256")
    plan = read_json(plan_path)
    if (
        not isinstance(plan, dict)
        or set(plan) != {"schema_version", "base", "scope_sha256", "declaration"}
        or type(plan["schema_version"]) is not int
        or plan["schema_version"] != 1
    ):
        raise CheckError("Unsupported guard plan")
    evidence_hash = digest(evidence_path.read_bytes())
    evidence, scope = load_bundle(evidence_path)
    result = {
        "schema_version": 1,
        "plan_sha256": plan_sha256,
        "evidence_sha256": evidence_hash,
        "base": evidence["base"],
        "candidate": evidence["candidate"],
        "expected_base": plan["base"],
        "scope_sha256": evidence["scope"]["sha256"],
        "recorded_check_status": evidence["status"],
        "diagnostics": [],
        "requirements": [],
        "checks": [],
        "limitations": [LIMIT],
    }
    if evidence["base"] != plan["base"] or _source(repo, plan["base"]["commit"]) != plan["base"]:
        _diagnostic(
            result,
            "baseline_changed",
            "failure",
            "base",
            "Evidence must retain the plan's starting baseline.",
        )
    if (
        evidence["scope"]["sha256"] != plan["scope_sha256"]
        or digest(canonical(_policy(repo, plan["base"]["commit"], scope_path)))
        != plan["scope_sha256"]
    ):
        _diagnostic(
            result,
            "checking_policy_changed",
            "failure",
            "scope",
            "Evidence and current caller policy must match the frozen policy.",
        )
    if _source(repo, candidate_ref)["sha256"] != evidence["candidate"]["sha256"]:
        _diagnostic(
            result,
            "stale_evidence",
            "failure",
            "candidate",
            "Current source differs from checked evidence; run a fresh check.",
        )
    if result["diagnostics"]:
        return _finish(result)
    report = impact(evidence_path, jar, java)
    expected = _declaration(
        plan["declaration"], report, scope, read_json(evidence_path.parent / "base-manifest.json")
    )
    if expected != plan["declaration"]:
        raise CheckError("Guard plan omits preserved baseline requirements")
    _preservation(plan, report, scope, result)
    _checks(plan, report, result)
    # Reuse native verification before any passing result; rejected checks remain rejected.
    if evidence["status"] in {"passed", "review_required"}:
        verify(
            repo,
            scope_path,
            plan["base"]["commit"],
            candidate_ref,
            evidence_path,
            allow_pending_review=True,
        )
    else:
        _diagnostic(
            result,
            "native_check_not_passing",
            "failure",
            "evidence",
            "Native check remains " + evidence["status"] + "; inspect its diagnostics.",
        )
    if (
        digest(evidence_path.read_bytes()) != evidence_hash
        or digest(plan_path.read_bytes()) != plan_sha256
    ):
        raise CheckError("Guard inputs changed during evaluation")
    if _source(repo, candidate_ref)["sha256"] != evidence["candidate"]["sha256"]:
        _diagnostic(
            result,
            "stale_evidence",
            "failure",
            "candidate",
            "Source changed during guard evaluation.",
        )
    return _finish(result)


def render(result):
    lines = ["Change guard: " + result["status"]]
    if result["status"] == "prepared":
        lines += ["Plan: " + result["plan"], "Caller-pinned SHA-256: " + result["plan_sha256"]]
    else:
        lines += [
            "Preservation checks: " + result["guard_status"],
            "Native check: " + result["recorded_check_status"],
            f"Requirements: {len(result['requirements'])}; retained checks: {len(result['checks'])}",
        ]
        lines += [
            f"{item['code']}: {item['subject']}: {item['message']}"
            for item in result["diagnostics"][:10]
        ]
        if len(result["diagnostics"]) > 10:
            lines.append(
                f"{len(result['diagnostics']) - 10} more diagnostics; use --format json for all details."
            )
    lines += result["limitations"]
    return "\n".join(lines)
