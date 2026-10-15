"""Unsigned in-toto statements; no signing, transport, or approval framework."""

from .common import CheckError, canonical, digest, read_json, relative_path
from .config import load_scope

EXIT_CODES = {
    "passed": 0,
    "rejected": 1,
    "error": 2,
    "empty": 3,
    "review_required": 4,
    "incomplete": 5,
}

STATEMENT = "https://in-toto.io/Statement/v1"
CHECK_TYPE = "https://github.com/kbak/intentbond/check/v0.2"
TEST_TYPE = "https://in-toto.io/attestation/test-result/v0.1"


def check_artifacts(evidence, directory, required):
    """Match bundle files to recorded hashes; producer trust remains external."""
    artifacts = evidence.get("artifacts")
    if not isinstance(artifacts, dict) or not set(required).issubset(artifacts):
        raise CheckError("Evidence artifact inventory is incomplete")
    for name, expected in artifacts.items():
        relative_path(name)
        path = directory / name
        if (
            path.is_symlink()
            or not path.resolve().is_relative_to(directory)
            or digest(path.read_bytes()) != expected
        ):
            raise CheckError(f"Evidence artifact missing or changed: {name}")
    return artifacts


def load_bundle(evidence_path, required=()):
    """Validate saved check inputs without requiring a passing check or live source."""
    from .oft import OFT_SHA256, OFT_VERSION

    evidence_path = evidence_path.resolve()
    directory = evidence_path.parent
    evidence = read_statement(read_json(evidence_path))
    if evidence.get("schema_version") != 2 or evidence.get("oft") != {
        "version": OFT_VERSION,
        "sha256": OFT_SHA256,
    }:
        raise CheckError("Unsupported check evidence or OFT version")
    check_artifacts(
        evidence,
        directory,
        {"scope.json", "base-manifest.json", "candidate-manifest.json", *required},
    )
    scope = load_scope(directory / "scope.json")
    if (
        scope != evidence["scope"]["configuration"]
        or digest(canonical(scope)) != evidence["scope"]["sha256"]
    ):
        raise CheckError("Scope differs from recorded policy")
    for label in ("base", "candidate"):
        if (
            digest(canonical(read_json(directory / f"{label}-manifest.json")))
            != evidence[label]["sha256"]
        ):
            raise CheckError(f"{label} manifest does not match evidence identity")
    return evidence, scope


def statement(predicate, predicate_type=CHECK_TYPE):
    candidate = predicate.get("candidate")
    return {
        "_type": STATEMENT,
        "subject": (
            [{"name": "candidate-manifest.json", "digest": {"sha256": candidate["sha256"]}}]
            if candidate
            else []
        ),
        "predicateType": predicate_type,
        "predicate": predicate,
    }


def read_statement(value):
    if (
        not isinstance(value, dict)
        or value.get("_type") != STATEMENT
        or value.get("predicateType") != CHECK_TYPE
        or not isinstance(value.get("predicate"), dict)
    ):
        raise CheckError("Unsupported traceability statement")
    evidence = value["predicate"]
    if value.get("subject") != statement(evidence)["subject"]:
        raise CheckError("Statement subject differs from checked candidate")
    return evidence


def test_statement(evidence, scope_digest):
    if evidence["tests"].get("source_status") != "matched":
        raise CheckError("Cannot attest a test result without matching stable source")
    value = statement(evidence, TEST_TYPE)
    value["predicate"] = {
        "result": "PASSED" if evidence["tests"]["status"] == "passed" else "FAILED",
        "configuration": [{"name": "scope.json", "digest": {"sha256": scope_digest}}],
    }
    return value
