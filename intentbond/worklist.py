"""Local, source-bound review progress. Completion never grants approval."""

import os
import tempfile
from collections import Counter
from pathlib import Path

from .common import CheckError, canonical, digest, read_json
from .config import load_baseline_scope, load_scope
from .evidence import load_bundle
from .impact import impact
from .snapshot import repository, snapshot

LIMIT = "Review progress only; check results, pending semantic review and assurance decisions remain unchanged."
STATES = {"pending", "reviewed", "deferred"}


# [impl->req~ib-review-worklist~1]
def tasks(report):
    """Freeze all changed files plus changed/affected items and immediate neighbors."""
    graphs = {
        "base": {item["id"]: item for item in report["inspection"]["base_artifacts"]},
        "candidate": {item["id"]: item for item in report["inspection"]["artifacts"]},
    }
    seeds = {label: set() for label in graphs}
    result = []
    for change in report["inspection"]["changed_files"]:
        result.append({"id": "file:" + change["path"], "kind": "file", **change})
        for label in graphs:
            seeds[label].update(change[f"{label}_artifacts"])
    for change in report["declarations"]:
        for label, field in (("base", "before"), ("candidate", "after")):
            if change[field]:
                seeds[label].add(change[field])
    selected_by_snapshot = {}
    for label, graph in graphs.items():
        selected = set(seeds[label])
        for ref in sorted(seeds[label]):
            item = graph.get(ref, {})
            selected.update(item.get("covers", []))
            selected.update(item.get("covered_by", []))
        selected_by_snapshot[label] = selected
    for label, graph in graphs.items():
        selected = selected_by_snapshot[label]
        for ref in sorted(selected):
            if ref in graph:
                # Show unchanged neighbors once, with candidate execution context.
                current = graphs["candidate"].get(ref)
                if (
                    label == "base"
                    and current
                    and all(current.get(name) == value for name, value in graph[ref].items())
                ):
                    selected_by_snapshot["candidate"].add(ref)
                    continue
                result.append(
                    {
                        "id": f"artifact:{label}:{ref}",
                        "kind": "artifact",
                        "snapshot": label,
                        "reason": "changed_file_or_declaration"
                        if ref in seeds[label]
                        else "immediate_link",
                        "artifact": graph[ref],
                    }
                )
    return result


def _atomic(path, value):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=".progress-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(canonical(value) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


# [impl->req~ib-review-worklist~1]
def _match_source(evidence, scope, repo, scope_path):
    repo = repository(repo)
    if Path(tempfile.gettempdir()).resolve().is_relative_to(repo):
        raise CheckError("Review temporary directory must be outside the repository")
    policy = (
        load_scope(scope_path)
        if scope_path is not None
        else load_baseline_scope(repo, evidence["base"]["commit"])
    )
    if policy != scope:
        raise CheckError(
            "Review scope differs from checked policy; use the original trusted --scope"
        )
    with tempfile.TemporaryDirectory(prefix="ib-review-source-") as temporary:
        for label, ref in (("base", evidence["base"]["commit"]), ("candidate", "worktree")):
            captured = snapshot(repo, ref, Path(temporary) / label)
            if captured.sha256 != evidence[label]["sha256"]:
                raise CheckError(
                    f"Review {label} source differs from checked evidence; run a fresh check and start a new worklist"
                )
    return repo


