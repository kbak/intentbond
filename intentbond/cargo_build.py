"""Prepare one private nextest archive for a captured candidate's test command."""

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .common import CheckError, canonical, digest, parse_json, read_json, run, xml_tree
from .snapshot import Snapshot, changed_source

VERSION = "0.9.152"
BUILD_ENV = "INTENTBOND_CAPTURED_CARGO_BUILD"


def versions(root, env=None, deadline=None):
    result = {}
    for name, command in (
        ("nextest", ["cargo", "nextest", "--version"]),
        ("rustc", ["rustc", "--version"]),
        ("cargo", ["cargo", "--version"]),
    ):
        timeout = None if deadline is None else max(0, deadline - time.monotonic())
        line = subprocess.check_output(
            command, cwd=root, env=env, text=True, timeout=timeout
        ).partition("\n")[0]
        if not line:
            raise CheckError(f"Missing {name} version")
        result[name] = line
    if result["nextest"].split()[:2] != ["cargo-nextest", VERSION]:
        raise CheckError(f"Unsupported cargo-nextest version; expected {VERSION}")
    return result


def build_args(target, packages, features):
    args = ["--locked", "--target-dir", str(target)]
    for name in packages:
        args.extend(["--package", name])
    if not packages:
        args.append("--workspace")
    if features:
        args.extend(["--features", features])
    return args


def archive_digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def build_artifacts(build):
    return {"cargo-build.log"} | ({"cargo-doctests.log"} if build.get("doctests") else set())


def doctest_command(target, build):
    return [
        "cargo",
        "test",
        "--doc",
        *build_args(target, build.get("packages", []), build.get("features")),
    ]


def build_passed(preparation):
    return (
        preparation["status"] == "passed"
        and preparation.get("doctests", {}).get("status", "passed") == "passed"
    )


def cargo_environment(env):
    # Retain only a digest. Compilation sees the check environment, before fixture setup.
    settings = {
        k: v
        for k, v in env.items()
        if k.startswith(("CARGO_", "RUST"))
        or k
        in {
            "CC",
            "CXX",
            "AR",
            "CFLAGS",
            "CXXFLAGS",
            "LDFLAGS",
        }
    }
    executables = {
        name: shutil.which(name, path=env.get("PATH"))
        for name in ("cargo", "cargo-nextest", "rustc")
    }
    return digest(canonical([settings, executables]))


# [impl->req~ib-cargo-build-reuse~1]
# [impl->req~ib-cargo-doctests~1]
def run_with_build(snap, config, out, env):
    started = time.monotonic()
    deadline = started + config["timeout_seconds"]
    build = config["cargo_build"]
    with tempfile.TemporaryDirectory(prefix="cargo-", dir=snap.root.parent) as directory:
        private = Path(directory)
        archive = private / "tests.tar.zst"
        target = private / "target"
        profile = private / "nextest.toml"
        profile.write_text("[profile.ib]\n")
        command = [
            "cargo",
            "nextest",
            "archive",
            *build_args(target, build.get("packages", []), build.get("features")),
            "--config-file",
            str(profile),
            "--user-config-file",
            "none",
            "--profile",
            "ib",
            "--archive-file",
            str(archive),
            "--zstd-level",
            "1",
        ]
        try:
            tools = versions(snap.root, env, deadline)
        except (OSError, subprocess.SubprocessError) as exc:
            raise CheckError(f"Cannot identify Cargo toolchain: {exc}") from exc
        preparation = run(
            command,
            snap.root,
            out / "cargo-build.log",
            max(0, deadline - time.monotonic()),
            {**env, "CARGO_BUILD_BUILD_DIR": str(target)},
        )
        if preparation["status"] == "passed":
            if archive.is_symlink() or not archive.is_file() or changed_source(snap):
                raise CheckError(
                    "Cargo preparation requires a fresh archive and unchanged captured source"
                )
            if build.get("doctests"):
                preparation["doctests"] = run(
                    doctest_command(target, build),
                    snap.root,
                    out / "cargo-doctests.log",
                    max(0, deadline - time.monotonic()),
                    {**env, "CARGO_BUILD_BUILD_DIR": str(target)},
                )
        if not build_passed(preparation):
            failed = preparation.get("doctests", preparation)
            shutil.copyfile(out / failed["log"], out / "tests.log")
            return {
                "command": config["command"],
                "status": "error",
                "exit_code": None,
                "log": "tests.log",
                "duration_seconds": round(time.monotonic() - started, 3),
                "cargo_build": preparation,
                "error": f"Cargo preparation did not pass; see {failed['log']}",
            }
        if archive.is_symlink() or not archive.is_file() or changed_source(snap):
            raise CheckError(
                "Cargo preparation requires a fresh archive and unchanged captured source"
            )
        shutil.rmtree(target)
        (private / "manifest.json").write_bytes(canonical(snap.manifest))
        binding = {
            "directory": str(private),
            "root": str(snap.root),
            "candidate": snap.identity(),
            "archive_sha256": archive_digest(archive),
            "toolchain": tools,
            "cargo_env_sha256": cargo_environment(env),
            "build": build,
        }
        result = run(
            config["command"],
            snap.root,
            out / "tests.log",
            max(0, deadline - time.monotonic()),
            {**env, BUILD_ENV: json.dumps(binding)},
        )
        result["duration_seconds"] = round(time.monotonic() - started, 3)
        result["cargo_build"] = {
            **preparation,
            "archive_sha256": binding["archive_sha256"],
            "toolchain": tools,
            "candidate_sha256": snap.sha256,
            "configuration": build,
        }
        return result


