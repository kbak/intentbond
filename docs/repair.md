# Optional bounded repair

`ib repair run` adds counterexample search and local repair to a caller-pinned
[change guard](change-guard.md). Ordinary `check`, `verify`, recovery and guard
commands do not invoke it. Boundaries support Python function bodies and explicitly
selected structured Lean clauses, with JSON cases and native JUnit execution links.
The runtime selects no model service,
reference implementation or default repair adapter.

For a runnable offline introduction, use the
[async lifecycle example](../examples/async-lifecycle). The source checkout and
source distribution include its form fixture, independent references, retained
counterexamples and deterministic demonstration actor. It uses this existing API
and changes no default behavior. The example is application-specific and does not
ship as a runtime adapter in the wheel.

The example also includes a [caller-command agent bridge](../examples/async-lifecycle#use-a-coding-agent).
It hands concrete failures to a coding agent in a separate workspace and submits
the complete source delta through the same checks. Agent completion is distinct
from accepted repair; partial commands and unsupported edits cannot pass. Model
selection, provider accounting and OS isolation stay with the caller.
The shared [bridge implementation](../examples/agent_bridge.py) also serves the
[reservation example](../examples/reservation), which reuses D4's rollback and
idempotency checks. Each trusted profile supplies its own instructions, references,
regression scaffold, edit boundary and operational report exclusion. Both the
bridge and profile are pinned; neither is selected by candidate output.

The [CLI ordering example](../examples/cli-ordering) adds D3's stable-order case
to the same bridge. Its original five tests miss an equal-name quantity tie
breaker; independent insertion and grouping checks expose it. The offline demo
retains 280 cases, tests a second repair after adversarial feedback, and accepts
legal JSON formatting and alternative implementations within the local boundary.

The caller supplies a trusted external adapter for case generation, reference
labels, observation, regression scaffolding and proposals. IntentBond owns the
limits, source identities, edit boundaries, accumulated cases, preservation
checks and final verification.

## Prepare and run

Prepare a guard from accepted baseline evidence. Preserve the repaired
requirements, select the old named checks, and protect files that must remain
unchanged. Keep the guard-plan digest and repair-policy digest in caller-controlled
task or CI state. Candidate input must not supply its own expected digests.

An illustrative external repair policy (replace digest placeholders):

```json
{
  "schema_version": 1,
  "requirements": ["req~name-validation~1"],
  "edits": [{"path": "server.py", "symbol": "validate",
             "requirements": ["req~name-validation~1"]}],
  "adapter": {
    "command": ["/opt/venv/bin/python", "/trusted/adapter.py"],
    "inputs": {
      "/trusted/adapter.py": "REPLACE_WITH_SHA256",
      "/trusted/reference.py": "REPLACE_WITH_SHA256"
    }
  },
  "regression": {
    "test_path": "tests/test_repair.py",
    "data_path": "tests/repair_cases.json",
    "links_path": "tests/links.json",
    "checks": ["utest~name-repair~1"]
  },
  "limits": {"seconds": 120, "repairs": 2, "cases": 1000}
}
```

Edit and regression paths are literal repository-relative paths. Select one
function per editable file; `Service.batch` selects a method. Editable files
must be traced inputs outside specification, test and protected paths.
Signatures, decorators and bytes outside the function body are immutable.
For a block body, the editable span starts after the header's logical newline
and includes leading blank lines and indented comments, statements, and trailing
indented comments. Comment indentation must be deeper than the selected function's
indentation; an enclosing-level comment before the first statement stays protected.
Trailing comments stop at the first enclosing-level comment or following code.
Blank lines before a trailing body comment belong to the body; separator blank
lines after the last body statement/comment and its final newline stay protected.
For an inline body, only the statements and their same-line trailing comment are
editable. Header comments, parameter comments and the selected function's own
decorators remain protected, including for async functions and methods. Source
outside the span is compared as UTF-8 bytes, without stripping comments or
normalizing source formatting.
This syntactic boundary alone cannot prevent unwanted behavior inside a function.

### Optional Lean clause boundary

To repair a generated predicate candidate, replace the Python edit entry with:

```json
{"path": "candidate.json", "format": "lean-clauses-v1",
 "requirements": ["req~successor~1"]}
```

The JSON candidate has exactly `imports`, `precond_aux`, `postcond_aux` (strings)
and `clauses` (a nonempty array of objects with exactly `requirement` and `expr`).
Each requirement is a unique full maintained reference; each expression is a
nonempty string. Only expressions selected by both the boundary and the proposal's
failed requirement targets may change. Imports, helpers, clause order/identities
and other expressions stay identical. JSON whitespace and object key order may
change; duplicate keys and malformed candidates are rejected.

The candidate must be a `.json` traced input outside accepted specification,
test and protected paths. Accepted natural-language requirements stay protected.
Pin the signature, renderer, Lean checker and reference labels as external adapter
inputs. The core checks structured locality; it does not parse Lean or establish
predicate correctness. The adapter must check compilation and concrete acceptance
and rejection, retain positive cases to detect overrestriction, and report errors,
inconclusive proofs and unknown labels as unresolved observations. Retained tests
must repeat those checks. No Lean toolchain, renderer or model service is bundled
or automatically enabled; this boundary uses the same budgets, guard, regression
retention, source verification and pending semantic review as Python repair.

### Retained regressions

Regression test and data paths must be new selected test inputs. The links path
is an existing JSON object in the `intentbond.unittest_junit` mapping format.
Native execution links and distinct new named regression IDs are required. The
suite must discover the new test. Its scaffold must read the retained case data
on every run, assert accepted outcomes and retain individual failure diagnostics.
Each named OFT test declaration must be unique. Links are added without replacing
existing entries.

```sh
ib repair run --repo /path/to/project --scope /trusted/scope.json \
  --plan /trusted/guard/plan.json --plan-sha256 "$GUARD_SHA256" \
  --policy /trusted/repair.json --policy-sha256 "$REPAIR_SHA256" \
  --out /outside/source/new-repair-run
```

Omit `--scope` to use `scope.json` at the guard's baseline commit. Use the same
trusted scope as the guard. `--oft-jar` and `--java` retain their ordinary meaning.
Output must be a new directory outside source. The guard plan, policy, adapter
and reference inputs must be outside source and output.

The Python API accepts the same inputs and returns the result dictionary:

```python
from pathlib import Path
from intentbond.repair import repair

result = repair(
    repo=Path("/path/to/project"), scope=Path("/trusted/scope.json"),
    plan=Path("/trusted/guard/plan.json"), plan_sha256=guard_digest,
    policy_path=Path("/trusted/repair.json"), policy_sha256=repair_digest,
    out=Path("/outside/source/new-repair-run"), jar=oft_jar,
)
```

## Optional requested-change completion

Preserved behavior alone does not establish that a new change request was done.
Unchanged code may pass every retained test while ignoring a requested refactor.
Add `completion` to the caller-pinned repair policy to check that request:

```json
{
  "request": "/trusted/CHANGE.txt",
  "command": ["/opt/venv/bin/python", "-B", "/trusted/check_completion.py"],
  "inputs": {
    "/trusted/CHANGE.txt": "REPLACE_WITH_SHA256",
    "/trusted/check_completion.py": "REPLACE_WITH_SHA256"
  }
}
```

Pin the request, checker entry point and its dependencies outside candidate source
and output. The request is nonempty UTF-8 text, at most 16 MiB. The checker command
receives absolute request/response JSON paths, using the existing shared deadline.
It must leave source and trusted inputs intact. No model, tool or token budget is
added or reset; provider limits still belong to the caller's agent runner.

The JSON request contains `schema_version: 1`, `worktree`, the text-file `request`
path, `remaining_seconds`, and three bindings: `source_sha256`, `request_sha256`
and `checker_sha256`. The last is the canonical digest of the entire completion
policy, including command and input pins. Exit zero and write exactly:

```json
{
  "schema_version": 1,
  "source_sha256": "ECHO_REQUEST_VALUE",
  "request_sha256": "ECHO_REQUEST_VALUE",
  "checker_sha256": "ECHO_REQUEST_VALUE",
  "status": "failed",
  "errors": ["The requested synchronous settle helper is missing."]
}
```

`passed` requires an empty error list; `failed` requires nonempty text diagnostics.
A nonzero exit, timeout, missing/invalid output, unknown status or binding mismatch
leaves the loop unresolved. A valid failed result produces a `requested_change`
feedback entry for the existing proposal adapter, carrying the request text,
bindings and diagnostics. Its targets remain the policy's preserved requirements
and declared function boundaries. It is not a reference-labelled behavioral case
and is not added to `cases.json` or substituted for retained regressions.
Completion is rechecked every cycle, including after adversarial cases are
installed, and must match the final source.

`result.json` adds `completion` only when enabled: its status, bindings, diagnostics
and saved response path remain separate from native status. A passed completion
checker does not override preservation failure or semantic review. Initial
retained-test failures still stop at `starting_native_checks_not_passing`.
The caller must qualify the request-to-checker translation against missed requests
and legitimate alternatives. Passing a finite checker is not proof that arbitrary
user intent was satisfied.

The shared example bridge accepts `completion=...` in `policy()`. Both profile
`agent_demo.py` commands accept `--completion-config /trusted/completion.json`;
their Python `run()` and `policy()` functions accept the same optional dictionary.
Omitting it preserves previous behavior. The standalone
[maintenance checker](../examples/request_completion.py) can be selected with
`[PYTHON, "-B", CHECKER_PATH, "reservation"]` for explicit state staging with one
Service, or `"async-lifecycle"` for the nested synchronous `settle` refactor.
Supply a matching request and pin that script and request. Use the healthy
`deep-copy`/`original` demo variants when starting from already-correct code.
These are two concrete example requests, not a generic prose evaluator. Existing
profile tests still establish the recorded behavioral preservation outcomes.

## Adapter protocol, version 1

Every invocation appends absolute request and response JSON paths to
`adapter.command`, without shell interpolation. Exit zero, write at most 16 MiB
of finite JSON, and echo the request's exact `source_sha256`. Requests include
`schema_version: 1`, `phase`, `worktree`, `source_sha256`, selected `requirements`
and `remaining_seconds`. Logs and messages are retained.

| Phase | Additional request fields | Response fields besides `source_sha256` |
| --- | --- | --- |
| `generate` | `stage`: `initial` or `adversarial`; accumulated `cases` | `cases`: nonempty batch with new IDs |
| `observe` | all accumulated `cases` | `observations`: exactly one result per case |
| `regression` | `regression` policy and initial `cases` | `test`: Python source; `links`: new test-method to ID-list mapping |
| `propose` | up to eight concrete `failures`, full `failure_count`, one-based `round` | `proposal`: targets, reason and complete file texts, or null |

A case has exactly these fields:

```json
{
  "id": "unicode-blank",
  "requirements": ["req~name-validation~1"],
  "kind": "negative_input",
  "input": {"display_name": "\u00a0"},
  "accepted": [{"ok": false, "error": "required"}],
  "label": {
    "status": "confirmed",
    "method": "Independent reference and Unicode property checker agree",
    "sources": ["/trusted/reference.py"]
  }
}
```

The initial batch must cover every selected requirement and include a `positive`
control. Other kinds are `negative_input` and `negative_output`; the adapter
defines their domain meaning. Labels require confirmed status, a nonempty method
and sources from pinned adapter inputs. Missing, conflicting or unknown labels
stop the run as unresolved. These fields record caller-supplied provenance;
IntentBond cannot establish its independence or the correctness of an interpretation.

`accepted` contains one or more legal JSON outcomes. Normalize reference and
observed outputs according to the maintained contract, allowing legal format
variations. Comparison uses canonical JSON, not Python's coercive equality.
Qualify the reference against valid alternatives and invalid outputs: an overly
restrictive label can still reject valid behavior.

An observation is `{"id":"unicode-blank","status":"returned","value":...}`
or `{"id":"unicode-blank","status":"candidate_exception","error":"..."}`.
Candidate exceptions are counterexamples. Checker errors, timeout, missing or
duplicate observations are unresolved. Keep expected labels and references
outside the evaluated program's environment. Observers must leave source intact;
disable Python bytecode writes or observe a disposable/read-only copy.

Proposals have exactly `targets` (requirement IDs from failed cases), `reason`
(text), and `files` (repository-relative path to complete replacement text).
Authority must match the policy's path, function and requirement links. There
are no deletion or arbitrary-file write operations. The adapter must not change
the worktree itself.

## Completion and retained evidence

Adapter and reference input pins are checked by streaming their complete contents
through SHA-256 at every existing verification boundary, including before and after
each external command. File size and timestamps do not substitute for content
verification. This bounds hashing memory for large runner binaries; it does not
cache digests, omit inputs or change the caller's responsibility for trusted
adapters and execution isolation. At most two adapter/reference files are hashed
concurrently. Results and errors are checked in declared input order, and all
pending reads finish before the check returns or an external command can start.

The run checks the original candidate and baseline preservation, generates cases,
installs one immutable regression scaffold and retains all cases in its data file.
Each cycle observes every accumulated case and reruns native checks. Old selected
checks must keep passing; new regression failures can drive repair. Accepted
proposals are applied only in the output copy.

After initial cases pass, one adversarial batch is added and retained. At most
two repairs are allowed across both stages. The shared time budget is at most
600 seconds; command timeouts use its remainder. Snapshot/final evidence
bookkeeping may finish after the deadline, but expiration cannot produce a
passing loop. The case limit is at most 1000.

Completion requires passing cases, native checks, preservation and new named
regression executions, followed by native source/evidence verification.
`loop_status` remains separate from native `status`:

| Exit | Status | Meaning |
| --- | --- | --- |
| 0 | `passed` | Loop and native checks pass; no native review gate raised |
| 4 | `review_required` | Loop passes; native semantic review remains pending |
| 1 | `rejected` | Scope/preservation/check failure or exhausted repair attempts |
| 5 | `unresolved` | Unknown labels, adapter/checker error, changed pins or timeout |
| 2 | input error | Invalid initial configuration or unable to initialize output |

`result.json`, `commands.json`, `cases.json`, proposals, before/after copies,
native evidence and adapter logs stay outside the repository. `work/` is the
reviewable Git copy; `frozen/` is its final snapshot. Failures retain their partial
candidate too: inspect status before using it. The original source is checked for
agreement and is never an apply/commit target. Applying a reviewed result back to
the project is a separate caller action.

## Trust and limits

This workflow is not an operating-system sandbox. Adapters, regression scaffolds
and configured native tests execute with caller permissions, as ordinary
IntentBond tests do. Use external isolation for untrusted programs. Pin all
relevant adapter/reference dependencies and protect the execution environment.
Hashes detect declared input changes between phases; they cannot defend against
malicious same-user processes rewriting and restoring files or dishonest checks.

Counterexamples identify obligations to investigate, not causal proof. Finite
search and regressions do not establish universal correctness, independent review
or measured advantage over an ordinary coding agent. The command never creates
semantic review or assurance approval.
