"""Optional manual/CI adapter: prepare context from existing Git and check records."""

import argparse
from pathlib import Path
from uuid import uuid4

from intentbond.assurance import capture_context
from intentbond.assurance_contract import policy
from intentbond.common import write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--candidate", default="worktree")
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--profile", choices=["lightweight", "ai-native-sdlc"], default="lightweight"
    )
    parser.add_argument("--require-review", action="store_true")
    parser.add_argument("--require-intent", action="store_true")
    parser.add_argument("--decision", action="append", default=[])
    parser.add_argument("--invocation", default=None)
    args = parser.parse_args()
    if args.out.resolve().is_relative_to(args.repo.resolve()):
        parser.error("--out must be outside the repository")
    required = ["execution", "traceability"] if args.evidence else []
    if args.require_review:
        required.append("review")
    if args.require_intent:
        required.append("intent")
    checking_policy = policy(profile=args.profile, required=required, decisions=args.decision)
    change = capture_context(
        args.repo,
        args.base,
        args.candidate,
        checking_policy,
        args.invocation or str(uuid4()),
        evidence_path=args.evidence,
    )
    args.out.mkdir(parents=True, exist_ok=False)
    write_json(args.out / "policy.json", checking_policy)
    write_json(args.out / "change.json", change)
    print(args.out.resolve())


if __name__ == "__main__":
    main()
