"""Assess existing evidence without running tests, agents, or granting approval.

The evaluator is a library boundary for trusted callers. CLI callers use
assess_files, which validates captured source and the selected check bundle.
Producer identity and authorization are supplied by the caller's trusted process;
digests do not authenticate the producer of an unsigned record.
"""

import tempfile
from pathlib import Path

from .assurance_contract import (
    STATES,
    bound_record,
    object_fields,
    strings,
    text,
    validate_context,
    validate_policy,
)
from .assurance_review import review_outcome, validate_assessments
from .common import CheckError, canonical, digest, read_json, within, write_json

EXIT_CODES = {"satisfied": 0, "failed": 1, "incomplete": 5, "decision_pending": 4}
LIMITS = [
    "Assessment satisfies only its selected obligations; it does not authorize merge or deployment.",
    "Evidence and review records are unsigned; producer identity and authority depend on the caller's trusted process.",
    "Source identity excludes external dependencies and environment inputs. Structural links and passing tests do not prove requirement satisfaction.",
]


def aggregate(states):
    return next(
        (state for state in ("incomplete", "failed", "decision_pending") if state in states),
        "satisfied",
    )


def validate_review(record, change):
    bound_record(record, change, {"verdict", "traceability_assessment", "intent_alignment"})
    if record["verdict"] not in {"satisfied", "failed", "incomplete"}:
        raise ValueError("Unsupported review verdict")
    if not isinstance(record["traceability_assessment"], list) or not isinstance(
        record["intent_alignment"], list
    ):
        raise ValueError("Review assessments must be lists")
    for item in record["traceability_assessment"]:
        object_fields(item, {"project", "summary", "changes"})
        text(item["project"])
        text(item["summary"])
        if not isinstance(item["changes"], list):
            raise ValueError("Review changes must be a list")
        for entry in item["changes"]:
            object_fields(
                entry,
                {"changed_paths", "behavior", "status", "rationale"},
                {
                    "requirement_ids",
                    "documentation",
                    "implementation",
                    "verification",
                    "remediation",
                },
            )
            if not strings(entry["changed_paths"], unique=False):
                raise ValueError("Review change needs changed paths")
            for key in ("behavior", "rationale"):
                text(entry[key])
            if entry["status"] not in {"covered", "not_needed", "missing", "uncertain"}:
                raise ValueError("Unsupported traceability judgment")
            for key in ("requirement_ids", "documentation", "implementation", "verification"):
                strings(entry.get(key, []), unique=False)
            if entry.get("remediation") is not None:
                text(entry["remediation"])
    for item in record["intent_alignment"]:
        object_fields(item, {"project", "status", "references", "summary"})
        text(item["project"])
        text(item["summary"])
        if item["status"] not in {"aligned", "conflict", "uncertain"} or not strings(
            item["references"], unique=False
        ):
            raise ValueError("Intent judgment needs a known status and references")


