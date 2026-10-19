"""Concise CLI feedback; the retained evidence remains the complete record."""

import codecs
from contextlib import contextmanager
from threading import Event, Thread

from junitparser import JUnitXmlError

from . import boundaries
from .common import CheckError, xml_tree
from .testing import report_cases


@contextmanager
# [impl->req~ib-check-progress~1]
def follow_test_log(out, stream=None):
    """Optionally follow the retained log without changing command execution."""
    if stream is None or out.exists() or out.is_symlink():
        yield
        return
    stopped = Event()

    def follow():
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        source = None
        try:
            stream.write(f"Following test output: {out.resolve() / 'tests.log'}\n")
            stream.flush()
            while True:
                if source is None:
                    try:
                        source = (out / "tests.log").open("rb")
                    except FileNotFoundError:
                        pass
                if source is not None:
                    while chunk := source.read(8192):
                        stream.write(decoder.decode(chunk))
                        stream.flush()
                if stopped.is_set():
                    stream.write(decoder.decode(b"", final=True))
                    stream.flush()
                    return
                stopped.wait(0.1)
        except (OSError, ValueError):
            pass  # Display failure cannot replace validation or its exit status.
        finally:
            if source is not None:
                source.close()

    thread = Thread(target=follow, name="ib-test-output", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stopped.set()
        thread.join(timeout=1)


def _excerpt(value, limit):
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "… [excerpt]"


def _failure_lines(out):
    try:
        failures = [
            case
            for case in report_cases(xml_tree(out / "tests.xml"))
            if case.is_failure or case.is_error
        ]
        if failures:
            lines = ["Reported failures (excerpt; full details in test report):"]
            for case in failures[:3]:
                name = "::".join(part for part in (case.classname, case.name) if part)
                detail = "\n".join(
                    "\n".join(part for part in (result.message, result.text) if part)
                    for result in case.result
                )
                lines.append(f"  {_excerpt(name, 180)}: {_excerpt(detail, 650)}")
            if len(failures) > 3:
                lines.append(f"  {len(failures) - 3} more failing cases in test report")
            return lines
    except (CheckError, JUnitXmlError, ValueError, TypeError):
        pass  # Missing or malformed reports cannot replace the recorded check outcome.
    try:
        with (out / "tests.log").open("rb") as log:
            log.seek(0, 2)
            log.seek(max(0, log.tell() - 1800))
            tail = log.read().decode("utf-8", errors="replace")
        if tail.strip():
            return ["Test log excerpt (last 1800 bytes, up to 24 lines):", *tail.splitlines()[-24:]]
    except OSError:
        pass
    return []


def render_check(result, out):
    out = out.resolve()
    lines = [f"{result['status']}: {out / 'evidence.json'}"]
    if "base" in result:
        lines.append(f"baseline: {result['base']['commit']}")
    if "candidate" in result:
        lines.append(f"source: {result['candidate']['sha256']}")
    tests = result["tests"]
    lines.append(f"tests: {tests['status']} ({tests['level']}); source={tests['source_status']}")
    # [impl->req~ib-check-progress~1]
    trace_durations = [
        command["duration_seconds"]
        for snapshot in result.get("trace", {}).values()
        for key in ("import", "trace")
        if "duration_seconds" in (command := snapshot.get(key, {}))
    ]
    timings = []
    if trace_durations:
        timings.append(f"trace commands={sum(trace_durations):.3f}s")
    if "duration_seconds" in tests:
        timings.append(f"tests={tests['duration_seconds']:.3f}s")
    if timings:
        lines.append("timings: " + "; ".join(timings))
    if "counts" in tests:
        lines.append("counts: " + ", ".join(f"{k}={v}" for k, v in tests["counts"].items()))
    if "error" in tests:
        lines.append("test error: " + _excerpt(tests["error"], 600))
    review = result.get("review", {})
    lines.append(
        f"semantic review: {review.get('status', 'not_recorded')}"
        f"; changes={review.get('change_count', 'unknown')}"
    )
    lines.extend(boundaries.lines(result.get("source_boundaries")))
    diagnostics = result["diagnostics"]
    lines.extend("- " + _excerpt(message, 600) for message in diagnostics[:5])
    if len(diagnostics) > 5:
        lines.append(f"- {len(diagnostics) - 5} more diagnostics in evidence.json")
    for name in (
        "review.json",
        "review.patch",
        "base-import.log",
        "candidate-import.log",
        "base-trace.log",
        "candidate-trace.log",
        "tests.xml",
        "tests.log",
    ):
        if name in result.get("artifacts", {}):
            lines.append(f"{name}: {out / name}")
    if tests["status"] in {"failed", "error"}:
        lines.extend(_failure_lines(out))
    if result["status"] == "review_required":
        lines.append("Automated checks passed; external semantic review is required.")
    lines.append(
        "Review the full candidate diff and linked behavior; checks do not prove conformance."
    )
    return "\n".join(lines)
