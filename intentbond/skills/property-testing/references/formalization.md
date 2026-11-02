# Translate selected promises

Use this guidance when translating or reviewing selected requirements as logical
statements, executable properties or model assertions. Scope the work to the
selected behavior; ordinary changes do not require formalizing the whole system.

## Preserve the behavioral relationship

Identify the clauses that carry each promise's meaning: how inputs and prior
state determine or constrain outputs, effects and subsequent state. Account for
conditions, branches, quantifiers, ordering, multiplicity and exceptions where
the requirement specifies them. Map each clause to the proposed checks or name
the part left unchecked. A single property can combine several clauses; separate
test identities are useful only when the obligations need to evolve independently.

Shape, range, preservation and metamorphic checks can supplement this relationship
but may leave the main behavior unconstrained. For example, preserving pending
jobs does not establish that the next eligible job was selected in the promised
priority order. Partial checks remain useful when their limits are explicit.
Preserve permitted alternatives: do not invent a deterministic choice, tie-break
rule or converse implication that the requirement does not promise.

## Challenge both omissions and extra restrictions

Construct a behavior that violates the selected requirement while satisfying the
proposed checks. Target the main relationship and its relevant branches, rather
than only a malformed output that an easy shape check rejects. Repair the missing
clause or retain it as an explicit gap. Also look for a permitted behavior that
the formalization rejects. Check that assumptions admit meaningful successful
cases; a nonvacuous property can still be incomplete. These examples guide review,
not a claim of equivalence or a mandatory solver pass.

## Keep uncertainty and observation boundaries explicit

Preserve clear guarantees while isolating ambiguous or conflicting cases. Record
the disputed meaning instead of replacing the whole promise with a weaker common
condition. Do not invent an answer, silently narrow the legal domain or turn a
required failure case into a precondition. Seek a decision only when the unresolved
meaning blocks the authorized work.

Identify the actual observation point. A post-call mutable input is not its
pre-call value; capture prior state when the harness supports it, or state what
cannot be checked. Match justified arithmetic, conversion, rounding and equality
semantics. Greater numeric precision or an arbitrary tolerance is not automatically
a faithful translation. Keep predicates defined on the legal domain and affordable
within the check's budget; preserve timeout and evaluation-error outcomes as gaps.

## Preserve meaning through evolution

For an affected promise, account for preserved, changed, added and removed clauses
in the existing change summary. Follow them to assertions, generators and model
assumptions. Where applicable, identify a behavior whose acceptance should change
and one whose acceptance should remain unchanged, including relevant failure and
boundary behavior. Only authorized changes may alter the promise; unchanged IDs
or passing tests do not establish that its meaning survived.