# [impl->req~ib-assurance-context~1]
# [impl->req~ib-assurance-review~1]
# [impl->req~ib-assurance-profile~1]
def assess(change, checking_policy, *, observations=None, review=None, decisions=()):
    """Evaluate caller-validated observations; never treat candidate records as authority.

    Each observation is a receipt from a trusted verifier, bound to this exact
    context. Callers must validate its evidence before supplying satisfied states.
    Use assess_files at a filesystem boundary instead of accepting receipt JSON
    from an untrusted implementation process.
    """
    validate_context(change, checking_policy)
    if observations is not None:
        object_fields(observations, set(), change["repositories"])
    rows = []
    context_sha256 = digest(canonical(change))

    def add(repository, obligation, status, reason, required=True, references=()):
        rows.append(
            {
                "repository": repository,
                "obligation": obligation,
                "status": status,
                "required": required,
                "reason": reason,
                "references": list(references),
            }
        )

    profile = checking_policy["profile"]
    for name in change["repositories"]:
        artifacts = [item for item in change["artifacts"] if item["repository"] == name]
        for role in profile["required_roles"]:
            present = any(item["role"] == role and item["sha256"] is not None for item in artifacts)
            add(
                name,
                f"role:{role}",
                "satisfied" if present else "incomplete",
                f"Required artifact role: {role}",
            )
        for item in artifacts:
            state = "satisfied"
            if item["sha256"] is None:
                state = "incomplete"
            elif item["role"] in profile["immutable_roles"]:
                state = (
                    "incomplete"
                    if "accepted_sha256" not in item
                    else "satisfied"
                    if item["sha256"] == item["accepted_sha256"]
                    else "failed"
                )
            add(
                name,
                f"artifact:{item['id']}",
                state,
                "Recorded current/accepted artifact identity",
                references=[item["path"]],
            )

        observed = (observations or {}).get(name)
        if observed is not None:
            bound_record(observed, change, {"repository", "outcomes", "references"})
            if observed["repository"] != name:
                raise ValueError("Observation names another repository")
            object_fields(
                observed["outcomes"],
                set(),
                {"execution", "traceability", "source", "change_review"},
            )
            if any(state not in STATES for state in observed["outcomes"].values()):
                raise ValueError("Unsupported observation outcome")
            strings(observed["references"])
        for key in ("source", "execution", "traceability"):
            state = observed["outcomes"].get(key, "incomplete") if observed else "incomplete"
            required = key in checking_policy["required"] or key == "source"
            add(
                name,
                key,
                state,
                "Validated observation" if observed else "No validated observation supplied",
                required,
                observed["references"] if observed else [],
            )

    review_state = intent_state = "incomplete"
    review_reason = "No review record supplied"
    if review is not None:
        validate_review(review, change)
        producer = review["producer"]
        permitted = not checking_policy["reviewers"] or producer in checking_policy["reviewers"]
        independent = not checking_policy["independent_review"] or (
            change.get("implementer") is not None and producer != change["implementer"]
        )
        if not permitted or not independent:
            review_reason = "Review producer does not satisfy the caller's trusted reviewer policy"
        else:
            expected = {
                name: repo
                for name, repo in change["repositories"].items()
                if "scope_sha256" in repo
            }
            validate_assessments(review["traceability_assessment"], expected)
            review_state = aggregate(
                [review["verdict"], review_outcome(review["traceability_assessment"])]
            )
            projects = [item["project"] for item in review["intent_alignment"]]
            if (
                len(set(projects)) != len(projects)
                or not set(projects) <= change["repositories"].keys()
            ):
                raise ValueError("Intent alignment has duplicate or unknown repositories")
            if set(projects) == change["repositories"].keys():
                intent_state = review_outcome(alignment=review["intent_alignment"])
            review_reason = (
                f"Caller-supplied review from {producer}; reference relevance remains a judgment"
            )
    change_review = any(
        item.get("outcomes", {}).get("change_review") == "decision_pending"
        for item in (observations or {}).values()
    )
    for key, state in (("review", review_state), ("intent", intent_state)):
        if key == "review" and change_review and review is None:
            state = "decision_pending"
        add(
            None,
            key,
            state,
            review_reason,
            key in checking_policy["required"] or (key == "review" and change_review),
        )

    if not isinstance(decisions, (list, tuple)):
        raise ValueError("Decisions must be a list")
    indexed = {}
    for record in decisions:
        bound_record(record, change, {"id", "actor", "outcome"})
        for key in ("id", "actor"):
            text(record[key])
        if record["outcome"] not in {"accepted", "rejected"} or record["id"] in indexed:
            raise ValueError("Unknown or duplicate decision outcome")
        indexed[record["id"]] = record
    for decision in checking_policy["decisions"]:
        record = indexed.get(decision)
        state = (
            "decision_pending"
            if record is None
            else "satisfied"
            if record["outcome"] == "accepted"
            else "failed"
        )
        add(
            None,
            f"decision:{decision}",
            state,
            "Decision required by trusted policy"
            if record is None
            else f"Recorded {record['outcome']} by {record['actor']}",
        )
    return {
        "schema_version": 1,
        "context_sha256": context_sha256,
        "policy_sha256": change["policy_sha256"],
        "invocation": change["invocation"],
        "status": aggregate([item["status"] for item in rows if item["required"]]),
        "context": change,
        "policy": checking_policy,
        "obligations": rows,
        "observations": observations or {},
        "review": review,
        "decisions": list(decisions),
        "limitations": list(LIMITS),
    }


