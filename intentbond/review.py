import difflib
from fnmatch import fnmatchcase

from .common import canonical, digest, within
from .snapshot import read_entry


def matches_glob(path, pattern):
    """Match complete POSIX paths. Positions are reachable path-component offsets."""
    parts = path.split("/")
    positions = {0}
    for component in pattern.split("/"):
        if not positions:
            return False
        if component == "**":
            positions = range(min(positions), len(parts) + 1)
        else:
            positions = {
                i + 1 for i in positions if i < len(parts) and fnmatchcase(parts[i], component)
            }
    return len(parts) in positions


# [impl->req~ib-review-selection~1]
def review_selection(path, scope):
    for field, label in (("specification_paths", "specification"), ("test_paths", "test")):
        if within(path, scope[field]):
            return label
    if within(path, scope.get("review_paths", [])) or any(
        matches_glob(path, pattern) for pattern in scope.get("review_globs", [])
    ):
        return "review"
    return None


def review_diff(base, candidate, changed):
    chunks = []
    for change in changed:
        if change["kind"] != "file":
            continue
        path = change["path"]
        left = (
            read_entry(base.root, path)[1].decode(errors="replace").splitlines(keepends=True)
            if change["before"]
            else []
        )
        right = (
            read_entry(candidate.root, path)[1].decode(errors="replace").splitlines(keepends=True)
            if change["after"]
            else []
        )
        chunks.extend(
            difflib.unified_diff(left, right, fromfile=f"base/{path}", tofile=f"candidate/{path}")
        )
    return "".join(chunks)


def changes(base, candidate, before, after, scope):
    result = []
    old = {item["key"]: item for item in before}
    new = {item["key"]: item for item in after}
    for key in sorted(old.keys() | new.keys()):
        left, right = old.get(key), new.get(key)

        # Location-only moves remain visible through file changes below.
        def meaning(item):
            return {k: item[k] for k in ("id", "revision", "content")} if item else None

        if meaning(left) != meaning(right):
            result.append({"kind": "requirement", "key": key, "before": left, "after": right})
    left = {f["path"]: f for f in base.manifest}
    right = {f["path"]: f for f in candidate.manifest}
    # [impl->req~ib-change-review~1]
    # [impl->req~ib-review-selection~1]
    for path in sorted(left.keys() | right.keys()):
        if left.get(path) != right.get(path) and review_selection(path, scope):
            result.append(
                {"kind": "file", "path": path, "before": left.get(path), "after": right.get(path)}
            )
    return result


# [impl->req~ib-revision-policy~1]
def revision_diagnostics(changed, scope):
    if not scope.get("policy", {}).get("require_revision_increase", False):
        return []
    result = []
    for change in changed:
        if change["kind"] != "requirement":
            continue
        old, new = change["before"], change["after"]
        if old and new:
            if new["revision"] < old["revision"]:
                result.append(f"{change['key']}: requirement revision must not decrease")
            elif new["content"] != old["content"] and new["revision"] <= old["revision"]:
                result.append(
                    f"{change['key']}: changed requirement content needs a revision increase and reviewed references"
                )
    return result


def review_record(base, candidate, scope_sha256, changed):
    return {
        "schema_version": 1,
        "base_commit": base.commit,
        "base_sha256": base.sha256,
        "candidate_sha256": candidate.sha256,
        "scope_sha256": scope_sha256,
        "changes_sha256": digest(canonical(changed)),
        "changes": changed,
    }