# [impl->req~ib-review-worklist~1]
def start(evidence_path, out, repo, jar, java="java", scope_path=None):
    evidence_path = evidence_path.resolve()
    out = out.resolve()
    repo = repository(repo)
    if out.is_relative_to(repo) or out.is_relative_to(evidence_path.parent):
        raise CheckError("Worklist output must be outside the repository and evidence bundle")
    evidence_sha256 = digest(evidence_path.read_bytes())
    report = impact(evidence_path, jar, java)
    evidence, scope = load_bundle(
        evidence_path, {"review.json", "base-items.xml", "candidate-items.xml"}
    )
    _match_source(evidence, scope, repo, scope_path)
    if digest(evidence_path.read_bytes()) != evidence_sha256:
        raise CheckError("Evidence changed while freezing review; retry with an immutable bundle")
    plan = {
        "schema_version": 1,
        "repo": str(repo),
        "evidence": str(evidence_path),
        "scope": str(scope_path.resolve()) if scope_path is not None else None,
        "evidence_sha256": evidence_sha256,
        "report": report,
    }
    progress = {
        "schema_version": 1,
        "plan_sha256": digest(canonical(plan)),
        "items": [
            {"id": item["id"], "state": "pending", "message": "", "history": []}
            for item in tasks(report)
        ],
    }
    out.mkdir(parents=True, exist_ok=False)
    _atomic(out / "plan.json", plan)
    _atomic(out / "progress.json", progress)
    return _view(plan, progress)


def _load(worklist, evidence_path=None, repo=None, scope_path=None):
    worklist = worklist.resolve()
    for name in ("plan.json", "progress.json"):
        if (worklist / name).is_symlink():
            raise CheckError("Worklist records must be regular files")
    plan = read_json(worklist / "plan.json")
    progress = read_json(worklist / "progress.json")
    if (
        not isinstance(plan, dict)
        or set(plan) != {"schema_version", "repo", "evidence", "scope", "evidence_sha256", "report"}
        or type(plan["schema_version"]) is not int
        or plan["schema_version"] != 1
    ):
        raise CheckError("Unsupported review plan")
    if (
        not isinstance(progress, dict)
        or set(progress) != {"schema_version", "plan_sha256", "items"}
        or type(progress["schema_version"]) is not int
        or progress["schema_version"] != 1
        or progress["plan_sha256"] != digest(canonical(plan))
    ):
        raise CheckError("Review progress does not match the frozen plan")
    expected = tasks(plan["report"])
    if (
        not isinstance(progress["items"], list)
        or any(not isinstance(item, dict) for item in progress["items"])
        or [item.get("id") for item in progress["items"]] != [item["id"] for item in expected]
    ):
        raise CheckError("Review progress omits, duplicates or reorders frozen tasks")
    for item in progress["items"]:
        if (
            set(item) != {"id", "state", "message", "history"}
            or item["state"] not in STATES
            or not isinstance(item["message"], str)
            or (item["state"] != "pending" and not item["message"].strip())
        ):
            raise CheckError("Invalid review state; reviewed/deferred tasks need a note")
        if not isinstance(item["history"], list):
            raise CheckError("Invalid review note history")
        for event in item["history"]:
            if (
                not isinstance(event, dict)
                or set(event) != {"state", "message"}
                or event["state"] not in STATES
                or not isinstance(event["message"], str)
                or (event["state"] != "pending" and not event["message"].strip())
            ):
                raise CheckError("Invalid review note history")
        latest = item["history"][-1] if item["history"] else {"state": "pending", "message": ""}
        if latest != {"state": item["state"], "message": item["message"]}:
            raise CheckError("Review state differs from its retained note history")
    evidence_path = (evidence_path or Path(plan["evidence"])).resolve()
    evidence, scope = load_bundle(
        evidence_path, {"review.json", "base-items.xml", "candidate-items.xml"}
    )
    if (
        digest(evidence_path.read_bytes()) != plan["evidence_sha256"]
        or any(plan["report"][label] != evidence[label] for label in ("base", "candidate"))
        or plan["report"]["scope_sha256"] != evidence["scope"]["sha256"]
    ):
        raise CheckError("Worklist belongs to different evidence; start a new worklist")
    repo = repo or Path(plan["repo"])
    if worklist.is_relative_to(repo.resolve()) or worklist.is_relative_to(evidence_path.parent):
        raise CheckError("Worklist must remain outside the repository and evidence bundle")
    scope_path = scope_path or (Path(plan["scope"]) if plan["scope"] is not None else None)
    _match_source(evidence, scope, repo, scope_path)
    return plan, progress


