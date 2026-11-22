"""Run a pinned Verus whole-crate check and link native function observations."""

import argparse
import subprocess
import sys
import xml.etree.ElementTree as ET

from .common import CheckError, digest, parse_json, xml_tree
from .rust_junit import (
    bindings,
    candidate_file,
    command_property,
    fresh_output,
    property_value,
    write_report,
)

VERSION = "0.2026.11.02.8bf68ee"


# [impl->req~ib-verus-evidence~1]
def observations(raw):
    """Read the qualified function entries, including partial results of failed runs."""
    try:
        data = parse_json(raw)
        identity = data["verus"]
        summary = data["verification-results"]
        if (
            identity["version"] != VERSION
            or not isinstance(identity["toolchain"], str)
            or not identity["toolchain"].strip()
        ):
            raise CheckError("Unsupported or unidentified Verus toolchain")
        if summary["is-verifying-entire-crate"] is not True:
            raise CheckError("Expected whole-crate verification")
        for key in ("success", "encountered-error", "encountered-vir-error"):
            if type(summary[key]) is not bool:
                raise CheckError(f"Invalid Verus {key}")
        for key in ("verified", "errors"):
            if type(summary[key]) is not int or summary[key] < 0:
                raise CheckError(f"Invalid Verus {key} count")
        functions = {}
        modules = data["times-ms"]["smt"]["smt-run-module-times"]
        if not isinstance(modules, list):
            raise CheckError("Invalid Verus module breakdown")
        for module in modules:
            entries = module["function-breakdown"]
            if not isinstance(entries, list):
                raise CheckError("Invalid Verus function breakdown")
            for entry in entries:
                name, passed = entry["function"], entry["success"]
                if (
                    not isinstance(name, str)
                    or not name
                    or type(passed) is not bool
                    or name in functions
                ):
                    raise CheckError(f"Invalid or duplicate Verus function: {name!r}")
                functions[name] = passed
        passed = (
            summary["success"]
            and not summary["encountered-error"]
            and not summary["encountered-vir-error"]
            and summary["errors"] == 0
            and summary["verified"] > 0
            and bool(functions)
            and all(functions.values())
        )
        return functions, passed
    except (KeyError, TypeError, ValueError) as exc:
        raise CheckError(f"Malformed or incomplete Verus JSON: {exc}") from exc


def validate_retained(report, raw):
    """Bind a passing JUnit projection to the original bytes and native identities."""
    root = xml_tree(report)
    hashes = root.findall("./properties/property[@name='verus_json_sha256']")
    exits = root.findall("./properties/property[@name='exit_code']")
    functions, passed = observations(raw)
    if (
        len(exits) != 1
        or exits[0].get("value") != "0"
        or not passed
        or len(hashes) != 1
        or hashes[0].get("value") != digest(raw)
        or root.tag != "testsuite"
        or root.get("name") != "verus"
    ):
        raise CheckError("Retained Verus report does not support passing JUnit evidence")
    cases = list(root.iter("testcase"))
    if (
        len(cases) != len(functions)
        or {case.get("name") for case in cases} != functions.keys()
        or any(
            case.get("classname") != "verus"
            or set(child.tag for child in case) - {"properties"}
            or case.get("status", "passed") != "passed"
            for case in cases
        )
    ):
        raise CheckError("Retained JUnit cases differ from native Verus function outcomes")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--bindings", action="append", default=None, metavar="RS_FILE")
    parser.add_argument("--verus", default="verus")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    extra = args.args[1:] if args.args[:1] == ["--"] else args.args
    try:
        report = fresh_output(args.report)
        native = fresh_output(args.report + ".verus.json")
        source = candidate_file(args.source)
        if not source.is_file():
            raise CheckError(f"Missing Verus source: {source}")
        links = bindings(args.bindings or [args.source], "verus")
        command = [args.verus, str(source), *extra]
        suite = ET.Element("testsuite", name="verus")
        command_property(suite, command)
        with native.open("xb") as stream:
            proc = subprocess.run(command, stdout=stream)
        raw = native.read_bytes()
        property_value(suite, "verus_json_sha256", digest(raw))
        property_value(suite, "exit_code", str(proc.returncode))
        try:
            functions, passed = observations(raw)
            for name, success in sorted(functions.items()):
                case = ET.SubElement(suite, "testcase", classname="verus", name=name)
                if name in links:
                    property_value(case, "oft_id", links[name])
                if not success:
                    ET.SubElement(case, "failure", message="Verus verification failed")
            if proc.returncode or not passed:
                raise CheckError(
                    f"Verus whole-crate verification did not pass (exit {proc.returncode})"
                )
        except CheckError as exc:
            ET.SubElement(suite, "error", message=str(exc))
            print(str(exc), file=sys.stderr)
        write_report(report, suite)
        return int(suite.find("error") is not None)
    except (CheckError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
