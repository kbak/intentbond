---
theme: default
title: Proving the Wrong Thing, Faster
author: Kacper Bak, PhD
favicon: /favicon.svg
info: |
  A talk on intent, validation, and requirements reconciliation.
layout: talk
class: cover-slide
aspectRatio: 16/9
canvasWidth: 1280
colorSchema: light
fonts:
  sans: Ubuntu Sans
  mono: Ubuntu Mono
  provider: none
drawings:
  enabled: false
transition: fade
duration: 12min
mdc: false
defaults:
  layout: talk
---

# Proving the<br>Wrong Thing,<br><span class="coral">Faster</span>

<div class="cover-stack" aria-label="Code, tests, and proof pass; alignment with intent remains uncertain">
  <div class="stack-card"><span>Code</span><b>✓</b></div>
  <div class="stack-card"><span>Tests</span><b>✓</b></div>
  <div class="stack-card"><span>Proof</span><b>✓</b></div>
  <div class="stack-card intent-card"><span>Intent</span><b>?</b></div>
</div>

<div class="cover-byline">Kacper Bak, PhD</div>

<!--
Pre-talk holding slide · outside the talk timing
-->

---
title: Keep verifying the right things.
class: overview-slide
---

# Keep verifying the <span class="coral">right things.</span>

<div class="overview-points">

- **Shared misunderstanding.**
- **A valid proof of the wrong property.**
- **Change reopens the question.**
- **How to keep artifacts aligned with the intent?**

</div>

<div class="cover-stack" aria-label="Code, tests, and proof pass; alignment with intent remains uncertain">
  <div class="stack-card"><span>Code</span><b>✓</b></div>
  <div class="stack-card"><span>Tests</span><b>✓</b></div>
  <div class="stack-card"><span>Proof</span><b>✓</b></div>
  <div class="stack-card intent-card"><span>Intent</span><b>?</b></div>
</div>

<p class="overview-experiment">IntentBond helps agents preserve intent.</p>

<!--
00:00–00:45 · 45 seconds

We can now ask an agent to write the code, write the tests, and help produce a proof.
What if all three agree because they inherited the same misunderstanding?

The proof can still be valid: the implementation satisfies a property that misrepresents what the user wanted.

And even if it is right today, the software and expectations will change.
Which guarantees still apply? What must be re-established?

That’s what this talk is about: keeping intent, specifications, implementation, and evidence aligned as they evolve—so we keep verifying the right things.

IntentBond is one experiment in supporting that work.
-->

---
title: Verification and validation
class: questions-slide
clicks: 2
---

<p class="challenge-framing"><strong>Proving a system is “safe” depends on what we mean by “safe.”</strong></p>

<div class="question-grid">
  <section class="question-panel verification">
    <div class="panel-label">VERIFICATION</div>
    <h1>Are we building<br>the <em>system<br>right?</em></h1>
    <p class="reference-point">Behavior against the specification</p>
  </section>
  <section class="question-panel validation question-reveal" :class="{ 'is-revealed': $clicks >= 1 }" :aria-hidden="$clicks < 1">
    <div class="panel-label">VALIDATION</div>
    <h1>Are we building<br>the <em>right<br>system?</em></h1>
    <p class="reference-point">The system against intended use</p>
  </section>
</div>

<div class="vv-consequence question-reveal" :class="{ 'is-revealed': $clicks >= 2 }" :aria-hidden="$clicks < 2">Verification can succeed while validation fails<br /><span class="vv-reverse">Verification cannot decide what users need</span></div>

<!--
00:45–01:45 · 60 seconds

When we say a system is safe, we mean that nothing bad happens within the scope we’ve defined. But what counts as "bad"? And have we chosen the right scope?

We make those choices explicit in a specification.

Verification checks whether the implementation satisfies it.
Validation asks whether the specification and resulting behavior serve the intended use.

We can prove that we meet a definition of safety—and still have chosen the wrong definition.

Formal models and counterexamples can help uncover that mismatch, but cannot decide what users need. The next example shows this gap.

Source: https://www.nasa.gov/reference/2-4-distinctions-between-product-verification-and-product-validation/
-->

---
title: Correct proof. Wrong promise.
class: example-slide
---

