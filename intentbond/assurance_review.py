"""Portable review records. Validation establishes accounting, not relevance."""


# [impl->req~ib-assurance-review~1]
def validate_assessments(assessments, expected):
    projects = [item["project"] for item in assessments]
    if len(set(projects)) != len(projects) or set(projects) != set(expected):
        raise ValueError("Traceability assessment must cover exactly the opted-in repositories")
    for assessment in assessments:
        project = assessment["project"]
        paths = set(expected[project]["changed_paths"])
        accounted = set()
        for change in assessment["changes"]:
            if not set(change["changed_paths"]) <= paths:
                raise ValueError(f"{project}: assessment includes paths outside the scoped change")
            accounted.update(change["changed_paths"])
            for reference in change.get("requirement_ids", []):
                label, identifier = (
                    reference.split(":", 1) if ":" in reference else ("candidate", reference)
                )
                indexed = expected[project].get("requirement_index", {}).get(label)
                if not isinstance(indexed, dict) or not indexed or "error" in indexed:
                    detail = (
                        indexed.get("error", "snapshot not available")
                        if isinstance(indexed, dict)
                        else "snapshot not available"
                    )
                    raise ValueError(
                        f"{project}: cannot resolve {reference}: {detail}; a source index is required"
                    )
                if not isinstance(indexed.get("ids"), list) or any(
                    not isinstance(item, str) for item in indexed["ids"]
                ):
                    raise ValueError(
                        f"{project}: malformed requirement ID index; a fresh review is required"
                    )
                if identifier not in indexed["ids"]:
                    raise ValueError(
                        f"{project}: unknown requirement ID or revision in {label}: {identifier}"
                    )
            if change["status"] == "covered" and not all(
                change.get(key)
                for key in ("requirement_ids", "documentation", "implementation", "verification")
            ):
                raise ValueError(
                    f"{project}: covered behavior needs requirement, documentation, implementation and verification references"
                )
            if change["status"] == "missing" and not change.get("remediation"):
                raise ValueError(f"{project}: missing traceability needs a concrete repair")
        if accounted != paths:
            raise ValueError(f"{project}: traceability assessment omits changed paths")


# [impl->req~ib-assurance-review~1]
def review_outcome(assessments=(), alignment=()):
    """Preserve uncertainty ahead of failures, matching the factory's review gate."""
    statuses = [change["status"] for item in assessments for change in item["changes"]]
    intents = [item["status"] for item in alignment]
    if "uncertain" in statuses or "uncertain" in intents:
        return "incomplete"
    if "missing" in statuses or "conflict" in intents:
        return "failed"
    return "satisfied"
