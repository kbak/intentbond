---
name: intentbond
description: Capture intent, draft specifications, or implement and review a task with OpenFastTrace, using the supplied scope and baseline to follow linked documentation, code, tests, and evidence.
---

Maintain affected intent, requirements, code, tests and their links together.
Compare the change with its starting baseline and retain evidence for review.
Links establish declared coverage; tests establish their recorded outcomes;
neither grants approval or proves that the user's intent is satisfied. Consult
[result meanings](references/semantics.md) when a distinction needs clarification.

## Task context

Reuse supplied context and matching local/package/factory tooling. Preserve local
changes and pinned revisions. Read only references needed for the current task;
supplied inline guidance needs no second lookup. Discussion and drafting do not
authorize implementation. Continue authorized work, asking only about unresolved
decisions that block it.

Retain the repository's absolute path, trusted scope and starting baseline commit
before editing. Use supplied inputs. Otherwise the CLI uses adopted scope.json
and the merge base with the locally known default branch (HEAD on that branch or
detached HEAD). Work based on another feature/release branch needs an explicit
baseline. Reuse the starting commit for checking and verification; resolving the
default after committing on the default branch would omit the change. Candidate
scope edits and approval files cannot authorize themselves.

Locate affected promises through headings, capability tables or targeted search.
Read their full meaning and follow links back to intent and through design, code
and assertions. When authoring intent or requirements, use the applicable section
of [authoring guidance](references/requirements.md). If starting requirements and
links are missing, use [baseline recovery](../recover-baseline/SKILL.md), then
continue authorized implementation and review the combined change. Work on an
adopted baseline does not repeat recovery.

## Implementation and review

Maintain affected assertions, generators, assumptions and documentation with the
change. Keep IDs beside relevant behavior and assertions, following trusted
coverage and revision policy. Existing links may suffice; unchanged promises need
no wording or ID edits, and files need no arbitrary annotations. Do not weaken
promises or remove obligations to hide failures. Conflicts with approved meaning
need a decision through the caller's existing process.

Use additional guidance for the work it covers:

- **Discover or substantively review properties:** use the
  [discovery pass](../property-testing/SKILL.md#discover-and-review-properties).
- **Translate or change a promise:** use shared
  [translation guidance](../property-testing/references/formalization.md).
- **Add or strengthen executable properties:** use
  [check implementation](../property-testing/SKILL.md#implement-and-maintain-checks)
  and only the applicable framework guide. Property tests are not required for
  every change.

Before a commit or final handoff, review the full intended Git diff, including
new files and affected unchanged promises. Start from substantive behavior and
boundary cases, including code-only changes; existing links are starting points,
not the extent of review. Check that implementation and assertions support the
promises. For substantial semantic changes, seek a small counterexample using
independent source examples or a suitable oracle, accounting for its assumptions;
tests and proofs derived from one specification can share an omission. See
[independent semantic checks](references/semantics.md#independent-semantic-checks).
Preserve useful counterexamples as regressions. After a repair, inspect its delta
and affected relationships; repeat full review if earlier conclusions or scope
no longer hold.

## Check and hand off

Run the configured check on the completed candidate and after repairs:

```sh
ib check --repo /path/to/repo --base STARTING_COMMIT --out /path/to/new-evidence
```

Add the caller's `--scope PATH` when supplied; the default candidate is `worktree`.
`python -m intentbond` is equivalent. Each evidence directory must be new and
outside the repository. The check runs configured tests; repeat them separately
only for a concrete need. `--progress` follows retained test output during long
checks. Trace/test timings do not measure agent effort or all checking overhead.

Start with printed status, counts, diagnostics and paths. Inspect required changes
in review.json; review.patch selects specification/test/optional review paths and
may not contain the full candidate diff or require repeating completed review.
Open detailed reports/logs for failures or unresolved questions.
Use `ib impact --compact --evidence PATH` for counts and review observations;
follow its full-output command for details. Gaps and hubs are inspection cues,
not proof of missing requirements or correctness.

Exit 0 passes automation; exit 4 leaves semantic review pending. Other exits cannot
establish completion. Repair in-scope failures and report prerequisite or baseline
defects without bypassing policy. Changed source requires a fresh check; an earlier
passing bundle cannot replace a failed run. Suite success alone does not establish
execution or adequacy of every linked test.

In the existing handoff, retain the actual baseline, exit code and complete evidence
path; reuse the requirement-change summary and identify checked behavior, gaps,
contradictions and uncertainty with IDs/locations. Completion requires current-source
agreement, successful checks and the caller's review gates. Follow the existing Git
process; this skill does not authorize publishing or acceptance.

## Conditional procedures

| Situation | Read when needed |
| --- | --- |
| Tooling is unavailable | [Standalone setup](references/setup.md) |
| Known IDs need context from saved evidence | [Explain linked context](references/development.md#saved-evidence-context) |
| Selecting review paths or revision enforcement | [Review policy](references/development.md#review-policy) |
| A larger/interrupted review needs a resumable worklist | [Review worklists](references/development.md#review-worklists) |
| Caller requests protected paths or retained regression obligations | [Optional change guard](references/development.md#optional-change-guard); freeze the authorized declaration before edits and retain its digest outside candidate control |
| Caller requests bounded counterexample-driven repair | [Optional bounded repair](references/development.md#optional-bounded-repair); supply trusted adapters and retain native review gates |
| Trusted scope enables `tests.execution_links` | [Execution links](references/execution-links.md); review declarations, runner associations and recorded outcomes together |
| The checked change is committed or exported | [Verify exported source](references/development.md#verify-exported-source) |