# Correct proof. Wrong promise.

<div class="stakeholder-quote">“Expire session after 30 minutes of <strong>inactivity.</strong>”<br /><br />Agent:</div>

<SessionTimeline />

<PropertyStatement reference="login_time" tone="wrong" />

<!--
01:45–02:50 · 65 seconds

The stakeholder says: sessions must expire after thirty minutes of inactivity.
The agent turns this into: expire thirty minutes after login.

Read the timeline: login at zero; qualifying activity at minute twenty-five.
At minute thirty, access denied.

A proof of the displayed login-age property could succeed.
Yet the user has only been inactive for five minutes.

The specification misinterprets the intent.
-->

---
title: The intended behavior.
class: example-slide
---

# The intended behavior.

<div class="stakeholder-quote">“Expire session after 30 minutes of <strong>inactivity.</strong>”</div>

<SessionTimeline refined />

<PropertyStatement reference="last_activity" tone="candidate" />

<!--
02:50–03:20 · 30 seconds

The intended behavior is: still active at thirty, then expired at fifty-five if there is no further activity.
The green interval measures time since the last activity, not since login.

We now have a property that matches our intent.

But software keeps changing.
What ensures that the existing promises survive?
-->

---
title: Is your agent still building the right system?
class: agent-drift-slide
---

# Is your agent <strong>still</strong> building the right system?

<p class="agent-drift-request"><strong>Next request:</strong> “Add audit logging to session expiry.”</p>

<div class="agent-drift-examples">
  <div><strong>Invent</strong><span>Add a session lifetime cap nobody requested.</span></div>
  <div><strong>Miss</strong><span>Forget that activity resets the timer.</span></div>
  <div><strong>Reinterpret</strong><span>Count background heartbeats as user activity.</span></div>
  <div><strong>Delete</strong><span>Remove session expiry.</span></div>
</div>

<p class="agent-drift-checks">Tests and proofs can pass against a weakened specification.</p>

<div class="agent-drift-boundary">How to keep intent, spec, implementation, tests, and evidence aligned?</div>

<!--
03:20–04:20 · 60 seconds

The next request is to add audit logging to session expiry.

An agent can go beyond that request:
invent a lifetime cap,
miss the timer reset,
reinterpret background heartbeats as user activity, or
delete expiry during a refactor.

The specification can stay unchanged while the behavior drifts.
Or the specification itself can be weakened, letting tests and proofs pass even as behavior departs from the accepted intent.

We need to compare the actual change with what was asked for, including the promises that should remain unchanged.

How do we keep doing that as the software evolves?
-->

---
title: IntentBond keeps development artifacts in sync.
class: repository-slide
---

# IntentBond keeps development artifacts in sync.

<p class="tool-intro">Agent skills + tools: links, checks, guidance for dev workflow</p>

<div class="tool-mechanisms">

- **Connect** <span>Establish links between intent, spec, implementation, and tests.</span>
- **Guide** <span>Direct repairs with deterministic feedback.</span>
- **Validate** <span>Review behavior against intent; repair or clarify.</span>
- **Refine** <span>Gradually formalize requirements into properties and models.</span>

</div>

<div class="related-credit">Built on <a href="https://github.com/itsallcode/openfasttrace">OpenFastTrace</a>.<br />Related: <a href="https://github.com/OathTech/covmap">Covmap</a> · <a href="https://tracey.bearcove.eu/guide/ai-integration/">Tracey</a> · <a href="https://github.com/Looted/kibi">Kibi</a> · <a href="https://github.com/spolu/code-contracts">Code Contracts</a> · <a href="https://openspec.dev/">OpenSpec</a></div>

<!--
04:20–05:05 · 45 seconds

IntentBond is a set of agent skills and tools.
It puts links, checks and review guidance into the agent's development workflow.

Connect supplies the links.
Guide supplies deterministic diagnostics for repair.
Validate prompts the agent to judge behavior against intent and act on mismatches.
Refine develops the models and properties.

These activities reinforce each other.
Validation continues throughout refinement and development.

Let's look at each.
-->

---
title: "Connect: links between artifacts."
class: trace-example-slide
clicks: 1
---

