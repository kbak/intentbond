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
