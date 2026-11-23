"""Run Cargo workspace libtest targets with nextest and emit linked JUnit."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from .cargo_build import build_args, captured_archive, versions
from .common import CheckError, parse_json, xml_tree
from .rust_junit import bindings, command_property, fresh_output, property_value, write_report
from .testing import junit_counts


def inventory(raw):
    data = parse_json(raw)
    cases = {}
    if not isinstance(data["rust-suites"], dict) or type(data["test-count"]) is not int:
        raise CheckError("Invalid nextest inventory")
    for binary, suite in data["rust-suites"].items():
        if binary != suite["binary-id"] or suite["status"] != "listed":
            raise CheckError(f"Incomplete nextest inventory for {binary}")
        if not isinstance(suite["testcases"], dict) or not all(
            isinstance(suite[field], str) and suite[field]
            for field in ("package-name", "binary-name", "kind")
        ):
            raise CheckError(f"Invalid nextest target: {binary}")
        for name, case in suite["testcases"].items():
            if case["kind"] != "test" or type(case["ignored"]) is not bool:
                raise CheckError(f"Unsupported nextest test kind or ignore status: {binary} {name}")
            cases[binary, name] = (case["ignored"], suite)
    if len(cases) != data["test-count"]:
        raise CheckError("Incomplete nextest test inventory")
    return cases


def selection(cases, ignored, excluded):
    named = [tuple(identity) for identity in (ignored or excluded)]
    if len(named) != len(set(named)) or set(named) - cases.keys():
        raise CheckError("Duplicate or unmatched exact nextest binary/test selection")
    if ignored and any(not cases[identity][0] for identity in named):
        raise CheckError("Explicit ignored selection matched a non-ignored test")
    selected = set(named) if ignored else cases.keys() - set(named)
    skipped = {key for key in selected if cases[key][0] and not ignored}
    return selected, skipped


def exact_filter(identities):
    # Escape arbitrary matcher input using nextest's documented Unicode escape.
    def literal(value):
        return "".join(c if c.isalnum() or c in "_:-." else f"\\u{{{ord(c):x}}}" for c in value)

    return " | ".join(
        f"(binary_id(={literal(binary)}) & test(={literal(name)}))" for binary, name in identities
    )


# [impl->req~ib-cargo-evidence~1]
def reconcile(suite, native, cases, selected, skipped, links):
    counts = junit_counts(native)
    root = xml_tree(native)
    if root.tag != "testsuites":
        raise CheckError("Invalid nextest report root")
    expected = selected - skipped
    seen = set()
    for group in root.findall("testsuite"):
        for case in group.findall("testcase"):
            key = group.get("name"), case.get("name")
            if key not in expected or key in seen or case.get("classname") != key[0]:
                raise CheckError(f"Unexpected or duplicate nextest case {key!r}")
            if (
                any(
                    child.tag not in {"failure", "error", "system-out", "system-err"}
                    for child in case
                )
                or case.get("status") is not None
                or len(case.findall("failure")) + len(case.findall("error")) > 1
            ):
                raise CheckError(f"Ambiguous nextest outcome for {key!r}")
            seen.add(key)
            suite.append(case)
    if len(seen) != counts["total"]:
        raise CheckError("Unrecognized nextest report structure")
    for binary, name in sorted(skipped):
        case = ET.SubElement(suite, "testcase", classname=binary, name=name)
        ET.SubElement(case, "skipped", message="Discovered as ignored by nextest")
    for case in suite.findall("testcase"):
        key = case.get("classname"), case.get("name")
        info = cases[key][1]
        for field in ("package-name", "binary-name", "kind"):
            property_value(case, field, info[field])
        if key in links:
            property_value(case, "oft_id", links[key])
    if seen != expected:
        raise CheckError(f"Incomplete nextest run: missing {sorted(expected - seen)!r}")
    if not seen or counts["failed"] or counts["errors"] or counts.get("suite_failed"):
        raise CheckError("Nextest report does not record a passing run")


def run_nextest(args, suite, scratch):
    links = bindings(args.bindings, "cargo")
    target = scratch / "target"
    config = scratch / "nextest.toml"
    native = scratch / "results.xml"
    config.write_text(
        f"[store]\ndir = {json.dumps(str(scratch / 'store'))}\n"
        f"[profile.ib.junit]\npath = {json.dumps(str(native))}\n"
        'report-skipped = "none"\nstore-failure-output = true\n'
    )
    prefix = ["cargo", "nextest"]
    tools = versions(Path.cwd())
    for key, value in tools.items():
        property_value(suite, key, value)
    if args.use_captured_build:
        if args.package or args.features is not None:
            raise CheckError(
                "Select packages and features in tests.cargo_build when using its archive"
            )
        archive, binding = captured_archive(scratch, tools)
        common = ["--archive-file", str(archive)]
        property_value(suite, "build_archive_sha256", binding["archive_sha256"])
        property_value(suite, "build_candidate_sha256", binding["candidate"]["sha256"])
        property_value(suite, "build_configuration", json.dumps(binding["build"], sort_keys=True))
    else:
        common = build_args(target, args.package, args.features)
    common.extend(["--config-file", str(config), "--user-config-file", "none", "--profile", "ib"])
    env = {**os.environ, "CARGO_BUILD_BUILD_DIR": str(target)}
    discover = prefix + ["list", *common, "--run-ignored", "all", "--message-format", "json"]
    property_value(suite, "discovery_command", json.dumps(discover))
    cases = inventory(subprocess.check_output(discover, env=env))
    selected, skipped = selection(cases, args.ignored, args.exclude)
    command = prefix + ["run", *common, "--no-fail-fast", "--retries", "0", "--no-tests", "fail"]
    command.extend(["--failure-output", "final", "--success-output", "never"])
    if args.ignored:
        command.extend(["--run-ignored", "only", "-E", exact_filter(args.ignored)])
    elif args.exclude:
        command.extend(["-E", f"!({exact_filter(args.exclude)})"])
    command_property(suite, command)
    proc = subprocess.run(command, env=env)
    property_value(suite, "exit_code", str(proc.returncode))
    reconcile(suite, native, cases, selected, skipped, links)
    if proc.returncode:
        raise CheckError(f"cargo nextest failed (exit {proc.returncode})")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--bindings", action="append", default=[], metavar="RS_FILE")
    parser.add_argument("--package", action="append", default=[])
    parser.add_argument("--features")
    parser.add_argument(
        "--use-captured-build",
        action="store_true",
        help="Run the build prepared by this check's tests.cargo_build configuration",
    )
    group = parser.add_mutually_exclusive_group()
    for option in ("--ignored", "--exclude"):
        group.add_argument(
            option, nargs=2, action="append", default=[], metavar=("BINARY_ID", "TEST")
        )
    args = parser.parse_args(argv)
    try:
        report = fresh_output(args.report)
        suite = ET.Element("testsuite", name="cargo-nextest")
        try:
            with tempfile.TemporaryDirectory(prefix="ib-nextest-") as scratch:
                run_nextest(args, suite, Path(scratch))
        except (
            CheckError,
            OSError,
            ValueError,
            KeyError,
            TypeError,
            subprocess.SubprocessError,
        ) as exc:
            ET.SubElement(suite, "error", message=str(exc))
            print(str(exc), file=sys.stderr)
        write_report(report, suite)
        return int(suite.find("error") is not None)
    except (CheckError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