def captured_archive(scratch, toolchain):
    if BUILD_ENV not in os.environ:
        raise CheckError("--use-captured-build requires tests.cargo_build in the current check")
    binding = parse_json(os.environ[BUILD_ENV])
    root = Path.cwd()
    if str(root) != binding["root"]:
        raise CheckError("Cargo build belongs to a different candidate directory")
    if (
        toolchain != binding["toolchain"]
        or cargo_environment(os.environ) != binding["cargo_env_sha256"]
    ):
        raise CheckError("Cargo build toolchain or build environment differs from preparation")
    private = Path(binding["directory"])
    identity = binding["candidate"]
    snap = Snapshot(
        root, identity["commit"], identity["kind"], read_json(private / "manifest.json")
    )
    if snap.identity() != identity or changed_source(snap):
        raise CheckError("Cargo build source differs from the captured candidate")
    # Both list and run consume this invocation's verified copy. Neither writes to the archive
    # used by sibling producers, and each receives a newly extracted target from nextest.
    archive = scratch / "tests.tar.zst"
    shutil.copyfile(private / "tests.tar.zst", archive)
    if archive_digest(archive) != binding["archive_sha256"]:
        raise CheckError("Captured Cargo build archive digest differs from preparation")
    return archive, binding


# [impl->req~ib-cargo-doctests~1]
def validate_build_evidence(preparation, build, candidate_sha256, report):
    if (
        not isinstance(preparation, dict)
        or preparation.get("status") != "passed"
        or preparation.get("exit_code") != 0
        or preparation.get("configuration") != build
        or preparation.get("candidate_sha256") != candidate_sha256
        or not re.fullmatch("[0-9a-f]{64}", str(preparation.get("archive_sha256")))
    ):
        raise CheckError("Cargo preparation differs from the captured source or configured build")
    if build.get("doctests"):
        try:
            command = preparation["command"]
            if not isinstance(command, list) or not isinstance(preparation["doctests"], dict):
                raise CheckError("Malformed Cargo doctest command or outcome")
            target = command[command.index("--target-dir") + 1]
            doctests = preparation["doctests"]
            if (
                doctests["status"] != "passed"
                or doctests["exit_code"] != 0
                or doctests["command"] != doctest_command(target, build)
                or doctests["log"] != "cargo-doctests.log"
            ):
                raise CheckError("Cargo doctest evidence does not match the configured build")
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise CheckError("Missing or malformed Cargo doctest evidence") from exc
    elif "doctests" in preparation:
        raise CheckError("Cargo doctest evidence was not requested by the scope")
    expected = {
        "build_archive_sha256": preparation["archive_sha256"],
        "build_candidate_sha256": candidate_sha256,
        "build_configuration": json.dumps(build, sort_keys=True),
    }
    for suite in xml_tree(report).iter("testsuite"):
        if suite.get("name") != "cargo-nextest":
            continue
        properties = suite.findall("./properties/property")
        recorded = [
            (p.get("name"), p.get("value")) for p in properties if p.get("name") in expected
        ]
        if recorded and (len(recorded) != len(expected) or dict(recorded) != expected):
            raise CheckError("Cargo report differs from the build prepared by this check")
