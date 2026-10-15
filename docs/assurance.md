# Optional assurance assessment

Use `ib assess` to combine existing checking evidence, semantic review, and
decisions for an identified change. It supports manual development, CI, coding
assistants, and factories. Existing `check` and `verify` workflows need no changes.
Assessment runs no tests, OFT commands, or models and grants no merge/deploy authority.

## Prepare and assess a change

Adapters build context from existing source, accepted requests, policy, and
retained results. Existing filenames remain valid. Routine changes need no
separate intent/specification/plan package.

The [example adapter](../examples/assurance/prepare.py) prepares context from Git
and optional existing check output:

```sh
ib check --repo /path/to/project --base BASE --out /tmp/change-check
python examples/assurance/prepare.py --repo /path/to/project --base BASE \
  --evidence /tmp/change-check/evidence.json --out /tmp/change-context
ib assess --repo /path/to/project \
  --change /tmp/change-context/change.json \
  --policy /tmp/change-context/policy.json \
  --evidence /tmp/change-check/evidence.json --out /tmp/change-assessment
```

Choose fresh output directories outside the repository. If checking used an
external scope, supply the same trusted `--scope` to assessment. Check exit 4
means automation passed with specification/test review pending; assessment
preserves this obligation even when policy did not explicitly require review.

Omit `--evidence` in both preparation and assessment for an untraced project.
Source matching works without Java/OFT; execution and traceability remain
unestablished. Requiring unavailable evidence makes assessment incomplete.
Existing `ib check` retains its OFT and nonempty-requirement requirements.

## Version one contracts

Unknown fields, versions, and duplicate JSON keys are errors. Contract versioning
is independent of existing check evidence. Helpers in `assurance_contract` and
`assurance` use the standard library and existing source/evidence functions.

| Record | Fields |
| --- | --- |
| Policy | `schema_version: 1`, `profile`, `required`, `decisions`, `reviewers`, `independent_review` |
| Profile | `name`, `version: 1`, `required_roles`, `immutable_roles` |
| Change | `schema_version: 1`, `invocation`, `policy_sha256`, nonempty `repositories`, `artifacts`; optional `accepted_request`, `implementer` |
| Repository | `base`, `candidate`, sorted `changed_paths`; optional `scope_sha256`, `evidence_sha256`, `requirement_index` |
| Source | Full Git `commit`, manifest `sha256`; optional existing snapshot `kind` and `file_count` |
| Artifact | Unique `id`, `repository`, `role`, relative `path`, regular-file `sha256` or null; optional `accepted_sha256` |
| Accepted request | Caller-retained authoritative `reference` and `sha256` |
| Review | `schema_version: 1`, `context_sha256`, `producer`, `verdict`, `traceability_assessment`, `intent_alignment` |
| Decision | `schema_version: 1`, `context_sha256`, `producer`, `id`, `actor`, `outcome` |

Record digests use `digest(canonical(record))` from `intentbond.common`. Source
manifest hashes, commits, file hashes, original policy bytes, and canonical
policy hashes remain distinct. `evidence_sha256` binds the exact designated
evidence.json bytes for this invocation. Context preparation does not validate
evidence; standalone assessment does, using existing `verify` logic.

Required checks are `execution`, `traceability`, `review`, and/or `intent`.
Source matching and declared artifact obligations are always required. Optional
observations retain incomplete states without becoming required by implication.

The built-in `lightweight` profile requires no document roles. Optional
`ai-native-sdlc` also requires no new documents, but protects accepted `intent`,
`specification`, and `acceptance` artifacts when mapped; `plan` may evolve.
Map frozen task snapshots separately from living specifications. Accepted hashes
come from trusted acceptance records, never candidate approval files. Custom
profiles can require/protect different roles using a distinct name. Profiles
are bounded declarative data, not executable plugins or lifecycle schedulers.

## Review and decisions

Review verdicts are `satisfied`, `failed`, or `incomplete`. Traceability records
use project, summary, and changes with changed_paths, behavior, status
(`covered`, `not_needed`, `missing`, `uncertain`), rationale, and applicable
requirement/documentation/implementation/verification references and remediation.
Covered behavior needs all four reference groups; missing tracing needs a repair.
Scoped changed paths must be accounted for and requirement IDs must resolve in
the selected source index. Relevance remains the reviewer's judgment.

Intent records contain project, status (`aligned`, `conflict`, `uncertain`),
references, and summary. Required intent review covers every repository exactly
once. Conflicts and uncertainty survive an overall passing review label.

Supply caller-trusted review using `--review /trusted/review.json` and a list of
decisions using `--decisions /trusted/decisions.json`. Records bind the entire
context, including source, policy, and invocation. Required decision IDs come from
policy; their outcomes are `accepted` or `rejected`. Missing decisions remain
pending even with passing tests and review.

The caller establishes producer identity and authorization through its own
trusted process. Records are unsigned; hashes and actor names do not authenticate
anyone. Policy `reviewers` restricts caller-established producer identities.
Independent review also requires a known implementer distinct from the reviewer.
A candidate choosing a different label cannot establish independence. Local or
self-review remains usable when policy permits it, with its provenance retained.

## Results and adapters

`assessment.json` retains context, policy, obligations and supporting references,
review, decisions, and limitations. `summary.md` is a compact readable report.
Exit codes: 0 satisfied, 1 failed, 2 invalid input/verification error, 4 decision
pending, 5 incomplete. Required incomplete obligations take precedence over
failures, then pending decisions; individual outcomes remain visible. A satisfied
assessment establishes only the selected obligations, never overall correctness.

Standalone assessment validates one Git repository, both source identities,
declared regular-file artifacts, complete selected changed paths, and applicable
retained check evidence. Without a check scope, paths must cover all captured
changes. Accepted hashes and authorization references remain caller trust inputs.
External dependencies/environment inputs and automatic proof preservation across
changes are outside the source identity contract.

Trusted adapters may call `assess(context, policy, observations=..., review=...,
decisions=...)` after their existing validation in the same trusted execution.
`observation(...)` creates context-bound verifier receipts. This library boundary
does not authenticate or revalidate supplied receipts; never expose it as an
untrusted evidence endpoint. Use `assess_files` at filesystem boundaries. Groups
retain separate repository identities without implying atomic approval.

IntentMade uses existing controller checks and independent review without another
model or test pass. Non-opted-in repositories retain their existing dependency
boundary. Formal evidence retains its existing model assumptions and bounds;
arbitrary external results do not become validated by appearing as references.
