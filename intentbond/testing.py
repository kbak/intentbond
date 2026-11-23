import os
import shutil
import xml.etree.ElementTree as ET

from junitparser import Attr, JUnitXml, TestCase

from .cargo_build import BUILD_ENV, build_passed, run_with_build, validate_build_evidence
from .common import CheckError, run, xml_tree
from .verus_junit import validate_retained


class ReportCase(TestCase):
    # Existing fixtures use the common disabled/notrun attribute dialect.
    status = Attr("status")


def report_cases(root):
    cases = [ReportCase.fromelem(case) for suite in JUnitXml.fromroot(root) for case in suite]
    # Unsupported wrappers must not silently hide cases from junitparser's iterator.
    if len(cases) != len(list(root.iter("testcase"))):
        raise CheckError("Unsupported JUnit structure: not every testcase was parsed")
    return cases


def skipped(case):
    return case.is_skipped or case.status in {"skipped", "disabled", "notrun"}


# [impl->req~ib-junit-completion~1]
def junit_counts(path):
    root = xml_tree(path)
    if root.tag not in {"testsuite", "testsuites"}:
        raise CheckError("Test report must be JUnit testsuite/testsuites XML")
    cases = report_cases(root)
    counts = {"total": len(cases), "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for case in cases:
        if case.is_error:
            counts["errors"] += 1
        elif case.is_failure:
            counts["failed"] += 1
        elif skipped(case):
            counts["skipped"] += 1
        else:
            counts["passed"] += 1
    # junitparser intentionally does not validate report completeness. Preserve
    # suite-level failures and omitted cases without imposing completion policy.
    for suite in root.iter():
        if suite.tag in {"testsuite", "testsuites"}:
            if suite.find("error") is not None or suite.find("failure") is not None:
                counts["suite_failed"] = True
            if "tests" in suite.attrib:
                try:
                    declared = int(suite.attrib["tests"])
                except ValueError as exc:
                    raise CheckError("Invalid JUnit tests count") from exc
                if declared != len(list(suite.iter("testcase"))):
                    raise CheckError("JUnit declared test count differs from reported test cases")
            for field in ("failures", "errors", "skipped", "disabled"):
                try:
                    value = int(suite.get(field, "0"))
                except ValueError as exc:
                    raise CheckError(f"Invalid JUnit {field} count") from exc
                if value < 0:
                    raise CheckError(f"Invalid JUnit {field} count")
                if value and field in {"failures", "errors"}:
                    counts["suite_failed"] = True
                if value and field in {"skipped", "disabled"}:
                    if value > sum(skipped(case) for case in report_cases(suite)):
                        raise CheckError("JUnit skip count lacks corresponding case outcomes")
                    counts["suite_skipped"] = True
    return counts


# [impl->req~ib-junit-completion~1]
def counts_pass(counts, scope):
    return bool(
        counts["passed"]
        and not (counts["failed"] or counts["errors"] or counts.get("suite_failed"))
        and (
            scope.get("policy", {}).get("allow_skipped_tests", True)
            or not (counts["skipped"] or counts.get("suite_skipped"))
        )
    )


# [impl->req~ib-report-merge~1]
def merge_reports(reports):
    """Preserve report-level outcomes and namespace suites by their source path."""
    merged = ET.Element("testsuites")
    for name, report in reports:
        junit_counts(report)
        root = xml_tree(report)
        group = ET.SubElement(merged, "testsuite", name=name)
        if root.tag == "testsuites":
            group.attrib.update(root.attrib)
            group.set("name", name)
            group.extend(root)
        else:
            group.append(root)
    return merged


def verus_report_pairs(config):
    """Resolve trusted report paths to their deterministic retained filenames."""
    reports = config.get("reports", [config.get("report")])
    return {
        name: (f"tests-{i}.xml" if "reports" in config else "tests.xml", f"verus-{i}.json")
        for i, name in enumerate(reports, 1)
        if name in config.get("verus_reports", [])
    }


def execute_tests(snap, scope, out):
    config = scope["tests"]
    names = (
        config.get("reports", [config.get("report")])
        if config.get("format", "junit") == "junit"
        else []
    )
    reports = [snap.root / name for name in names]
    # [impl->req~ib-fresh-reports~1]
    native = verus_report_pairs(config)
    for report in [*reports, *(snap.root / (name + ".verus.json") for name in native)]:
        if report.exists() or report.is_symlink():
            raise CheckError(
                "Configured JUnit report already exists in candidate; require a fresh generated report"
            )
        if not report.resolve().is_relative_to(snap.root):
            raise CheckError("JUnit report must stay inside the candidate")
        report.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.pop(BUILD_ENV, None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # Commands using PROJECT_DIR must target the captured candidate.
    env["PROJECT_DIR"] = str(snap.root)
    if "cargo_build" in config:
        result = run_with_build(snap, config, out, env)
    else:
        result = run(
            config["command"], snap.root, out / "tests.log", config["timeout_seconds"], env
        )
    result["format"] = config.get("format", "junit")
    result["level"] = "suite" if reports else "command"
    # [impl->req~ib-command-results~1]
    if not reports or ("cargo_build" in result and not build_passed(result["cargo_build"])):
        return result
    target = out / "tests.xml"
    try:
        retained = []
        for name, (_, artifact) in native.items():
            path = snap.root / (name + ".verus.json")
            if (
                path.is_symlink()
                or not path.is_file()
                or not path.resolve().is_relative_to(snap.root)
            ):
                raise CheckError(f"Missing or unsafe native Verus report for {name}")
            shutil.copyfile(path, out / artifact)
        # [impl->req~ib-fresh-reports~1]
        for index, (name, report) in enumerate(zip(names, reports), 1):
            if (
                not report.is_file()
                or report.is_symlink()
                or not report.resolve().is_relative_to(snap.root)
            ):
                raise CheckError(
                    f"Test command did not produce a fresh regular JUnit report: {name}"
                )
            copy = out / f"tests-{index}.xml" if "reports" in config else target
            shutil.copyfile(report, copy)
            retained.append({"source": name, "artifact": copy.name})
            counts = junit_counts(copy)  # Validate originals before combining.
            if name in native and not (
                counts["errors"] or counts["failed"] or counts.get("suite_failed")
            ):
                validate_retained(copy, (out / native[name][1]).read_bytes())
        if "reports" in config:
            result["reports"] = retained
            merged = merge_reports((r["source"], out / r["artifact"]) for r in retained)
            ET.ElementTree(merged).write(target, encoding="utf-8", xml_declaration=True)
        result["report"] = target.name
        if "cargo_build" in config:
            validate_build_evidence(
                result["cargo_build"], config["cargo_build"], snap.sha256, target
            )
        counts = junit_counts(target)
        result["counts"] = counts
        if not counts_pass(counts, scope):
            result["status"] = "failed"
            result["error"] = "Report does not satisfy the configured test completion policy"
    except CheckError as exc:
        result["status"] = "error"
        result["error"] = str(exc)
    return result
