# Preserve requirements during a change

The optional change guard checks a candidate against the caller's accepted change:
which existing requirements may change or disappear, which files must be retained,
and which existing regression checks must still pass. It reuses `ib check` evidence,
OFT declarations and execution links. It runs no agent, model or project tests.

Maintained requirement documents remain authoritative. The declaration contains
references and change permissions, not another copy of the specification.

## Prepare before editing

Reuse a check bundle containing the accepted baseline, or create one with base
equal to candidate. Enable the existing [execution-link profile](../intentbond/skills/intentbond/references/execution-links.md)
and name the retained test artifacts to obtain individual check observations.
The following example assumes `req~session-expiration~1` and its named check
named `utest~expiration-boundary~1`, with an existing protected `api/` directory.

```sh
BASE=$(git rev-parse HEAD)
ib check --base "$BASE" --candidate "$BASE" --out /tmp/session-baseline
```

Write `/tmp/session-change.json` with the change already authorized by the caller:

```json
{
  "schema_version": 1,
  "requirements": {
    "preserve": ["req~session-expiration~1"],
    "change": [],
    "remove": [],
    "add": []
  },
  "protected_paths": ["api"],
  "checks": ["utest~expiration-boundary~1"],
  "check_support_paths": ["run_tests.py"]
}
```

```sh
ib guard prepare --base "$BASE" \
  --evidence /tmp/session-baseline/evidence.json \
  --declaration /tmp/session-change.json --out /tmp/session-guard
```

Retain the printed `plan_sha256` in caller-controlled task or CI state. Pass that
exact value later; **do not recompute it from a candidate-modified plan**. The plan
and declaration must be outside the repository and evidence bundle; the output
directory must be new. Use the original external `--scope` on both guard commands
if the check used one. All commands accept an explicit repository root with `--repo`.

All baseline artifacts whose types are selected by `required_coverage` are
preserved by default, including ones omitted from `preserve`. `change` and `remove`
reference exact baseline IDs; `add` references expected new IDs. Actions cannot
overlap by logical identity. Explicit additions are not an allowance to remove
an existing promise. The caller's normal review process authorizes declaration
changes; the guard does not introduce another approval interaction.

`protected_paths` and `check_support_paths` are literal repository-relative files
or directory prefixes, with at least one captured baseline file each. A directory
also protects new files under it. Use actual captured paths, not symlink aliases
for their referents. Include assertion helpers, fixtures and report producers in
support paths when their changes must trigger reassessment. Dependencies are not
discovered automatically.

## Check before handoff

After editing, run the usual check and then the guard:

```sh
ib check --base "$BASE" --out /tmp/session-candidate
ib guard check --plan /tmp/session-guard/plan.json \
  --plan-sha256 CALLER_RETAINED_DIGEST \
  --evidence /tmp/session-candidate/evidence.json
```

`--format json` returns the complete source-bound report; text lists up to ten diagnostics.
`--candidate COMMIT` checks an exported commit instead of the current worktree.
Save the output outside the repository. Prepare/check return exit 2 for invalid
inputs, altered plans or invalid bundles. Prepare exit 0 means the plan was saved.
Check uses exit 0 for passing preservation plus a passing native check, exit 1 for
rejection and exit 4 for unresolved review. `guard_status` reports preservation
separately from `recorded_check_status`; the overall `status` retains native pending
review or failure. None of these results grants semantic approval.

## Worked change and counterexamples

For a requested label change from “Sign in” to “Continue”, keep the API schema and
30-minute session expiry behavior. The regression checks 1799, 1800 and 1801 seconds.

| Candidate | Expected guard observation |
| --- | --- |
| Change the label; refactor expiry from `seconds >= 1800` to `not seconds < 1800` | Preservation passes with unchanged passing regression evidence. |
| Also rename the API field in `api/schema.json` | `protected_path_changed`, even if tests pass. |
| Delete the expiry requirement | `requirement_missing`; a missing declaration does not erase the plan's obligation. |
| Change expiry to `seconds > 1800`; new feature tests pass | `check_unresolved` with a failed retained boundary check. |
| Also replace the 1800-second assertion with `assert True` | `check_source_changed` requires reassessment despite a passing test. |
| Skip/delete the old test or stop reporting its identity | Unresolved check plus changed source; suite success cannot substitute. |
| Keep the requirement but select no executed check linked to it | `requirement_unchecked`, requiring review. |
| Explicitly declare a separate obsolete requirement's removal | Removal is reported as authorized; native specification/test review remains pending. |

These controls are executable in [test_change_guard.py](../tests/test_change_guard.py).
They use disposable Git repositories, the pinned OFT engine and actual test runs;
they are not a model-comparison benchmark.

A changed requirement's prose or a harmless edit to a retained test file requires
review, not a claim that the change is wrong. Correct implementation refactors can
pass without freezing their source bytes. To change the protected boundary or
selected obligations, the caller prepares a new declaration and retains its new
digest. Changed retained tests require reassessment through the existing review
process; their passing output cannot automatically discharge that reassessment.

The guard cannot detect undocumented requirements, prove assertion equivalence,
or guarantee that a producer honestly reported every case. Its plan and check
evidence are unsigned; caller-controlled storage and policy provide the trust
boundary. It detects stale source and changed records under that boundary. It
does not replace full diff review, `ib verify`, or existing approval gates.
