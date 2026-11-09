---
name: property-testing
description: Discover and review behavioral properties in specifications, then add and maintain authorized property tests using the project's existing library and runner.
---

A property is a rule intended to hold across a defined set of inputs or states.
An executable property test searches for violations using generated inputs.

For authoring or reviewing selected behavioral statements, use the shared
[translation guidance](references/formalization.md). It owns clause preservation,
omission/overrestriction checks and evolution review. Use the section needed for
the task; supplied inline guidance needs no second lookup.

When documenting an existing project's requirements with `ib recover`, identify
existing tests, proposed properties, input domains, and missing checks in the
feature table or claim notes. Preserve tests, generators, dependencies and runner
configuration during that documentation step. Add or change tests once the starting
requirements are reviewed and the task authorizes test work; passing documentation
checks do not approve inferred intent. Keep authored analysis beside the maintained
requirements, using the existing [document roles](../intentbond/references/requirements.md).
Native tests, models, proofs and results remain linked artifacts, not a parallel
authored specification or property catalog.

## Discover and review properties

Use this pass when establishing a specification, identifying missing properties,
or reviewing a substantive semantic change. Scale depth to the requested scope;
ordinary edits do not require an exhaustive verification plan.

Start with guarantees supported by user outcomes, documented contracts or
applicable normative sources, then compare implementation behavior. Record an
unavailable source or disputed interpretation as unresolved. Identify the relevant
entry paths, configurations, producers and consumers, including failure paths.
Distinguish inspected behavior from merely cited files; retain uncovered in-scope
work with a next step rather than implying that links or property counts close it.

For each selected obligation, make the following concrete beside its existing ID:

- **Observable meaning:** define the state, inputs, outcomes, quantifiers and
  observation point. Define load-bearing terms such as valid, authorized or
  completed. Keep a logical statement and its prose equivalent in scope. Account
  for machine arithmetic, conversions and sequences where they affect the promise.
- **Boundary evidence:** identify what justifies granting authority, trusting a
  result or completing a phase. Enumerate relevant success, pending, partial,
  refusal and failure outcomes and each caller's handling. An empty eligible set
  or an absence of errors does not by itself establish the caller's completion
  condition.
- **Retained assumptions:** across callbacks, retries, replacement or asynchronous
  work, identify the identity, generation, configuration or authorization retained,
  what can change, and what must hold when it is used again. Express accepted
  boundary invariants as properties; a table-only concern remains a gap.
- **Nonvacuity:** give a concrete violating trace or counterimplementation and a
  permitted behavior. Require successful behavior under justified conditions so
  reject-all cannot satisfy the functional specification. Cover effects before
  failure as well as successful returns; do not assume away feasible violations.
- **Composition:** distinguish environmental/cryptographic premises, external
  dependency contracts and in-scope claims needing proof. Name the producers and
  consumers of the latter. Resolve circular dependencies with a joint invariant
  or induction; trusting a dependency does not prove its callers meet its contract.

Try to construct a system failure while all selected component properties hold.
Use the resulting trace to repair the statement or expose a missing obligation.
Classify a hypothetical counterimplementation, observed behavior, disputed
requirement and validated defect separately. A proposed check is not execution
evidence; record actual methods, results and limits independently of approval.
Lean-style notation is optional, and a statement with a proof placeholder is not
a proof. Maintain these notes in the specification; preserve tool-managed recovery
records and their citations without turning them into a second authored contract.

## Implement and maintain checks

Improve the maintained test suite for the selected behavior. Start from approved
requirements and their linked implementation; inferred behavior is a proposed
property until its intended meaning is established. Reuse existing test libraries,
requirements, IDs, and fixtures. Add a separate property item only when it expresses
a useful refinement, not a duplicate requirement. Ordinary example tests remain useful.

To improve the test suite, start with missing checks identified in the requirements
or review. When behavior changes, follow the affected requirements and code to
existing properties. Update assertions, generators, and assumptions, and add
checks for new requirements or uncovered behavior. Follow the translation guidance's
[evolution check](references/formalization.md#preserve-meaning-through-evolution);
preserve identities for surviving promises and retain deferred checks/counterexamples
in the maintained documentation/tests.

Link an executable assertion to the selected obligation. Explain its scope and
assumptions in the maintained prose, following
[requirement authoring](../intentbond/references/requirements.md#author-requirements-and-design)
when a statement needs clarification. Optional **Domain**, **Assumptions** and
**Logical statement** labels are Markdown conventions, not machine-checked fields.
Keep caller/environment assumptions separate from guarantees and generator limits
separate from promised domains. Stronger preconditions, narrower domains and weaker
guarantees are requirement changes subject to normal review. Derive checks from
the complete statement; translation review identifies what remains unchecked.

Exercise the actual implementation. Specify generators for relevant boundaries,
invalid inputs, and operation sequences; generated valid inputs must not silently exclude promised
behavior. Pair safety constraints with required successful behavior where relevant.
Check that the premises admit cases and the assertion constrains the implementation,
including the caller obligations identified above. An independently correct helper
does not establish that every path invokes it or preserves its result.

Use the existing runner and library. When framework-specific guidance is needed,
read only the applicable guide:
[Hypothesis](references/python.md), [fast-check](references/typescript.md),
[QuickCheck](references/haskell.md), or [Hegel](references/hegel.md).
For Daml contracts, read the [Daml guide](references/daml.md); Haskell's
QuickCheck is not a drop-in Daml dependency.
The assertion framework determines the guide, not a wrapper script's language.
Existing example tests or native proof checks do not require introducing a
property-testing library.
If an adapter supplied this text without the references, read the matching installed
file with `importlib.resources.files("intentbond")` under
`skills/property-testing/references/`. No new agent service is needed.

Distinguish an implementation defect from a wrong assertion, invalid generated
input, or harness failure. Preserve the failing example before repair. Changes to
approved properties, exclusions, generators, budgets, skips, or assumptions belong
in the existing review; do not narrow them merely to obtain a pass. Use a targeted
known defect or deliberate mutation when useful to check assertion sensitivity.

Run committed tests without an LLM. Keep native replay details and turn useful
minimal failures into regression examples. Report the checked revision, method,
scope, result, and limits through the existing test/evidence flow. A property-test
pass describes a search, not a proof. Missing tests, excessive discards, timeouts,
and harness errors must remain visible. One property can exercise many inputs;
do not count those inputs as distinct requirements or proofs.

Humans can follow this same procedure without an agent. With OFT, preserve exact
requirement/test IDs and revisions and the project's existing coverage chain.
Keep property identity independent of the checking method so later runtime,
differential, schema-based, or symbolic checks can target the same obligation.
Use a formal tool's native language when needed, linking its model or predicate
to the property ID and revision and retaining assumptions, bounds, and tool version.
Shared IDs do not establish semantic equivalence. Review the translation and the
model's relationship to the implementation; never assume the guarantee merely to
make a model check pass.

For an authorized Alloy or Z3 modeling task, use the sibling
[model-checking skill](../model-checking/SKILL.md). During recovery, identify useful
model candidates in the existing property notes; its executable authoring and
replay steps apply when the task includes that work.
