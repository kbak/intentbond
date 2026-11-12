"""Run the qualified lifecycle profile with a caller-supplied coding agent."""

import argparse
import json
import sys
from pathlib import Path

import contract
from agent_adapter import bridge
from demo import REGRESSION, baseline
from qualification import qualify
from runtime import ROOT

from intentbond.common import CheckError, digest, write_json
from intentbond.oft import default_jar
from intentbond.repair import repair


def policy(config_path, seconds, completion=None):
    return bridge.policy(
        config_path,
        seconds,
        root=ROOT,
        requirements=contract.REQUIREMENTS,
        edits=[
            {
                "path": "client/controller.py",
                "symbol": "Form.validate",
                "requirements": [contract.ASYNC],
            }
        ],
        regression=REGRESSION,
        completion=completion,
    )


def run(out, config, jar, seconds=240, variant="counter-reset", completion=None):
    if not __debug__:
        raise CheckError("Qualification assertions require Python without -O")
    out, config = out.resolve(), config.resolve()
    if out.is_relative_to(ROOT.parents[1]):
        raise CheckError("Use a new output directory outside the source checkout")
    if config.is_relative_to(out):
        raise CheckError("Keep the agent configuration outside the output directory")
    if not 0 < seconds <= 600:
        raise CheckError("Use a repair budget between 0 and 600 seconds")
    value = policy(config, seconds, completion)
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "references.json", qualify())
    base = baseline(out / "baseline", variant, jar)
    write_json(out / "policy.json", value)
    guard = base["guard"]
    result = repair(
        base["source"],
        base["scope"],
        Path(guard["plan"]),
        guard["plan_sha256"],
        out / "policy.json",
        digest((out / "policy.json").read_bytes()),
        out / "repair",
        jar,
    )
    write_json(out / "result.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--agent-config", type=Path, required=True)
    parser.add_argument(
        "--completion-config", type=Path, help="Pinned request/checker JSON (optional)"
    )
    parser.add_argument("--oft-jar", type=Path, default=default_jar())
    parser.add_argument("--seconds", type=float, default=240)
    parser.add_argument(
        "--variant", choices=("original", "counter-reset", "unique-token"), default="counter-reset"
    )
    args = parser.parse_args()
    result = run(
        args.out,
        args.agent_config,
        args.oft_jar,
        args.seconds,
        args.variant,
        bridge.read(args.completion_config) if args.completion_config else None,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "loop_status": result["loop_status"],
                "reason": result["reason"],
                "evidence": str(args.out.resolve()),
            },
            indent=2,
        )
    )
    sys.exit({"passed": 0, "review_required": 4, "rejected": 1, "unresolved": 5}[result["status"]])