def observation(change, repository, outcomes, references=(), *, producer="caller"):
    return {
        "schema_version": 1,
        "context_sha256": digest(canonical(change)),
        "producer": producer,
        "repository": repository,
        "outcomes": outcomes,
        "references": list(references),
    }


def render(report):
    from .summary import code

    lines = [
        "# Assurance assessment",
        "",
        f"Status: {report['status']}",
        f"Invocation: {code(report['invocation'])}",
        "",
    ]
    for item in report["obligations"]:
        label = code((item["repository"] + ": " if item["repository"] else "") + item["obligation"])
        lines.append(
            f"- {label}: **{item['status']}** ({'required' if item['required'] else 'observed'}) — {code(item['reason'])}"
        )
    lines.extend(["", *["- " + item for item in report["limitations"]], ""])
    return "\n".join(lines)


def write_report(out, report):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "assessment.json", report)
    (out / "summary.md").write_text(render(report), encoding="utf-8")


def capture_context(
    repo_path,
    base,
    candidate,
    checking_policy,
    invocation,
    *,
    evidence_path=None,
    artifact_roles=None,
    accepted_artifacts=None,
    accepted_request=None,
    implementer=None,
    name="project",
):
    """Build context from Git and optional existing check output, without executing checks.

    The resulting context still needs assess_files validation at a later boundary.
    Accepted artifact digests and request references come from the caller's retained
    acceptance record, never from candidate-generated approval metadata.
    """
    from .assurance_contract import context
    from .evidence import read_statement
    from .oft import import_items
    from .snapshot import repository, snapshot

    validate_policy(checking_policy)
    repo = repository(Path(repo_path))
    evidence_path = Path(evidence_path).resolve() if evidence_path else None
    evidence = read_statement(read_json(evidence_path)) if evidence_path else None
    with tempfile.TemporaryDirectory(prefix="ib-context-") as directory:
        root = Path(directory)
        before = snapshot(repo, base, root / "base")
        after = snapshot(repo, candidate, root / "candidate")
        left, right = ({item["path"]: item for item in snap.manifest} for snap in (before, after))
        paths = sorted(
            path for path in left.keys() | right.keys() if left.get(path) != right.get(path)
        )
        spec = {"base": before.identity(), "candidate": after.identity(), "changed_paths": paths}
        if evidence:
            scope = evidence["scope"]["configuration"]
            spec.update(
                scope_sha256=evidence["scope"]["sha256"],
                evidence_sha256=digest(evidence_path.read_bytes()),
            )
            spec["changed_paths"] = [path for path in paths if within(path, scope["inputs"])]
            spec["requirement_index"] = {
                label: {
                    "ids": sorted(
                        item["id"]
                        for item in import_items(
                            evidence_path.parent / f"{label}-items.xml", Path(".")
                        )
                        if within(item["path"], scope["specification_paths"])
                    )
                }
                for label in ("base", "candidate")
            }
        artifacts = []
        for path, role in (artifact_roles or {}).items():
            entry = right.get(path)
            item = {
                "id": path,
                "repository": name,
                "role": role,
                "path": path,
                "sha256": entry["sha256"]
                if entry and entry["mode"] in {"100644", "100755"}
                else None,
            }
            if path in (accepted_artifacts or {}):
                item["accepted_sha256"] = accepted_artifacts[path]
            artifacts.append(item)
    return context(
        invocation,
        {name: spec},
        checking_policy,
        artifacts=artifacts,
        accepted_request=accepted_request,
        implementer=implementer,
    )


