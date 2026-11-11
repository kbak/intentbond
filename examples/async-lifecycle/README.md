# Opt-in async lifecycle repair example

This self-contained form fixture demonstrates the existing bounded repair API.
It catches a stale-response bug that 618 retained tests miss, adds 136 interleaved
lifecycle cases, and retains all 754 cases after a localized repair. It also
accepts a different correct implementation using unique request tokens.

The offline demo uses a deterministic demonstration actor. The optional
[coding-agent command](#use-a-coding-agent) replaces proposal production with a
caller-supplied command. Neither enables repair for ordinary commands or provides
an oracle for arbitrary apps.
It is included in the source checkout and source distribution, not the runtime wheel.

## Run offline

Prerequisites: Python 3.11+, an installed IntentBond package with its runtime
dependencies, Git, Java 17+, and the pinned OpenFastTrace 4.9.0 JAR. Provision
these beforehand using the repository's [setup instructions](../../CONTRIBUTING.md#development-setup).
The command below performs no downloads or network/model calls. It works from
any current directory; substitute the location of the checkout or extracted sdist:

```sh
python -B /path/to/intentbond/examples/async-lifecycle/demo.py \
  --oft-jar /path/to/openfasttrace-4.9.0.jar \
  --out /tmp/async-lifecycle-run-1
```

The output directory must be new and outside the checkout. `--oft-jar` may be
omitted when the JAR is at its normal cache path or `INTENTBOND_OFT_JAR` is set.
No historical experiment directory, absolute workstation path, pytest, Hypothesis,
or model credential is needed. Do not use Python's `-O`: qualification assertions
must remain active. Run `--references-only` for a quick check of the generators,
both reference models and retained outcomes without executing candidates.

The fixture and its tests are trusted example code. The subprocess observer
separates candidate imports from reference calculations and disables bytecode
writes; it is not an OS sandbox. Use external filesystem/network isolation for
untrusted candidates. No isolation or offline claim is inferred merely from a
successful subprocess exit.

## What the command checks

1. Verify retention hashes, both reference models, 544 wrong-output controls,
   nine malformed schedules, and independently enumerated schedule bounds.
2. Copy the fixture to three new local Git repositories: original, counter reset,
   and unique-token implementation. Ordinary `check` and `verify` pass their five
   existing check identities without generating cases or invoking repair.
3. Add the same 136 tests directly, without a repair controller. This
   ordinary-plus-retention control rejects counter reset and accepts both correct
   implementations. The faulty implementation fails ten traces of one known bug.
4. Prepare guard plans from the frozen native evidence and run 12 API controls.
   The counter-removal and unique-token repairs each need one proposal; healthy
   sources need none. Signature, protected-file, old-test and requirement edits
   are rejected before application. A no-progress proposal exhausts two attempts.
   Conflicting labels, unavailable labels and unavailable observations stay unresolved.
5. Check that both exact counterexamples fail the new native test before repair,
   that all old named checks keep passing, and that the final retained data and
   scaffold match the selected profile. Verify outside-body bytes, an independent
   AST comparison, additive links, preserved requirements and source/evidence agreement.

The command returns zero only when all those expected outcomes hold, including
the intentional rejection/unresolved controls. Inspect `results.json` and
`api/*/qualification.json`; do not interpret the process exit as approving every
candidate. Successful repair results remain `review_required`, with verification
`matched`. The five old check identities plus the new
`utest~d11-async-lifecycle~1` represent six test methods containing 754 case records,
not 754 requirements or independent fault discoveries.

`api/repair/repair/` retains the exact failures, proposal, before/after sources,
all generated cases, native evidence and final `frozen/` candidate. The original
fixture and copied baseline sources remain unchanged. Applying an output to an
application is a separate reviewed action.

## Contract and finite coverage

The fixture's [maintained requirements](fixture/requirements.md) preserve the
`display_name` wire field, original submitted values, Unicode nonblank rule and
`Continue` label. Only the most recently started validation may set error/pending.
The observer checks these values after every start and completion without reading
the implementation's serial counter.

The retained counterexample is:

```text
start A (empty), start B (Ada), complete B,
start C (李雷), complete A, complete C
```

Resetting the generation after B lets C reuse A's identity. A incorrectly sets
the error and clears pending while C is outstanding. `regressions.json` also
retains the converse-validity trace and its exact expected states.

The versioned `d11-async-lifecycle-v1` generator enumerates all well-formed
schedules of one, two and three requests with fixed ordinal start order: 1, 3
and 15 schedules. Every assignment from `""` and `"Ada"` gives 134 cases; the two
exact regressions bring this to 136. Four initial cases precede the repair and
132 adversarial cases follow it. Each API run allows at most two proposals,
60 seconds and 1,000 generated cases; the example retains 754 cases in total.

An incremental latest-started model and a separate prefix-history model agree
on labels. String validity is checked separately using stripping and Unicode
categories. This does not prove oracle correctness or universal application
behavior. More than three requests, arbitrary strings, cancellation, timeout,
failed requests and malformed responses are not exhaustively covered or assigned
new semantics. The old 618 cases retain wider whitespace/name coverage; for
example, they still reject an unwanted restriction on nonblank control characters.

## Reuse and provenance

`adapter.py` implements the five phases in the [repair protocol](../../docs/repair.md).
`demo.py` constructs and pins the guard and repair policy outside each candidate.
Only `Form.validate` is editable. Requirements, old tests/case data and other
implementation files are preserved. Native semantic review is retained.

For another app, supply its accepted requirements, observation boundary, legal
input domain and independently checked labels. Replace the application-specific
imports in `observer.py` and the demonstration actor in `lifecycle.py`, and qualify
the regression scaffold against a real failure and a legal alternative. Declare
the new function boundary and protected paths explicitly. Do not reuse this
fixture's field names or response assumptions as an inferred application contract.

The old 618 cases and new 136 cases keep their original IDs, kinds, inputs,
requirement mappings and accepted outcomes. `retention.json` pins canonical
digests excluding label metadata. Only provenance paths were relocated to bundled
reference files; both models recheck all outcomes before execution. Formatting
of fixture source was normalized for this repository. Historical studies remain
unchanged. No recorded execution logs or machine-local evidence are shipped.

Ordinary-plus-retention obtains the same detection power from identical tests.
This example demonstrates retention and bounded repair orchestration, not a
measured accuracy advantage over an ordinary coding model.

## Use a coding agent

`agent_demo.py` reuses this profile and its regression data with a coding agent.
Like the qualified development runner, `agent_adapter.py` supplies lifecycle
instructions to the shared [command bridge](../agent_bridge.py), which gives the
agent a separate copy and converts its complete source delta into a proposal. The
[reservation profile](../reservation) uses the same bridge with D4's rollback and
idempotency checks and its own edit boundary. Only
proposal production changes; generation, both reference models, observation,
regression scaffolding, body boundaries and native checks stay the same.

Create a trusted configuration outside the run output. Commands are argument
arrays, without shell interpolation. Use absolute paths and pin the wrapper and
its relevant local dependencies; the runtime environment remains caller trusted.

```json
{
  "command": ["/path/to/python", "-B", "/trusted/my_agent.py"],
  "inputs": {"/trusted/my_agent.py": "REPLACE_WITH_SHA256"},
  "seconds": 120
}
```

The bridge appends two absolute paths, `request.json` and `response.json`, and
runs the command with its current directory set to the agent workspace. The
request contains `schema_version: 1`, `worktree`, a `prompt` file path, the original
`source_sha256`, `round`, and `remaining_seconds`. The prompt includes concrete
failures and the instruction to preserve all accepted requirements. The wrapper
must pass this prompt to its coding agent, allow edits only in `worktree`, enforce
its own model/token/tool allowances, and finish within the supplied wall budget.

After a completed agent turn, the wrapper writes:

```json
{"status": "completed", "source_sha256": "COPY_FROM_REQUEST"}
```

Incomplete/refused turns must not claim completion. Additional usage fields may
be retained in this response, but the portable bridge does not validate provider
token accounting. Credentials stay in the wrapper's external environment; do not
put them in configuration arguments, prompts or source files.

```sh
python -B /path/to/intentbond/examples/async-lifecycle/agent_demo.py \
  --agent-config /trusted/agent.json \
  --oft-jar /path/to/openfasttrace-4.9.0.jar \
  --seconds 240 --out /tmp/async-agent-run-1
```

This starts the counter-reset fixture. `--variant original` and `--variant
unique-token` are healthy controls that complete without invoking an agent.
The shared repair budget covers at most two proposals plus the adversarial pass;
the baseline/reference qualification happens before that budget. Choose a wrapper
with an aggregate budget when provider usage must be bounded across both turns.
The bridge caps each invocation by the remaining repair time and kills its process
group after exit or timeout. A wrapper must not leave separately detached workers.

Unexpected file changes are returned to the native guard, including requirement
and old-test edits. Deletions, executable-mode changes and symbolic links cannot
be represented by this text-proposal API and stop as unresolved. Only Git metadata,
Python bytecode directories and the fixture's `test-results.xml` operational report
are omitted from the delta. Partial, stale, malformed or failed command results
cannot produce a successful proposal. An unchanged proposal remains rejected.
The operational report exclusion comes from the trusted profile. The shared
bridge and all profile dependencies are pinned by the repair policy; an agent
response cannot select instructions, exclusions or a different edit boundary.

Inspect `result.json`, `repair/repair-*/proposal.json` and
`repair/adapter-*-propose/agent/` for prompts, command logs, responses, complete
agent workspaces and deltas. Successful results normally exit 4 with
`review_required`; exit 1 rejects and exit 5 remains unresolved. The original
source is never an apply target. The command bridge is not an OS sandbox: arrange
external isolation for agent tools and untrusted code, as in the offline demo.
