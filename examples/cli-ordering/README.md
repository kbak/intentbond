# Opt-in CLI ordering repair profile

This example ports D3's ordering case to the existing [shared command bridge](../agent_bridge.py).
The five original tests pass a faulty quantity tie breaker. Independently labelled
challenges expose the missing promise: sort names ascending, preserve encounter
order among equal names, and keep every duplicate and quantity. Text, JSON,
streaming and invalid-option contracts remain binding; see the
[fixture requirements](fixture/requirements.md).

## Offline qualification

Use Python 3.11+, installed IntentBond runtime dependencies, Git, Java 17+ and an
already provisioned OpenFastTrace 4.9.0 JAR. Examples ship in the source distribution
and checkout; install the runtime wheel separately. No provider or model is used.

```sh
python -B /path/to/source/examples/cli-ordering/demo.py \
  --oft-jar /path/to/openfasttrace-4.9.0.jar --out /tmp/cli-ordering-run-1
```

The output must be new and outside the checkout. Do not use `-O`: qualification
assertions are required. `--references-only` checks the labels without running a
candidate. The full demo runs the real shared bridge with a deterministic actor,
plus explicit malformed-response injections for reference, observation and path
boundary controls. Each repair run permits 120 seconds, two proposals, one
adversarial batch and at most 1,000 cases; the whole qualification includes many
such controls and baseline checks. Ordinary `check`/`verify` invoke no repair and
leave source unchanged. No proposal is needed for the already-correct control.

Inspect `results.json`, per-control proposals, failures, retained tests, native
evidence and source verification. Successful loops still require semantic review;
scripted qualification does not approve a change to the user's code.

## Use a coding agent

Supply a trusted external configuration following the existing
[caller-command contract](../async-lifecycle#use-a-coding-agent): absolute argv,
SHA-256 pins for the wrapper and dependencies, and a per-command limit. The command
receives request/response paths, reads the prompt and edits its separate workspace.
It must mark partial or unknown outcomes incomplete. Provider, token/tool budgets
and OS/network isolation belong to the caller.

```sh
python -B /path/to/source/examples/cli-ordering/agent_demo.py \
  --agent-config /trusted/agent.json --seconds 240 \
  --oft-jar /path/to/openfasttrace-4.9.0.jar --out /tmp/cli-agent-run-1
```

Keep the configuration outside the output directory. Variants are `tie-breaker`
(default), `stable` (healthy) and `pretty-json` (valid JSON formatting with the
ordering defect). The bridge forwards the entire source delta. Only `ordered`'s
body in `formatters.py` may change; its signature, other functions/modules,
requirements, old tests and runner are protected. Deletions, mode/link changes,
partial/stale/unknown responses remain unresolved. The only profile report
exclusion is `test-results.xml`, alongside the bridge's Git/bytecode exclusions.
Successful CLI runs exit 4 (`review_required`), rejected runs 1 and unresolved runs 5.

## References and retained cases

The D2 stable-insertion reference and independent D3 grouping/invariant checker
agree on 20 initial and 260 adversarial cases. `retention.json` pins their semantic
content, all three formats of the minimal equal-name regression, and the exact
requirements interpretation. Changed requirements require a deliberate profile
revision; missing or conflicting labels never become success. All 280 cases are
retained in executable ordinary tests. Six initial failures expose the original
bug; 51 adversarial failures expose an incomplete first repair, which needs a
second local repair. Reintroducing the bug fails the retained tests.

The observer and retained scaffold use only neutral output parsing. JSON output
is compared semantically, allowing indentation and horizontal whitespace. Text
and error strings stay exact; nonempty JSON/stream output requires its final
newline, and JSON rejects extra trailing blank lines. The demo includes a
body-local proposal that changes JSON rendering through a runtime side effect;
retained tests reject that violation even though the five old tests pass.
Reference/actor modules are outside the copied
candidate inputs. Interpreter separation is not an OS sandbox. Adversarial code
requires caller-provided filesystem/process/network isolation.

This finite profile selects ordering and errors for challenges and preserves all
five accepted requirements through the guard and original tests. It covers bounded
lists and options, not arbitrary CLI behavior or natural-language interpretation.
The two references may share omissions. The same retained tests have the same
detection power when run ordinarily; scripted actors establish no model-quality gain.