# <span class="capability-verb">Connect:</span> links between artifacts.

<RequirementTrace />


<div class="trace-example-credit">Document split follows <a href="https://claude.com/resources/articles/the-ai-native-sdlc-playbook">Anthropic’s AI-native SDLC playbook</a>.</div>

<!--
05:05–05:50 · 45 seconds

intent.md states the outcome;
spec.md refines it using prose and a formal property.
It can also capture design decisions and rationale.
Git preserves their recorded history; people remain accountable for those decisions.

`Covers` links the requirement back to intent;
`Needs` requires implementation and test coverage.
Annotations connect the Lean files to the requirement.
These links show relationships.

The #guard checks test the boundary: just before thirty minutes, and exactly at thirty minutes.
-->

---
title: "Guide: give agents deterministic feedback."
class: impact-slide
clicks: 4
---

# <span class="capability-verb">Guide:</span> give agents deterministic feedback.

<CheckRepairLoop />

<!--
05:50–07:10 · 80 seconds

The privileged timeout changes from thirty to five minutes.
Code and tests already implement five minutes;
the implementation annotation still names revision 1.

The deterministic check rejects that stale link even though tests pass.
The agent reads the revised promise, confirms the behavior, repairs the annotation and reruns the check. Links and tests now pass.

The OFT trace graph supports impact analysis and checks required coverage between intent, requirements, implementation and tests.

The links and tests can pass while the actual change violates intent.
Let's review the behavior against the request.
-->

---
title: "Validate: does the change preserve intent?"
class: validation-slide
clicks: 3
---

# <span class="capability-verb">Validate:</span> does the change preserve intent?

<ChangeValidation />

<!--
07:10–08:00 · 50 seconds

Consider another failure in the same timeout-change scenario: we asked for privileged sessions to expire after five minutes. The agent applied that limit to every session.

Previously, Guide detected a broken reference. What if the reference itself is correct?

Here, IntentBond’s skill directs the agent to review the change against the linked requirements: ordinary sessions still need thirty minutes.

The agent restores thirty minutes for ordinary sessions, checks both roles, and reruns the checks. When intent is unclear, it seeks clarification.

That review relies on agent judgment.
Can we make more of these expectations formally checkable?
-->

---
title: "Refine: make requirements formally checkable."
class: formalization-slide
clicks: 4
---

# <span class="capability-verb">Refine:</span> make requirements formally checkable.

<FormalizationPath />

<!--
08:00–09:00 · 60 seconds

IntentBond helps agents progressively refine intent into an informal specification, then a formal one.

That lets us verify whether detailed rules satisfy formalized intent, before writing the implementation.

Scenarios and counterexamples also help us refine the requirements with stakeholders: do they capture what was intended?

The formal specification then guides implementation and verification.
It can help agents derive better tests.

Agents can propose properties and invariants.
Stakeholders and engineers must judge whether they capture the intended behavior.
-->

---
title: Future work for IntentBond
class: future-work-slide
---

# What’s next for IntentBond?

<FutureWork />

<!--
09:00–10:00 · 60 seconds

Four directions for IntentBond.

First, evaluation: compare the same agent with and without IntentBond over successive changes. Measure intent preservation, false assurance, review effort, and cost.

Second, turn counterexamples and surprising behaviors into focused questions for users, then capture their answers as requirements.

Third, go beyond stale links: detect weakened properties and changed assumptions, and identify guarantees that need to be re-established.

Fourth, connect decisions to production outcomes: even if we implement the decision correctly, was it a good decision?
-->

---
title: Keep verifying the right things.
class: closing-slide
---

# Keep verifying<br>the <span class="coral">right things.</span>

<div class="closing-body">
  <div class="closing-argument">
    <p>Keeping specs and code faithful to intent is still hard.</p>
    <p>Agents help maintain alignment and decision history.</p>
    <p class="closing-accountability">We remain responsible for the properties we choose.</p>
  </div>
  <div class="closing-repository">
    <a class="closing-qr" href="https://github.com/kbak/intentbond" aria-label="Open the IntentBond GitHub repository">
      <img src="/intentbond-qr.svg" alt="QR code for https://github.com/kbak/intentbond" width="259" height="259" />
    </a>
    <div class="closing-link"><a href="https://github.com/kbak/intentbond">github.com/kbak/intentbond</a></div>
  </div>
