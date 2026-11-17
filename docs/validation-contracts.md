# Python validation contracts

IntentBond can generate finite, reviewable acceptance tests from an explicitly
reviewed contract for a synchronous Python validator. This is an opt-in library
API. It does not change `ib check`, guard, comparison or repair defaults.

Use this when new requirements need expected answers independent of the current
implementation. The caller translates the requirements into the contract and
reviews that translation. The generator does not infer requirements from prose,
inspect the target implementation, or assume the baseline is correct.

## Review a contract

This example describes a function taking one JSON-valued argument. It accepts a
closed object, supplies missing defaults, returns the normalized object and raises
`ValueError` (including subclasses) for invalid input. It preserves its input on
both success and rejection. Error wording and dictionary order are unconstrained.

```json
{
  "schema_version": 1,
  "requirement": "req~service-retry-settings~1",
  "preserve_input": true,
  "output": "normalized",
  "rejection": "ValueError",
  "input": {
    "type": "object",
    "nullable": false,
    "properties": {
      "retries": {
        "required": false,
        "default": 3,
        "schema": {
          "type": "integer",
          "nullable": true,
          "min": 0,
          "max": 5
        }
      },
      "enabled": {
        "required": false,
        "default": true,
        "schema": {"type": "boolean", "nullable": false}
      }
    }
  }
}
```

The requirement reference must name the caller's maintained requirement. Review
the allowed and forbidden values, absence versus explicit null, defaults, return
shape and preservation before approving the contract. Record its SHA-256 digest
separately after that review. A matching digest binds bytes; it does not certify
semantic correctness. There is no self-authorizing `approved` flag.

## Generate and run tests

```python
from pathlib import Path
from intentbond.validation_contract import generate_validation_cases, render_validation_tests

# Supply the digest accepted during review, not a new digest of unreviewed input.
reviewed_sha256 = "<64 lowercase hexadecimal characters>"
cases = generate_validation_cases("validation.json", reviewed_sha256)
source = render_validation_tests(
    "validation.json", reviewed_sha256,
    module="service.settings", function="validate_retry_settings",
)
Path("test_retry_contract.py").write_text(source, encoding="utf-8")
```

Review the returned cases and generated source before retaining them in your
project. Each case records its input, expected acceptance or rejection, normalized
output when applicable, and the boundary being exercised. Generated tests use
`unittest` and IntentBond's assertion helper; both IntentBond and the target module
must be importable in the caller's test environment. Each test carries the declared
requirement reference. Those links do not establish that the tests ran or that the
requirements are complete.

Generation neither imports the target nor executes any candidate code. Running
the generated tests executes trusted caller code in the caller's environment,
without a security sandbox or built-in execution timeout. Use the existing runner
and its budgets for execution. An interrupted run remains incomplete. Generation
never grants semantic approval, authorizes a repair, or increases runner budgets.

## Supported semantics

This format is a small IntentBond contract, **not JSON Schema**. Every node requires
an explicit `type` and boolean `nullable`.

| Type | Required fields and meaning |
| --- | --- |
| `integer` | Inclusive `min` and `max`; Python booleans and floats are rejected. Bounds must be integers between minus and plus one billion. |
| `boolean` | Strict Python boolean; integers are rejected. |
| `string` | `min_length` and `max_length` in Python Unicode code points, bounded by 256; maximum must be positive. Optional `alphabet` and `initial` must both be nonempty sets of distinct printable ASCII characters, with initial characters a subset of the alphabet. Without them, Unicode characters are allowed. |
| `object` | `properties` with 1–16 named fields. Each field has boolean `required` and a `schema`. Optional fields may declare a `default`; without one, absent fields stay absent. Unknown fields are rejected. Defaults are recursively normalized and apply only to absence, never explicit null. |
| `map` | `keys` is a non-null string schema; `values` is any supported schema. Empty maps are accepted. Entry counts are unconstrained. |

`output` must be `normalized`, and `rejection` must be `ValueError`. A normalized
result preserves supplied values and adds only declared defaults recursively.
`preserve_input: false` explicitly permits input changes. Output aliasing and
dictionary order are not constrained. Equality is type-sensitive, so `true`, `1`
and `1.0` are distinct. Unexpected exceptions and asynchronous results cannot
pass the tests.

