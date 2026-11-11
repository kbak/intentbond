# Optional bounded repair

`ib repair run` adds counterexample search and local repair to a caller-pinned
[change guard](change-guard.md). Ordinary `check`, `verify`, recovery and guard
commands do not invoke it. This first profile supports Python function bodies,
JSON cases and native JUnit execution links. The runtime selects no model service,
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
adapters and execution isolation.

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
