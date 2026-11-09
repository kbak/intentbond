# IntentBond specification evaluation, protocol v1

This repository-only protocol implements [E01](https://github.com/kbak/intentbond/issues/8)
of the [evaluation roadmap](https://github.com/kbak/intentbond/issues/7).
It freezes the **current IntentBond treatment**, the initial prompts and the
experimental decisions below. It is not a benchmark result or an implemented
evaluation runner. Acceptance of this protocol does not establish that the later
harness has met its qualification requirements.

The files in this directory are evaluation inputs, not additional instructions
for ordinary IntentBond users. Product behavior and packaged skills are unchanged.

## Frozen inputs and subsequent execution locks

- [baseline.json](baseline.json) identifies IntentBond 0.5.0 at
  `e55614cf0898dd98dc8d75795b66ed7764f60f06`, its source archive, distribution
  artifacts, packaged guidance, existing checking policy and observed tooling.
- [experiment.json](experiment.json) records the model, condition identities,
  sampling rules, budgets, analysis and decision thresholds.
- [prompts/common.md](prompts/common.md), [prompts/generic.md](prompts/generic.md)
  and [prompts/intentbond.md](prompts/intentbond.md) are the initial prompt templates.
- [scope.json](scope.json) is the common task-fixture policy to be qualified by E03.
  It is distinct from IntentBond's frozen repository self-check policy.
- [SHA256SUMS](SHA256SUMS) covers these protocol files. Run `sha256sum -c SHA256SUMS`
  from this directory before assembling a run.

E02 must produce an immutable upstream artifact/toolchain lock and explicit task
list. E03 must produce the harness/container/tool-definition lock, qualified
budget controls, rendered prompt hashes and task-fixture hashes. E05 and E08 must
pin the comparator and hybrid implementations and their internal prompts. These
are required **before their respective generation runs**, not invented E01
measurements. Record their hashes in each run manifest alongside this protocol's
commit and file hashes. Missing locks or failed qualification prohibit launch.

The known Codex binary is pinned as a runtime candidate, not certified here as a
budget-enforcing harness. If qualification requires a different client or driver,
record a protocol amendment before any measured generation and apply it to all
matched conditions. Never silently substitute a runtime, model or budget.

## Questions and conditions

The primary question is whether the current complete IntentBond agent workflow
improves specification correctness over the same model with ordinary development
tools. The second question is whether requirement-attributed repair improves that
workflow, and at what cost. Static specification quality and preservation of intent
through changes are different outcomes; E10/E11 cover the latter.

| ID | Treatment | Interpretation |
| --- | --- | --- |
| A: generic | Astra and ordinary shell, file, Git, Lean and test tools | Common agent baseline with ordinary test/repair access. |
| B: intentbond-current | A plus the frozen IntentBond package and existing development/property-testing workflow | Complete current workflow, including trace/check/review use; not a skill excerpt. |
| C: verispecgen | Qualified official implementation or explicitly labeled reproduction, using the same Astra model and ordinary tools | Procedure comparison; report fidelity and departures. |
| D: intentbond-hybrid | B plus the optional, separately pinned E08 repair loop | Incremental value over B. |

Ordinary execution capabilities and task information are equal. The IntentBond
package/workflow and C/D's orchestration are intentional treatment differences.
Do not expose B's skills through global instructions or installed plugins to A/C.
Do not add a requirement-decomposition, oracle-generation or adversarial-repair
algorithm to B's adapter: its existing skills decide how to perform the task.
Record how much of that workflow actually executed. A guidance-only fallback is
a separately named exploratory condition and cannot replace B.

Prespecified comparisons are B−A (primary current-workflow effect), C−A and C−B
(method comparisons), and D−B (incremental transfer). Historical different-model
paper scores are context only. A successful deterministic `ib check` is neither
the primary semantic score nor acceptance of the generated contract.

## Model and runtime controls

Use **`gpt-6-astra`, reasoning effort `xhigh`**, matching the maintainer's normal
configuration. Use standard execution mode where exposed; no model substitution,
delegation, hidden helper model or condition-specific effort. All model calls,
including decomposers, judges, oracle generation and repair, use this setting and
consume the attempt's common budget. Do not copy the paper's temperature setting
to a backend that does not expose it. Leave temperature, top-p and sampling seed
unset and report that limitation; repetitions are independent fresh sessions, not
claimed deterministic samples.

Record the provider/backend route, client version and binary hash, non-secret
effective configuration, model requested/returned, any returned snapshot identity,
tool schemas, supported settings and run times. Never retain authentication
material in the manifest. Record immutable server identity as unavailable when it
is not exposed. A model alias is not an immutable model snapshot.

Interleave conditions within each task/repetition block in deterministic
randomized order. Fresh sessions must not inherit conversations, global skills,
MCP connections, user configuration, memories or artifacts from another attempt.
Use the same qualified sandbox and local dependency image for all conditions;
generated programs have no scoring-data, host-repository or general network
access. Model transport is outside the generated-program environment.

If a later hybrid run uses an alias without a verifiable stable server snapshot,
regenerate A/B/C alongside D in the final wave. Retain the earlier wave as
historical evidence; do not call a cross-wave score difference a paired method
effect. Reusing **the same output for multiple evaluators** is always different
from reusing outputs as a later model control.

The requested model/settings are supported by the observed local model catalog;
[OpenAI's Astra documentation](https://developers.openai.com/api/docs/models/gpt-6-astra)
also lists `xhigh`. Neither observation proves a particular account can execute
the later run. E03 verifies effective settings without silently falling back.

## Tasks, splits and information access

Use the official VERINA SpecGen tasks and their stable IDs, with neither reference
code nor reference pre/postcondition descriptions supplied. E02 pins the exact
dataset/evaluator revision and checks the official few-shot exclusion rule.
Reserve `verina_basic_15` and `verina_basic_44` as the same two few-shot examples
for every condition; they are never scored. If the pinned official configuration
uses a different convention, amend this protocol before generation.

The expected inventory is 189 tasks: 108 basic and 81 advanced. After the two
basic few-shot exclusions, 187 tasks remain. These are expected counts to be
verified in E02, not a claim that E01 audited every task.

Within each stratum, sort IDs by the ascending hexadecimal SHA-256 digest of
UTF-8 `intentbond-verina-v1-split\n` followed by the exact task ID, with task ID as
the tie-breaker. Select the first 14 basic and first 10 advanced tasks as the
24-task development cohort. The other 163 tasks are the initially untouched
evaluation cohort. E02 must write and hash both explicit lists; do not handpick
tasks using model success or failure. If a stratum is too small or IDs/counts do
not match, stop and reconcile the inventory before generation.

E04 runs A/B on 24 development tasks × 3 repetitions = 144 attempts. E05 may run
C on the same development cohort × 3 = 72 attempts. After qualification, E06
runs A/B/C over all 187 eligible tasks × 5 = 2,805 attempts. Report the 163-task
untouched cohort as the primary B−A analysis and all 187 tasks as the official-set
comparison; do not mix the development cohort into an untouched-set claim.

After E06 results are inspected to design D, those tasks are no longer untouched
for D. Report D−B on this benchmark as **adaptive/exploratory**, even when the
comparison is otherwise matched and uses new samples. Do not rename an exposed
test set "held out". Independent confirmation of the adopted workflow requires
E10's separately authored, sealed evolution tasks (or a separately preregistered
new static task set). E10 must freeze its held-out oracles before E11 generation.
No statistical interval erases this reuse limitation.

Generation receives only the public problem description, signature, necessary
type/import auxiliaries and the designated few-shot examples. The harness must
extract these fields before launch; workers must never receive `task.lean` with
reference code/specifications/proofs, `test.json`, `reject_inputs.json`, generated
reference caches, evaluation results, or a mount containing them. Public benchmark
availability creates a possible pretraining-contamination limit even with runtime
isolation; report it, and prohibit retrieval during the run.

All conditions may author and execute their own candidate programs as oracles.
None receives a trusted reference implementation. Record each oracle's source,
hash and disagreements; generated oracle outputs are not automatically user intent.
Respect multiple permitted outputs. Preserve required error behavior instead of
inventing a precondition that excludes it. Evaluation-only reference artifacts
remain in a separate scorer environment, inaccessible through tools or symlinks.

## Common fixture and prompt assembly

E03 prepares the same fresh Git fixture for each condition with `task/input.json`,
`intent.md`, `requirements.md`, Lean signature stubs, a `checks/` directory,
`.gitignore`, the pinned scope and the same two few-shot examples. Record the
baseline commit and complete manifest. The seed intent/requirement text must be
the supplied description without semantic rewriting. Common stubs may declare
the intended trace links, but are visibly unfinished and are not behavioral
evidence. A seed fixture is task scaffolding, not a recovered or accepted software
implementation. Initial tests are incomplete; no fake passing checks are allowed.

The trusted `/opt/evaluation/run_checks.py` adapter is E03 work. It builds the
candidate's own Lean checks and emits fresh JUnit outcomes; it must reject an
empty or unsuccessful suite. It contains no benchmark answers, performs no model
call, and provides no hidden repair guidance. Its hash and container identity are
mandatory launch inputs. The read-only external scope is used for B/D checks so
candidate edits cannot change their own checking policy. Preserve pending semantic
review; an experiment does not manufacture reviewer approval.

Build the initial user message by concatenating common.md, two newlines, the
condition suffix, two newlines, and the task-path notice. Encode UTF-8 with LF
newlines and retain the exact rendered bytes and hashes. The task-path notice is
exactly `Task input: task/input.json\n`. A uses generic.md; B uses intentbond.md.
The latter points to the **frozen package**, never the working repository or this
protocol. C/D must freeze their additional prompts/configuration under E05/E08.
Ordinary agent/system prompts and tool definitions are shared and separately
hashed; record any platform-owned portion that cannot be exported.

Final output is one JSON object with the VERINA GenSpecOutput string fields:
`imports`, `precond_aux`, `precond`, `postcond_aux`, `postcond`. E03 defines a
syntax-only extraction/schema adapter, with no semantic editing, model repair,
best-of-N selection or hidden compiler-fix loop after the attempt ends. Reject
missing/extra fields or non-string values. Reject proof holes, admitted axioms
introduced to make checks pass, changed signatures and attempts to replace the
trusted evaluator under E02's exact qualified policy.

Bind native checks to that same candidate: the trusted driver must verify that
the compiled specification is the canonical rendering of candidate.json. Retain
both hashes. A check of a different predicate is an artifact-mismatch failure,
not evidence for the scored candidate. This consistency check may normalize the
specified serialization only; it cannot correct the candidate's meaning.

## Resource limits and stopping

Every condition uses the limits in experiment.json. Per attempt: 1,048,576 total
input tokens, 131,072 total output tokens (including reported reasoning), 16,384
output tokens per model request, 60 model requests, 240 dispatched tool operations,
25 specification-repair rounds, 60 distinct internally labeled tests, and 1,800
seconds of generation wall time. A Lean/prover operation is limited to 120 seconds.
At most 3 attempts run concurrently. Budget consumption includes decomposition,
oracle generation/execution, judging, initial checks, adversarial checks and repair.
Input usage includes cached tokens; do not add reasoning tokens again when the
backend already includes them in output totals.

Count the initial specification separately from up to 25 repairs. Multiple
specifications generated in one response still consume separate candidate/repair
counts when evaluated for selection. A batched tool request counts each actual
dispatched operation; a bundled test invocation still consumes wall time and the
distinct-test limit. Terminate child processes with the attempt; background work
cannot continue outside its budget. Log actual consumption, concurrency and
resource-limit outcomes. These are ceilings, not expected cost or a commitment
to run every later stage.

Token enforcement is an E03 launch requirement: check input size before a request,
reserve/enforce its maximum output against the remaining attempt/stage budget,
then reconcile actual usage. The inspected Codex CLI did not establish a hard
per-request token cap. Do not simulate one with a prompt or call wall-time limits
token limits. If the selected transport cannot enforce or accurately account for
them, stop qualification and amend the runtime/budget design before generation;
never label an uncapped run token-matched. The amendment requires review through
the normal project workflow, not an undocumented experimental exception.

Stage ceilings are the fixed scheduled attempt count multiplied by each
per-attempt maximum; experiment.json gives the attempt counts and hard concurrency
limit. E09's later wave has at most 3,740 attempts (A/B/C/D, 187 × 5); its three
ablations have at most 216 development attempts (24 × 3 × 3). Ablations disable
attribution/localized feedback, post-success adversarial checks, or preservation
checks one at a time. They are exploratory development-set evidence, not an
additional untouched confirmation. No unregistered additional samples or best-of-N
selection. Stop a stage before exceeding any aggregate reservation or attempt cap.

Finish an attempt when it returns a final candidate, declares it cannot produce
one, or reaches its first resource limit. Score only the last complete candidate
saved before termination; no post-limit repair or evaluator-guided selection.
No candidate is failure, not a dropped row. Permit at most two transport retries
only when the provider confirms the request was not processed; count requests and
elapsed time, and retain the event. Ambiguous delivery or consumption is an
incomplete attempt with unknown usage, not a free retry.

Scoring is outside generation and cannot feed back into it. Apply the same
qualified evaluator limits to every condition/suite: 120 seconds per proof/check,
3,600 seconds total per candidate per suite, and 3 concurrent scoring workers.
Exhaustion or unsupported checking remains unknown/failure in the conservative
primary metric. A different scoring budget is a labeled sensitivity analysis of
the same frozen outputs, never a replacement of the registered result.

## Outcomes and analysis

The primary endpoint is conservative joint SpecGen success: a candidate compiles
and satisfies the pinned official evaluator's required precondition and
postcondition soundness/completeness checks, with **every unknown, error, missing
candidate or incomplete check counted as non-success**. E02 must record the exact
mapping from upstream statuses to this endpoint and qualify it with controls.
Test-based acceptance is not a universal equivalence proof; preserve the native
method/status alongside the normalized outcome.

Report separately:

- compilation/schema/admission rejection;
- precondition and postcondition checks in both directions, including unknowns;
- permitted-example acceptance and forbidden-input/output rejection, with actual
  denominators and missing-outcome counts;
- joint success over **all scheduled attempts**, not only compilable contracts;
- original versus augmented-suite results on the exact same output hash;
- trace/check/execution-link results, review-pending state and observed workflow
  use, separately from semantic quality;
- tokens, model/tool calls, repairs, elapsed/worker time and measured human review
  minutes. Missing cost/effort is null, not zero or inferred from artifact counts.

For a candidate, case-level rejection credit requires the appropriate semantic
predicate to reject the forbidden behavior; exceptions/timeouts are not successful
detection. Use task-macro averages, not a pooled case average that lets large suites
dominate. Give each scheduled attempt equal weight within its task, then each task
equal weight within the analysis cohort. Expose any positive-only/negative-only
task and unsupported case mapping; never fabricate an empty-denominator rate.

For B−A, average repetitions within each task and compute paired task differences.
Use a stratified paired bootstrap: sample task IDs with replacement within basic
and advanced strata, preserve all conditions and repetitions for each selected
task, weight strata by their original cohort sizes, and take the 2.5th/97.5th
percentiles of 10,000 resamples. Fix the PRNG/seed in experiment.json and the
analysis-library version in the execution lock. Repetitions are not independent
task units. Report point differences and 95% intervals even when they include zero.
C comparisons, D−B and ablations are secondary; report their multiplicity/adaptive
limits without turning a favorable exploratory interval into a confirmatory claim.

Do not pool across original/augmented suites, waves or task cohorts. Report
quality against actual cost and budget exhaustion as well as fixed-budget scores.
Reference-control defects found before generation may be globally excluded with
a recorded reason and immutable exclusion list. If a harness/reference defect is
found after outputs exist, retain the as-scheduled accounting, quarantine all
affected condition/task pairs, and show the qualified-cohort analysis separately.
Correcting infrastructure permits consistent rescoring of unchanged outputs;
changing generation requires a new versioned run, retaining the old one.

## Pilot decision and change control

The pilot establishes feasibility and diagnoses tradeoffs; 24 tasks cannot certify
a general quality gain. Proceed to full evaluation only when: every scheduled
attempt has artifacts or an explicit terminal state; leakage and budget controls
pass; at least 98% of scheduled outputs have a valid scorer result or a classified
candidate failure; and no unclassified infrastructure failures remain. A model's
compile error or resource-limit failure is not a harness defect.

Flag a tradeoff if B's development joint success is at least 5 percentage points
below A or its invalid-behavior rejection is at least 5 points lower while
permitted-behavior acceptance rises. This triggers a documented go/no-go analysis,
not automatic exclusion or prompt tuning on the evaluation cohort. A null or
negative effect is a valid full-study outcome. Freeze any development-driven
protocol revision before the first untouched-task generation. Stop and diagnose
any leakage, wrong model/settings, violated budget or scorer-control failure.

For the later adoption decision, require a matched D−B joint improvement of at
least 3 percentage points, no more than a 2-point reduction in either permitted
acceptance or forbidden rejection, and no more than 2× B's median output-token
and worker-time use. These are practical decision thresholds, not claims of
statistical power or universal product guarantees. Static results remain
exploratory after reuse; require independent evolution evidence and review of
observed collateral regressions before adoption. Otherwise revise, reject, or
justify an explicitly scoped tradeoff with evidence in E12.

Record all deviations, who accepted them and whether outputs had been inspected.
Never overwrite the v1 manifest to make a completed run appear compliant. Store
runtime logs, candidate source, raw scores and credentials outside the product
repository; publish only reviewed evidence with hashes and access/retention notes.

## Historical experiments reviewed

Two retained local experiments informed the outcome definitions: an interim
164-task Python postcondition comparison (4 attempts, 3 prompt arms) and a
12-task translation-development comparison (3 attempts, 3 guidance variants).
Both used Astra at medium effort through Codex 0.165.0, a moving server alias and
180-second attempt limits, without verified token caps. They evaluated guidance
projections, not the complete current workflow or VERINA. The first showed that
higher reference-test acceptance could accompany lower conditional mutant
rejection. The second reused development tasks to compare guidance variants.

The historical artifact hashes and guidance identities are in baseline.json.
Those local artifacts are not distributed here; these observations motivate
separate acceptance/rejection metrics and cannot establish an E01 result or serve
as a matched control for the xhigh experiments. Their reported subscription
monetary cost and immutable server snapshot are unavailable.

## Reproduce the frozen package

Use Python 3.12.3, Git 2.43.0 and the exact build dependencies in the frozen
requirements/ci.txt. From an IntentBond clone containing the baseline commit:

```sh
IB_EVAL_BASE=e55614cf0898dd98dc8d75795b66ed7764f60f06
IB_EVAL_BUILD=$(mktemp -d)
git archive --format=tar --output="$IB_EVAL_BUILD/source.tar" "$IB_EVAL_BASE"
mkdir "$IB_EVAL_BUILD/source"
tar -xf "$IB_EVAL_BUILD/source.tar" -C "$IB_EVAL_BUILD/source"
python3 -m venv "$IB_EVAL_BUILD/venv"
"$IB_EVAL_BUILD/venv/bin/python" -m pip install --require-hashes --only-binary=:all: \
  -r "$IB_EVAL_BUILD/source/requirements/ci.txt"
SOURCE_DATE_EPOCH=$(git show -s --format=%ct "$IB_EVAL_BASE") \
  "$IB_EVAL_BUILD/venv/bin/python" -m build --no-isolation \
  --outdir "$IB_EVAL_BUILD/dist" "$IB_EVAL_BUILD/source"
sha256sum "$IB_EVAL_BUILD/source.tar" "$IB_EVAL_BUILD"/dist/*
```

Compare against baseline.json. The deterministic Git archive and wheel-content
digest are portable integrity checks; a distribution byte hash additionally
identifies the exact built file. Record rather than conceal timestamp/metadata
differences in rebuilt sdists. The manifest defines the wheel-content digest as
SHA-256 of UTF-8 JSON (sorted keys, compact separators) mapping every non-directory
ZIP member except `*.dist-info/RECORD` to the SHA-256 of its uncompressed bytes.
The exact artifact hash still covers RECORD and ZIP metadata; the portable
comparison excludes RECORD serialization and archive timestamps.

E01 validates JSON, file/source hashes, packaged guidance and the normal repository
checks. E02/E03 qualify benchmark/toolchain and harness behavior; no new model
generation or benchmark score is produced by this ticket.

## Sources

- [VeriSpecGen paper](https://arxiv.org/html/2604.10392v1), especially Sections 3/5.
- [Project walkthrough](https://spec.verina.io/).
- [VERINA interface and dataset](https://github.com/sunblaze-ucb/verina).
- [VeriScale paper](https://arxiv.org/abs/2605.22368) and
  [released artifacts](https://github.com/XiaoyangLiu-sjtu/VeriScale).
- [IntentBond development contract](../../docs/contract.md),
  [granularity guidance](../../docs/requirement-granularity.md) and
  [translation guidance](../../intentbond/skills/property-testing/references/formalization.md).
