"""Version one assurance contracts; standard library only, no factory runtime."""

import copy
import re

from .common import canonical, digest, relative_path

STATES = {"satisfied", "failed", "incomplete", "decision_pending"}
CHECKS = {"execution", "traceability", "review", "intent"}
PROFILES = {
    "lightweight": {
        "name": "lightweight",
        "version": 1,
        "required_roles": [],
        "immutable_roles": [],
    },
    "ai-native-sdlc": {
        "name": "ai-native-sdlc",
        "version": 1,
        "required_roles": [],
        "immutable_roles": ["intent", "specification", "acceptance"],
    },
}


def object_fields(value, required, optional=()):
    if (
        not isinstance(value, dict)
        or not set(required) <= value.keys()
        or value.keys() - set(required) - set(optional)
    ):
        raise ValueError(f"Expected fields {sorted(required)}; optional {sorted(optional)}")


def text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Expected nonempty text")
    return value


def strings(value, *, unique=True):
    if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
        raise ValueError("Expected a list of nonempty strings")
    if unique and len(value) != len(set(value)):
        raise ValueError("Duplicate entries are unsupported")
    return value


def sha256(value):
    if not isinstance(value, str) or not re.fullmatch("[0-9a-f]{64}", value):
        raise ValueError("Expected a SHA-256 digest")
    return value


def version(value):
    if type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise ValueError("Unsupported assurance schema version")


def identity(value):
    object_fields(value, {"commit", "sha256"}, {"kind", "file_count"})
    if not isinstance(value["commit"], str) or not re.fullmatch(
        "(?:[0-9a-f]{40}|[0-9a-f]{64})", value["commit"]
    ):
        raise ValueError("Source commit must be a full Git object ID")
    sha256(value["sha256"])
    if value.get("kind", "commit") not in {"commit", "worktree", "archive"}:
        raise ValueError("Unsupported source kind")
    if "file_count" in value and (type(value["file_count"]) is not int or value["file_count"] < 0):
        raise ValueError("Source file_count must be a nonnegative integer")


# [impl->req~ib-assurance-context~1]
def policy(
    *, profile="lightweight", required=(), decisions=(), reviewers=(), independent_review=False
):
    value = {
        "schema_version": 1,
        "profile": copy.deepcopy(PROFILES[profile]) if isinstance(profile, str) else profile,
        "required": list(required),
        "decisions": list(decisions),
        "reviewers": list(reviewers),
        "independent_review": independent_review,
    }
    validate_policy(value)
    return value


def validate_policy(value):
    object_fields(
        value,
        {"schema_version", "profile", "required", "decisions", "reviewers", "independent_review"},
    )
    version(value)
    profile = value["profile"]
    object_fields(profile, {"name", "version", "required_roles", "immutable_roles"})
    text(profile["name"])
    if type(profile["version"]) is not int or profile["version"] != 1:
        raise ValueError("Unsupported assurance profile version")
    for key in ("required_roles", "immutable_roles"):
        strings(profile[key])
    if profile["name"] in PROFILES and profile != PROFILES[profile["name"]]:
        raise ValueError("Built-in profile contents cannot be replaced; use a custom name")
    if not set(strings(value["required"])) <= CHECKS:
        raise ValueError("Unsupported assurance obligation")
    strings(value["decisions"])
    strings(value["reviewers"])
    if type(value["independent_review"]) is not bool:
        raise ValueError("independent_review must be boolean")
    if value["independent_review"] and (
        not value["reviewers"] or not set(value["required"]) & {"review", "intent"}
    ):
        raise ValueError(
            "Independent review needs trusted reviewers and a required review obligation"
        )
    return value


def context(
    invocation,
    repositories,
    checking_policy,
    *,
    artifacts=(),
    accepted_request=None,
    implementer=None,
):
    value = {
        "schema_version": 1,
        "invocation": invocation,
        "policy_sha256": digest(canonical(validate_policy(checking_policy))),
        "repositories": repositories,
        "artifacts": list(artifacts),
    }
    if accepted_request is not None:
        value["accepted_request"] = accepted_request
    if implementer is not None:
        value["implementer"] = implementer
    validate_context(value, checking_policy)
    return value


def validate_context(value, checking_policy):
    object_fields(
        value,
        {"schema_version", "invocation", "policy_sha256", "repositories", "artifacts"},
        {"accepted_request", "implementer"},
    )
    version(value)
    text(value["invocation"])
    if value["policy_sha256"] != digest(canonical(validate_policy(checking_policy))):
        raise ValueError("Assurance policy differs from the context's trusted policy")
    if not isinstance(value["repositories"], dict) or not value["repositories"]:
        raise ValueError("Assurance needs at least one repository")
    for name, repo in value["repositories"].items():
        text(name)
        object_fields(
            repo,
            {"base", "candidate", "changed_paths"},
            {"requirement_index", "scope_sha256", "evidence_sha256"},
        )
        identity(repo["base"])
        identity(repo["candidate"])
        if repo["base"].get("kind") == "worktree":
            raise ValueError("Baseline must identify an immutable Git version")
        for path in strings(repo["changed_paths"]):
            relative_path(path)
        if repo["changed_paths"] != sorted(repo["changed_paths"]):
            raise ValueError("Changed paths must be sorted")
        if "scope_sha256" in repo:
            sha256(repo["scope_sha256"])
        if "evidence_sha256" in repo:
            sha256(repo["evidence_sha256"])
        indexes = repo.get("requirement_index", {})
        object_fields(indexes, set(), {"base", "candidate"})
        for label, indexed in indexes.items():
            object_fields(indexed, set(), {"source", "ids", "error"})
            if "error" in indexed:
                text(indexed["error"])
                if "ids" in indexed:
                    raise ValueError("A failed source index cannot supply requirement IDs")
            else:
                strings(indexed.get("ids"))
            if "source" in indexed:
                identity(indexed["source"])
                if any(indexed["source"][key] != repo[label][key] for key in ("commit", "sha256")):
                    raise ValueError("Requirement index describes another source version")
    if not isinstance(value["artifacts"], list):
        raise ValueError("artifacts must be a list")
    ids = set()
    for artifact in value["artifacts"]:
        object_fields(artifact, {"id", "repository", "role", "path", "sha256"}, {"accepted_sha256"})
        for key in ("id", "role"):
            text(artifact[key])
        if artifact["id"] in ids or artifact["repository"] not in value["repositories"]:
            raise ValueError("Duplicate artifact identity or unknown repository")
        ids.add(artifact["id"])
        relative_path(artifact["path"])
        if artifact["sha256"] is not None:
            sha256(artifact["sha256"])
        if "accepted_sha256" in artifact:
            sha256(artifact["accepted_sha256"])
    if "accepted_request" in value:
        object_fields(value["accepted_request"], {"reference", "sha256"})
        text(value["accepted_request"]["reference"])
        sha256(value["accepted_request"]["sha256"])
    if "implementer" in value:
        text(value["implementer"])
    return value


def bound_record(value, change, required, optional=()):
    object_fields(value, {"schema_version", "context_sha256", "producer", *required}, optional)
    version(value)
    text(value["producer"])
    if value["context_sha256"] != digest(canonical(change)):
        raise ValueError("Record describes another change context or invocation")