</div>
<div class="closing-takeaway">Making continuous alignment practical.</div>

<!--
10:00–11:05 · 65 seconds, including a closing pause

Keeping specifications and implementations faithful to intent has always been hard.
Faster generation makes continuous alignment more important.

Agents can help maintain that alignment and record why decisions were made.
Formal methods strengthen guarantees,
We remain responsible for choosing what to guarantee.

You define what “safe” means.
That definition is part of your verification story.

IntentBond is one experiment in making continuous alignment practical.
-->

---
title: Extra slides.
class: appendix-divider
appendix: true
---

# Extra slides

<!--
Optional appendix divider.

The main talk ends at the conclusion. Use these extra slides only if questions lead to requirements elicitation or the software-factory example; they are outside the main timing.
-->

---
title: We don’t know every requirement upfront.
class: elicitation-slide
---

# We don’t know every requirement upfront.

<div class="elicitation-questions">
  <section>
    <h2>Should active sessions expire too?</h2>
    <p>A maximum lifetime would require another condition.</p>
  </section>
  <section>
    <h2>Does a background heartbeat count as activity?</h2>
    <p>Counting it could keep an unattended session alive indefinitely.</p>
  </section>
</div>

<div class="elicitation-credit">AI-assisted elicitation, e.g. <a href="https://github.com/mattpocock/skills/blob/5beb35b040e3de97e54fa9e386d7e42d15c295c2/skills/productivity/grilling/SKILL.md">Matt Pocock’s grill-me</a></div>

<!--
Optional discussion · about 60–90 seconds

Developers often do not know every requirement upfront. Elicitation discovers missing decisions as well as clarifying language.
-->

---
title: Keep alignment in the factory loop.
class: factory-slide
---

# Keep alignment in the factory loop.

<FactoryLoop />

<div class="factory-gate"><strong>Publication gate:</strong> checks pass · review satisfied · evidence matches code.</div>

<!--
Optional discussion · about 60 seconds

The boundary is IntentMade, powered by OpenHands. IntentBond guides its coordinator, implementation agent and reviewers. Intent, specification and plan follow Anthropic's SDLC artifact roles.

The upper path builds a change, validates it, and publishes a draft PR. Failed checks or requested changes trigger repair and fresh validation. Evidence must match the published code.

The lower path reviews someone else's PR. CI can enforce IntentBond's deterministic checks. With CI passing, a GitHub review event triggers IntentMade's review against accepted intent, guided by IntentBond. Passing review leads to approval. CI failures and requested review changes return to the author through the same update loop. Updated PRs rerun CI before review. Semantic review still involves agent judgment.
-->

---
title: Built on OFT. Packaged for agents.
class: related-work-slide
---

# Built on OFT. Packaged for agents.

<RelatedWork />

<!--
Optional comparison · use only for questions

Selected differences, not exclusive features. We deliberately reuse OFT's machinery.

`Needs: impl, utest` makes both links mandatory in OFT; a missing test link fails coverage.

Tracey already has versioned links. IntentBond also maintains refinement from intent through requirements and optional models.

Kibi organizes work around typed facts, scenarios and proof contracts. IntentBond starts with linked artifacts and existing tests; formal models are optional. Kibi also supports SMT certificates, so formal verification is not exclusive.

Code Contracts validates syntax/IDs; prose compliance needs judgment.

OpenSpec validates spec/change documents deterministically; code correspondence is agent-assessed. IntentBond's semantic review also needs judgment.

Sources: research/related-work.md; Kibi [modeling workflow](https://github.com/Looted/kibi/blob/develop/docs/modeling-cheatsheet.md) and [proof contracts](https://github.com/Looted/kibi/blob/develop/docs/proving-requirements.md#certificate-proof-kinds); OpenSpec [validation](https://github.com/Fission-AI/OpenSpec/blob/main/docs/cli.md#openspec-validate) and [review](https://github.com/Fission-AI/OpenSpec/blob/main/src/core/templates/workflows/verify-change.ts).
-->
