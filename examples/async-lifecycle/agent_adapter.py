"""Lifecycle instructions and reference phases over the shared command bridge."""

import sys
from pathlib import Path

import adapter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent_bridge as bridge  # noqa: E402

INSTRUCTIONS = (
    "Repair the concrete failures below. Read requirements.md: every accepted "
    "requirement remains binding, including valid Unicode names, original submitted "
    "values, display_name wire fields, the Continue label and latest-request error/pending "
    "behavior. Only the body of Form.validate in client/controller.py is authorized. "
    "Keep its signature, all other source, requirements and existing tests/data intact. "
    "The current tests include retained regressions; run python -B run_tests.py. "
)


def main():
    config, request, response = map(Path, sys.argv[1:])
    q = bridge.read(request)
    if q["phase"] == "propose":
        result = {
            "source_sha256": q["source_sha256"],
            "proposal": bridge.propose(
                q,
                config,
                request.parent / "agent",
                instructions=INSTRUCTIONS,
                report_path="test-results.xml",
            ),
        }
    else:
        result = adapter.answer(q, "repair", request)
    bridge.save(response, result)


if __name__ == "__main__":
    main()