Unknown fields, regular expressions, arrays, unions, cross-field predicates,
custom exceptions and arbitrary effects are unsupported and refused. Required
fields cannot also declare defaults. Invalid defaults are refused. Do not weaken
or omit a requirement merely to fit this format; retain separate checks for
unsupported obligations.

## Bounds and evidence limits

The generator samples types, empty values, inclusive endpoints and adjacent
values, string lengths and character restrictions, missing/defaulted fields,
unknown object fields, and nested map keys and values. Nullable siblings and
mixed null/non-null map entries exercise validation bypasses. This is a finite
boundary suite, not exhaustive combinations or a proof. A case's schema path
identifies the sampled location, not the cause of a later failure.

Contracts are limited to 64 KiB, nesting depth five below the root, and 64 schema
nodes. Generation defaults to 512 distinct cases; an explicit `max_cases` can
select up to 1,024. Traversal is also bounded. If a limit would omit generated
cases, generation fails without returning a partial suite. It never silently
relaxes the contract to fit a cap. These bounds concern this API; existing model,
tool and execution budgets remain the caller's responsibility.

Qualification must include independent valid implementations and regression
controls, not just agreement with this module's interpreter. Incorrect reviewed
semantics can still produce incorrect tests. The initial offline qualification
supports the declared subset; it establishes no general advantage over an agent
using the same generator and no automatic translation of human intent.

See [the specification](spec.md#generate-finite-tests-from-reviewed-validation-contracts)
for the maintained promises and [Python comparison](python-comparison.md) for
preservation against an explicitly accepted baseline.

## Use generated cases in bounded repair

`prepare_validation_repair` supplies an opt-in adapter for the existing
[repair API](repair.md). It freezes cases once from the reviewed contract and
provides observations and a retained regression scaffold. It does not execute
the candidate, choose a model, invoke repair or change any default.

```python
from intentbond.validation_repair import prepare_validation_repair

adapter = prepare_validation_repair(
    contract_path, reviewed_sha256,
    module="service.settings", function="validate_retry_settings",
    proposer=trusted_proposal_command,
    out=external_preparation_directory,
    max_cases=existing_policy["limits"]["cases"],
)
existing_policy["adapter"] = adapter
```

`trusted_proposal_command` has the same `command` and `inputs` shape as a repair
adapter. Supply an absolute executable and pinned entry point/dependencies. It
handles only `propose`: the existing request contains attributed failures,
including each case's `input.value`, accepted outcome and observed outcome. It
writes the ordinary source-bound proposal response. Preparation never runs it.
The adapter replaces its process with this command, so the existing runner owns
the same deadline and process group. No extra actor attempt or budget is added.

Keep preparation output, the original reviewed contract, proposer and installed
IntentBond runtime outside candidate source and repair output. The returned input
pins cover them; include all other actor dependencies in its supplied inputs.
Pin the resulting repair policy through the normal workflow. The adapter supports
one contract requirement, which must be selected and preserved by the guard.
Other preservation obligations and old checks remain in the guard. It uses the
unchanged explicit edit boundaries; it grants no additional authority.

Select one new regression check identity and sibling test/data paths. The test
file must be discoverable by the project's existing native test command. The
scaffold reads retained case data on every run and adds execution links without
replacing old links. The target module must import from the candidate worktree;
run the adapter in its normal fresh subprocess, with IntentBond available in the
trusted test environment.

All but one generated rejection case form the initial batch, with positive
controls retained. The last reserved case is supplied at the existing second
generation stage. This satisfies the native protocol without duplicate cases or
more generation; it is a frozen boundary check, not adaptive adversarial search.
All cases must pass and remain in the retained data before the loop completes.
Changed batches, insufficient capacity and changed pinned inputs are refused.

Expected outcomes come from the reviewed contract, including changed requirements
that the previous implementation does not satisfy. Observations distinguish
declared rejection, accepted values, unexpected exceptions and input mutation.
Asynchronous results and interrupted commands remain unresolved. Legitimate error
wording, validation order and output copying remain unconstrained.

Preparation and contract review are separate from repair execution. The caller
keeps its existing case, time, repair, tool and provider budgets; preparation does
not enlarge them. Native source checks, old tests, edit restrictions and semantic
review still govern acceptance. The adapter is for trusted code and adds no OS
sandbox. Ordinary Astra can use the same adapter; its availability alone does not
establish a comparative gain.