def _view(plan, progress):
    counts = Counter(item["state"] for item in progress["items"])
    pending = next((item["id"] for item in progress["items"] if item["state"] == "pending"), None)
    merged = [{**task, **state} for task, state in zip(tasks(plan["report"]), progress["items"])]
    return {
        "schema_version": 1,
        "context_sha256": progress["plan_sha256"],
        "source": plan["report"]["candidate"],
        "scope_sha256": plan["report"]["scope_sha256"],
        "recorded_check_status": plan["report"]["recorded_check_status"],
        "recorded_review": plan["report"]["review"],
        "status": "reviewed" if not counts["pending"] and not counts["deferred"] else "incomplete",
        "counts": {name: counts[name] for name in sorted(STATES)},
        "current": next((item for item in merged if item["id"] == pending), None),
        "items": merged,
        "limitations": [
            LIMIT,
            "The frozen tasks cover changed files and immediate graph neighbors, not exhaustive semantic impact. Notes are local, unsigned reviewer observations.",
        ],
    }


def status(worklist, **options):
    return _view(*_load(worklist, **options))


# [impl->req~ib-review-worklist~1]
def record(worklist, identifier, state, message, **options):
    if (
        state not in STATES
        or not isinstance(message, str)
        or (state != "pending" and not message.strip())
    ):
        raise CheckError("Use pending, reviewed or deferred; reviewed/deferred tasks need a note")
    lock = worklist.resolve() / ".writer.lock"
    try:
        stream = lock.open("x")
    except FileExistsError as exc:
        raise CheckError(
            "Another review writer is active; remove .writer.lock only after confirming that writer has stopped"
        ) from exc
    try:
        stream.close()
        plan, progress = _load(worklist, **options)
        item = next((item for item in progress["items"] if item["id"] == identifier), None)
        if item is None:
            raise CheckError(f"Unknown frozen review task: {identifier}")
        item.update(state=state, message=message)
        item["history"].append({"state": state, "message": message})
        _atomic(worklist.resolve() / "progress.json", progress)
        return _view(plan, progress)
    finally:
        lock.unlink(missing_ok=True)


def render(result, current_only=False):
    counts = result["counts"]
    lines = [
        f"Review progress: {result['status']} ({counts['reviewed']} reviewed, {counts['pending']} pending, {counts['deferred']} deferred)",
        f"Recorded check: {result['recorded_check_status']}; review gate: {result['recorded_review']['status']}",
        f"Source: {result['source']['sha256']}",
    ]
    selected = (
        [result["current"]]
        if current_only and result["current"]
        else []
        if current_only
        else result["items"]
    )
    for item in selected:
        lines.append(f"{item['id']}: {item['state']}")
        if item["kind"] == "artifact":
            artifact = item["artifact"]
            lines.extend(
                [
                    f"  {artifact['path']}:{artifact['line']} ({item['snapshot']}; {item['reason']})",
                    f"  {artifact['title']}",
                    artifact["description"],
                    f"  Covers: {', '.join(artifact['covers']) or '(none)'}",
                    f"  Covered by: {', '.join(artifact['covered_by']) or '(none)'}",
                ]
            )
            if "linked_test_execution" in artifact:
                lines.append(f"  Linked execution: {artifact['linked_test_execution']}")
        else:
            lines.append(
                f"  {item['change']}; {item['annotation_status']}; semantic review selection={item['semantic_review_selection']}"
            )
        if item["message"]:
            lines.append("  Note: " + item["message"])
    if current_only and result["current"] is None:
        lines.append(
            "No pending tasks. Deferred tasks still require attention."
            if counts["deferred"]
            else "All frozen tasks have review notes."
        )
    lines.extend(result["limitations"])
    return "\n".join(lines)
