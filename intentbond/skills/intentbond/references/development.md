# Conditional development procedures

Use the section matching the current operation. Ordinary edits follow the
[main workflow](../SKILL.md).

## Saved-evidence context

When known IDs need missing context, assemble them together:

```sh
ib explain 'req~first~1' 'req~second~1' --compact --evidence /path/to/check/evidence.json
```

This shares metadata and linked locations without rerunning tests. Use
`--format json` for structured IDs or `--snapshot base` for historical items.
Query to resolve gaps, not as a required final step. Follow indirect links as
needed; saved evidence establishes neither complete impact coverage nor current
source agreement. Explain exit 0 means inspection succeeded, not validation passed.

For a nondefault OFT installation, keep `INTENTBOND_OFT_JAR` set or pass `--oft-jar`
to inspection commands as well as check; saved evidence does not configure the
local JAR path.

## Review policy

Use trusted `review_paths` for implementation roots when code-only changes should
leave review pending. Candidate scope edits remain proposals until adopted through
the caller's process. Keep revision enforcement optional; strict imported-content
revision policy also applies to editorial edits. Review meanings independently of
IDs or structural coverage. See [identity and exact versions](semantics.md#identity-and-exact-versions).

## Review worklists

For a larger or interrupted review, optionally create a worklist:

```sh
ib review start --repo ROOT --evidence PATH --out NEW_DIRECTORY
ib review next --worklist DIRECTORY
ib review record TASK_ID --worklist DIRECTORY --state reviewed -m 'What was inspected'
ib review status --worklist DIRECTORY
```

Use the exact task ID and a meaningful note. States are `reviewed`, `deferred`
and `pending`; deferred items remain incomplete. The directory must be new and
outside source and evidence. The plan covers changed files and immediate graph
neighbors, so inspect affected behavior beyond those links. Every resume matches
current source and trusted policy. After a repair, run a fresh check and start a
fresh worklist; old notes remain references, not completion of the new change.
Progress is unsigned local accounting and never clears semantic review or supplies
an assurance approval.

## Verify exported source

Once the change is committed or exported to another checkout, verify the exported
commit against saved evidence using the original baseline:

```sh
ib verify --repo /path/to/repo --base STARTING_COMMIT --candidate EXPORTED_COMMIT \
  --evidence /path/to/new-evidence/evidence.json
```

Add the same `--scope` if one was supplied. For exit-4 evidence, use
`--allow-pending-review` only when the caller enforces review before acceptance;
verification leaves it pending. Verify matches source without rerunning tests.
Recheck changed contents. Keep the evidence, source identity and pending decisions
in the existing handoff; verification does not authorize publishing or acceptance.

## Optional change guard

When requested, `ib guard prepare --base START --evidence BASE_EVIDENCE
--declaration CHANGE_JSON --out NEW_DIRECTORY` freezes a change declaration outside
the repository and evidence. It preserves baseline requirement references except
explicit authorized changes/removals, and selects protected paths and named
retained regression checks. Keep the printed plan digest in caller-controlled
task state. After the normal candidate check, run `ib guard check --evidence
CANDIDATE_EVIDENCE --plan PLAN_JSON --plan-sha256 CALLER_RETAINED_DIGEST` with the
original trusted scope. Never derive the expected digest from candidate input.

Missing requirements, protected edits, unresolved checks and changed check source
remain separate diagnostics. Missing execution associations are visible gaps.
Legitimate implementation edits can pass; changed assertion files need reassessment.
The guard retains native rejection/pending review and grants no semantic approval.
The declaration schema and worked example are in the project's
[command reference](https://github.com/kbak/intentbond/blob/main/docs/change-guard.md).

## Optional bounded repair

When the caller requests a repair loop, `ib repair run` consumes the accepted
guard plan and an independently pinned repair policy. Supply a trusted external
adapter for attributed cases, reference checks, observations, regression tests
and local proposals. Keep those inputs outside candidate source and use the
original trusted checking scope. The first profile permits selected Python
function bodies, up to two repairs and one adversarial pass under a shared budget.

Review `result.json`, retained counterexamples, the complete candidate diff,
native preservation checks and source verification before applying the output
copy. Status 4 keeps semantic review pending; status 5 means unresolved evidence.
Never turn either into approval. Ordinary development does not invoke repair
automatically. The policy, protocol and trust limits are in the
[repair guide](https://github.com/kbak/intentbond/blob/main/docs/repair.md).

For a new change request, preserved behavior alone may allow a no-op. The optional
`completion` policy pins an external request and checker and records source-bound
task completion separately. Valid negative feedback uses the same bounded repair
path; missing or stale evidence cannot pass. Qualify the checker against legitimate
alternatives and missed-request controls, and retain every native preservation and
review gate. Omit the option to keep existing behavior.