# [impl->req~ib-assurance-source~1]
def assess_files(
    repo_path,
    change_path,
    policy_path,
    out,
    *,
    evidence_path=None,
    review_path=None,
    decisions_path=None,
    scope_path=None,
):
    """Validate source and designated evidence at a standalone filesystem boundary."""
    from .oft import import_items
    from .runner import verify
    from .snapshot import repository, snapshot

    change, checking_policy = read_json(change_path), validate_policy(read_json(policy_path))
    validate_context(change, checking_policy)
    if len(change["repositories"]) != 1:
        raise ValueError(
            "Standalone assessment takes one repository; use the library adapter for groups"
        )
    name, spec = next(iter(change["repositories"].items()))
    repo = repository(Path(repo_path))
    out = Path(out).resolve()
    if out.is_relative_to(repo):
        raise CheckError("Assessment output must be outside the checked repository")
    outcomes = {"source": "satisfied"}
    with tempfile.TemporaryDirectory(prefix="ib-assess-") as directory:
        scratch = Path(directory)
        captures = {}
        for label in ("base", "candidate"):
            identity = spec[label]
            ref = "worktree" if identity.get("kind") == "worktree" else identity["commit"]
            capture = snapshot(repo, ref, scratch / label)
            captures[label] = capture
            if (
                capture.sha256 != identity["sha256"]
                or capture.commit != identity["commit"]
                or ("file_count" in identity and len(capture.manifest) != identity["file_count"])
            ):
                raise CheckError(f"{label} source differs from the change context")
        before = {item["path"]: item for item in captures["base"].manifest}
        after = {item["path"]: item for item in captures["candidate"].manifest}
        changed = {
            path for path in before.keys() | after.keys() if before.get(path) != after.get(path)
        }
        # A context may scope review to selected paths, but cannot invent paths.
        if not set(spec["changed_paths"]) <= changed:
            raise CheckError("Context includes paths outside the actual source change")
        for item in change["artifacts"]:
            entry = after.get(item["path"])
            actual = entry["sha256"] if entry and entry["mode"] in {"100644", "100755"} else None
            if actual != item["sha256"]:
                raise CheckError("Artifact differs from captured regular source: " + item["path"])
    references = []
    if evidence_path is not None:
        evidence_path = Path(evidence_path).resolve()
        if spec.get("evidence_sha256") != digest(evidence_path.read_bytes()):
            raise CheckError("Evidence differs from this invocation's designated bundle")
        matched = verify(
            repo,
            scope_path,
            spec["base"]["commit"],
            "worktree"
            if spec["candidate"].get("kind") == "worktree"
            else spec["candidate"]["commit"],
            evidence_path,
            allow_pending_review=True,
        )
        from .evidence import read_statement

        evidence = read_statement(read_json(evidence_path))
        if (
            spec.get("scope_sha256") != evidence["scope"]["sha256"]
            or spec["base"]["sha256"] != evidence["base"]["sha256"]
        ):
            raise CheckError("Check baseline or scope differs from the context")
        selected = sorted(
            path for path in changed if within(path, evidence["scope"]["configuration"]["inputs"])
        )
        if spec["changed_paths"] != selected:
            raise CheckError("Context omits or misorders scoped source changes")
        for label in ("base", "candidate"):
            expected = spec.get("requirement_index", {}).get(label)
            if expected is not None:
                # The retained OFT export uses relative source paths; no Java run is needed.
                items = import_items(evidence_path.parent / f"{label}-items.xml", Path("."))
                ids = sorted(
                    item["id"]
                    for item in items
                    if within(
                        item["path"], evidence["scope"]["configuration"]["specification_paths"]
                    )
                )
                if expected.get("ids") != ids:
                    raise CheckError("Requirement index differs from retained check evidence")
        if matched["status"] == "matched":
            outcomes.update(execution="satisfied", traceability="satisfied")
        if evidence["review"]["status"] == "required":
            outcomes["change_review"] = "decision_pending"
        references.append(str(evidence_path))
    elif (
        "traceability" in checking_policy["required"] or "execution" in checking_policy["required"]
    ):
        outcomes.update(execution="incomplete", traceability="incomplete")
    if "scope_sha256" in spec and evidence_path is None:
        raise CheckError("A traceability context requires its designated check evidence")
    if evidence_path is None and spec["changed_paths"] != sorted(changed):
        raise CheckError("Context omits or misorders source changes")
    report = assess(
        change,
        checking_policy,
        observations={name: observation(change, name, outcomes, references)},
        review=read_json(review_path) if review_path else None,
        decisions=read_json(decisions_path) if decisions_path else [],
    )
    write_report(out, report)
    return report
