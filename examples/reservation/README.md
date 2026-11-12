# Opt-in reservation repair profile

This example uses the same [caller-command bridge](../agent_bridge.py) as the
[async lifecycle profile](../async-lifecycle#use-a-coding-agent). The bridge copies
the workspace, invokes the caller's command and submits its complete source delta.
This profile supplies the reservation contract, independent references, observer,
retained tests and `Service.batch` edit boundary. It introduces no default adapter.

The fixture contains a shallow-copy bug: a failed batch can leak changes through
the shared active-reservation and idempotency-history dictionaries. For capacity 2,
batch `[(a, 1), (b, 3)]` must fail without storing either key; reserving `(a, 2)`
afterward must succeed. A repair must also preserve cancelled-key replay without
reactivation, conflicting-quantity rejection, capacity reuse, cancellation,
successful batches and empty batches. See the [requirements](fixture/requirements.md).

## Run

Use Python 3.11+, installed IntentBond runtime dependencies, Git, Java 17+ and a
previously provisioned OpenFastTrace 4.9.0 JAR. The checkout and source distribution
contain both profiles and the shared bridge; the runtime wheel does not.

Provide the same trusted external agent configuration described by the
[lifecycle command contract](../async-lifecycle#use-a-coding-agent): absolute argv,
SHA-256 pins for the wrapper and dependencies, and a per-command time limit. The
wrapper receives request/response paths, reads the profile's prompt, edits only
the separate workspace, and returns a completed, source-matched response. A local
deterministic wrapper works for offline testing. A model wrapper controls its own
provider, credentials, token/tool budgets and network use.

```sh
python -B /path/to/intentbond/examples/reservation/agent_demo.py \
  --agent-config /trusted/agent.json \
  --oft-jar /path/to/openfasttrace-4.9.0.jar \
  --seconds 240 --out /tmp/reservation-agent-run-1
```

The output directory must be new and outside the checkout; keep the configuration
outside that output. The default `shallow-copy` variant requires repair.
`--variant deep-copy` is a healthy control requiring no proposal. Qualification
assertions require Python without `-O`. The repair budget permits at most two
proposals, one adversarial batch and 1,000 cases; reference and baseline checks
precede that budget. Default `check` and `verify` do not invoke the agent or repair.

## Cases and boundaries

The profile reuses D4's 17 initial and 510 adversarial traces, preserving their
IDs, inputs, requirement mappings, kinds and accepted outcomes. A D2 event-log
model and the separate D4 transition checker agree on all 527 labels. Six
hand-written invalid-output controls reject partial rollback, lost history,
reactivation and rejection of an empty batch. `retention.json` preserves the
exact seven rollback and eleven idempotency regression records from D4, with
overlap between the two sets. Both historical test identities remain in the
new scaffold; the full generated cases are now retained as JSON as well.

The observer compares every operation's response and complete active/history
state. It runs separately from the reference models. The retained scaffold runs
in the fixture's ordinary native suite without importing a reference model or
accessing any historical research directory. Fixture source formatting is
normalized; the D4 generator and checker retain their behavior.

Only the body of `Service.batch` in `service.py` may change. The signature,
`reserve`, `cancel`, other modules, requirements, old tests and runner stay intact.
The bridge pins this profile and its shared implementation. It forwards collateral
edits for native rejection; deletions, mode/link changes, partial or stale command
results remain unresolved. The trusted profile excludes only `test-results.xml`
as an operational report, in addition to the bridge's Git/bytecode exclusions.
Report exclusions are never selected by the candidate or agent response.

Inspect `result.json` and `repair/` for failures, retained cases, proposals, copied
workspaces, native evidence and source verification. Successful repairs normally
exit 4 (`review_required`); rejected repairs exit 1 and unresolved runs exit 5.
The original fixture remains unchanged. Applying a reviewed result is a separate
action. OS isolation is external: subprocess separation is not a sandbox.

These are finite in-memory reservation traces, not database transactions, HTTP
services, concurrency or crash recovery. The two references can share an omission.
The reusable part is the command transport and repair orchestration, not an oracle
for arbitrary applications. The example establishes no model-accuracy advantage;
ordinary execution of the same retained tests has the same detection power.

### Check completion of a new request

For a maintenance request against working code, optionally pass
`--completion-config /trusted/completion.json` to `agent_demo.py`, or supply
`completion=...` to its Python API. This pins an external request and checker and
feeds a missed request into the same bounded local repair path. All preservation
checks still apply; native review remains separate. Omission keeps the existing
behavior. See the [completion protocol](../../docs/repair.md#optional-requested-change-completion)
for the shared checker covering the two example maintenance requests, policy
fields, exact source binding and limits.
