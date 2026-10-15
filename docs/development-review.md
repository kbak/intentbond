# Review changes during development

Keep requirements and annotations authoritative. Use the existing OFT graph and
saved check evidence to decide what to inspect; recorded relationships do not
replace reading the full intended change and its affected behavior.

## Select the review and revision policy

The trusted scope's `specification_paths` and `test_paths` already select review.
Add implementation roots to `review_paths` when implementation-only changes should
also leave review pending, for example `"review_paths": ["src"]`. This does not add
trace inputs. IntentBond's own scope selects its `intentbond` implementation root,
examples and AGENTS.md in addition to specification/test paths.

Scope changes are proposals until adopted through the project's review process.
Check the proposal against the existing accepted baseline; subsequent work uses
the new accepted baseline. Editing candidate scope.json cannot lower or raise the
policy applied by that same check. An explicitly supplied `--scope` must come from
the caller's trusted process.

`policy.require_revision_increase` stays optional and defaults to false. Enable
it when every imported requirement-content change needs an explicit revision
increase. It compares imported text and metadata, so editorial edits can require
bumps too. With it disabled, edits remain visible for review and OFT still checks
exact reference revisions. Neither mode judges semantic equivalence or performs
automatic revision updates. See [requirement granularity](requirement-granularity.md).

## Inspect gaps and related work

```sh
ib impact --evidence /tmp/change-check/evidence.json
ib impact --evidence /tmp/change-check/evidence.json --format json
ib explain 'req~retry-cap~2' --evidence /tmp/change-check/evidence.json
```

Impact's additive `inspection` object retains baseline and candidate artifacts,
changed-file artifact membership, coverage gaps, required execution gaps, and
immediate-link hubs. Text shows at most ten hubs; JSON retains all of them.
Explain includes each selected artifact's exact resolving incoming/outgoing links
and degree. Neither command reruns project tests or requires a checkout; both
reuse pinned OFT to report the retained graph.

Interpret observations separately:

| Observation | Meaning |
| --- | --- |
| `no_imported_artifacts` | A surviving changed file selected for tracing contains no imported artifact. This does not establish a missing requirement or untested behavior. |
| `excluded_from_tracing`, `outside_tracing_inputs` | Explicit scope boundaries, not unannotated-code findings. |
| `removed_file` | Baseline references remain visible; there is no candidate file to annotate. |
| Native coverage gap | Preserve OFT's coverage/status and uncovered types. A draft can be UNCOVERED without missing types. This is structural coverage, not requirement satisfaction. |
| Required execution gap | A trusted required identity lacks established passing observations. Distinguish missing declarations, skips and reported nonpassing outcomes. |
| Hub | An artifact has more than one resolving immediate incoming or outgoing link. Degree prioritizes inspection; it is not an error or confidence score. |

The full candidate graph retains linked execution outcomes even for optional
tests. Execution descriptions remain bounded by report completeness and source
stability. Impact validates retained JUnit/OFT associations just as explain does.
Rejected check bundles with the necessary retained artifacts remain inspectable.

## Resume review against the checked source

```sh
ib review start --repo /path/to/project \
  --evidence /tmp/change-check/evidence.json --out /tmp/change-review
ib review next --worklist /tmp/change-review
ib review record 'file:src/retry.py' --worklist /tmp/change-review \
  --state reviewed -m 'Inspected cap behavior, callers and boundary assertions'
ib review status --worklist /tmp/change-review
```

Use the exact task ID printed by next/status. Output directories must be new and
outside both the repository and evidence bundle. All commands support
`--format json`. Start returns 0 when creation succeeds; record returns 0 when a
note is saved. Next/status return 4 while any item is pending or deferred and 0
when every frozen item is reviewed. These exits describe progress, never approval.

The frozen plan contains every changed captured file, artifacts declared on those
files or changed declarations, and their immediate graph neighbors. This includes
files outside tracing or selected semantic-review roots. Unchanged neighbors
shared by both snapshots appear once with candidate context. Changed/removed
baseline artifacts remain inspectable. This is not exhaustive semantic impact;
inspect related behavior beyond recorded links.

Repeated next calls return the same first pending task until its state changes.
Use `--state deferred` with a reason to continue elsewhere while keeping that work
incomplete. Use `--state pending` to reopen an item. Reviewed and deferred states
require a nonempty note. Status retains all notes and deferred tasks even when
there are no pending tasks. Re-running start cannot overwrite an existing queue.
Each task retains its note/state history across deferral and reopening; JSON
includes the history while text presents the current note.

Every operation validates bundle integrity, exact evidence identity, the frozen
task inventory and progress binding, current worktree contents, original baseline,
and trusted checking scope. It does not rerun tests, models or OFT after start.
If check used an external scope, supply that same `--scope` at start; its local
path is remembered and can be overridden on later commands. `--repo` and
`--evidence` can likewise relocate matching inputs without changing their identity.
The commands compare contents with captured manifests, not Git checkout labels.

After a repair or policy change, run a fresh check and start a new worklist.
Previous notes remain in their old directory for reference; completion is not
automatically transferred. No command edits the original check bundle or clears
its pending review. Worklist files are unsigned local observations and are not
accepted as an `ib assess --review` record. Use the existing caller-trusted
[assurance review](assurance.md#review-and-decisions) process for that decision.

Writes use atomic file replacement and an exclusive writer lock. A competing
writer is refused. After an interrupted writer, remove `.writer.lock` only after
confirming the original writer has stopped. Do not place worklists in versioned
product documentation or use task notes as an alternative traceability store.

Run the [development-review example](../examples/development-review) to exercise
both revision policies, missing required execution, unannotated source, hubs,
interrupted review, and a fresh queue after repair.
