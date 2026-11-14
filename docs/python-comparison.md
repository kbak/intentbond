# Compare preserved Python behavior

`ib compare-python` generates boundary inputs, observes an accepted baseline and
candidate in fresh Python processes, and compares explicitly preserved outputs.
It requires no model service, custom generation adapter or separately authored
reference implementation.
Ordinary check, verify, guard and repair commands do not invoke it.

The caller supplies the accepted baseline, valid input domain and observation
points. This checks preservation, not whether the baseline is correct or a newly
requested feature was implemented. No prose-to-contract inference is performed.

## Policy and invocation

Keep this policy outside the repository and retain its digest in caller-controlled
task/CI state. Select an immutable full Git commit, not a branch name:

```json
{
  "schema_version": 1,
  "baseline": "REPLACE_WITH_FULL_ACCEPTED_COMMIT",
  "functions": [{
    "id": "session", "path": "session.py", "symbol": "state",
    "arguments": {
      "seconds": {"type": "integer", "min": 0, "max": 3600, "boundaries": [1800]}
    },
    "observations": [{"requirement": "req~session-expiration~1", "path": ["expired"]}]
  }],
  "limits": {"cases": 100, "seconds": 60, "call_seconds": 2, "shrink_steps": 20}
}
```

For a function returning `{"expired": true, "label": "Continue"}`, only `expired`
is compared. An equivalent expiry refactor or authorized label change passes;
changing `>= 1800` to `> 1800` produces a counterexample at 1800. Select only
behaviors that must remain unchanged. Requirement references attribute observations,
not proven causal blame; the caller keeps them consistent with maintained
requirements and change authorization. This command does not perform OFT review.

```sh
ib compare-python --repo /path/to/project \
  --policy /trusted/preservation.json --policy-sha256 CALLER_RETAINED_DIGEST \
  --out /outside/source/new-comparison
```

`--candidate` defaults to `worktree`; an explicit commit also works. Output must
be new and outside source. The Python API is
`intentbond.python_compare.compare_python(repo, policy, policy_sha256, out,
candidate="worktree", replay=None, replay_sha256=None)`.

## Supported domain and assumptions

- Select 1–16 synchronous top-level Python functions in captured `.py` files,
  each with up to eight keyword arguments. Captured local helpers can be imported.
- Integer domains use inclusive signed 64-bit bounds and up to 32 explicit
  boundaries. Samples include endpoints, adjacent in-domain values, zero where
  valid, midpoint, and each boundary plus its neighbors. This is finite sampling.
- Enum domains are `{"type":"enum","values":[...]}` with 1–32 distinct finite
  JSON values, including strings, objects and lists. Generation uses the full
  Cartesian product of the argument samples. Empty argument maps call zero-argument
  functions. Oversized products are rejected rather than silently truncated.
- An observation path contains object keys or nonnegative list indices; `[]`
  selects the whole return. Equality is exact, type-sensitive JSON equality with
  object key order ignored. Other equivalences require a reviewed observation
  wrapper; numerical tolerances or unordered collection semantics are not inferred.

Functions must be pure and deterministic. Each version/input is observed twice
in fresh interpreters; selected outputs must repeat. A stable candidate exception
or missing field differs from a valid baseline return. Baseline exceptions/missing
fields, unsupported values, async functions, argument mutation, import/call setup
failures, unstable observations and timeouts remain unresolved. Unselected output
changes are deliberately outside the comparison.

These are **trusted local code executions, not an OS security sandbox**. Use
caller-controlled isolation for untrusted code. Fresh processes and repeated
observations do not prove purity/determinism. Python/runtime, installed dependencies
and external state remain assumptions; effects and concurrency are unsupported.

## Evidence, reduction and replay

`comparison.json` records exact source identities, observations, attributed
differences, reductions and diagnostics. Policy, manifests and process evidence
remain outside source. Temporary execution copies are removed even on unresolved
outcomes. Source/policy drift prevents completion; changes restored between checks
cannot be detected. The command does not intentionally edit original source.

| Status / exit | Meaning |
| --- | --- |
| `no_difference` / 0 | All scheduled finite comparisons completed without a difference; no whole-domain or semantic approval claim. |
| `regression` / 1 | A reproducible difference in a declared preserved observation; the bounded run completed. |
| Input error / 2 | Invalid policy, pin, repository, baseline or output location. |
| `unresolved` / 5 | Execution, integrity or time prevented completion. Retained differences remain diagnostic evidence. |

Failing inputs are saved immediately to `regressions.json`. Afterwards, the first
failure per function is reduced within a shared step limit: integer arguments move
toward the in-domain value nearest zero; enums toward earlier declared values.
Each retained reduction is re-observed against both versions and must retain the
original implicated differences. There is no global-minimum claim. A timeout
during reduction retains known counterexamples but makes the run unresolved.

Replay the retained cases against a later edit with the same policy and baseline:

```sh
ib compare-python --repo /path/to/project \
  --policy /trusted/preservation.json --policy-sha256 CALLER_RETAINED_DIGEST \
  --replay /outside/source/prior/regressions.json --replay-sha256 RETAINED_CASE_DIGEST \
  --out /outside/source/new-replay
```

Replay validates domains and re-observes baseline expectations instead of trusting
labels blindly. It runs only retained cases, without generation or reduction, and
keeps them even when the candidate passes. Empty replay sets are rejected; prior
files remain unchanged. Reports can inform the explicit repair workflow, but this
command neither applies repairs nor automatically installs a repair adapter.

A trusted completion checker can convert a completed result with
`intentbond.repair_feedback.python_comparison_failures` and the opt-in
[structured repair handoff](repair.md#structured-failure-handoff). Supply
caller-retained source and policy identities; unresolved comparisons must stop
the check. Baseline preservation still needs separate checks for new behavior.

Limits allow at most 1000 generated cases, 1000 reduction evaluations, 600 seconds
shared execution time and 60 seconds per subprocess. Each evaluation makes four
observations. Replay uses at most the original case-plus-reduction allowance.
Snapshot/check overhead consumes the shared budget; overdue final checks remain
unresolved. Existing Git capture has its own timeout, so this is not an OS-level
hard wall-clock termination promise. Policy, response and retained JSON each have
a 1 MiB admission limit; source size and process-log storage remain caller concerns.
