<script setup>
import { useId } from 'vue';
import { useSlideContext } from '@slidev/client';

const { $clicks } = useSlideContext();
const arrowId = useId();
const reviewArrowId = useId();
</script>

<template>
  <div class="formalization-path" role="group" aria-label="Refinement, specification checking, requirements validation and implementation verification. Boxes are artifacts; labeled arrows are activities.">
    <svg class="formalization-links" viewBox="0 0 1152 480" aria-hidden="true">
      <defs>
        <marker :id="arrowId" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
          <path d="M1 1 L9 5 L1 9" fill="none" stroke="var(--teal)" stroke-width="1.5" />
        </marker>
        <marker :id="reviewArrowId" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
          <path d="M1 1 L9 5 L1 9" fill="none" stroke="var(--coral)" stroke-width="1.5" />
        </marker>
      </defs>
      <g class="forward-links" :marker-end="`url(#${arrowId})`">
        <path d="M176 120 H240" />
        <path class="formalization-reveal" :class="{ 'is-revealed': $clicks >= 1 }" d="M460 120 H524" />
        <path class="formalization-reveal" :class="{ 'is-revealed': $clicks >= 4 }" d="M772 120 H852" />
        <path class="spec-check-link formalization-reveal" :class="{ 'is-revealed': $clicks >= 2 }" d="M648 228 V318" />
        <path class="formalization-reveal" :class="{ 'is-revealed': $clicks >= 4 }" d="M825 244 V318" />
      </g>
      <g class="verification-inputs">
        <path class="formalization-reveal" :class="{ 'is-revealed': $clicks >= 2 }" d="M648 182 V228" />
        <path class="formalization-reveal" :class="{ 'is-revealed': $clicks >= 4 }" d="M648 228 Q648 244 664 244 H825" />
        <path class="formalization-reveal" :class="{ 'is-revealed': $clicks >= 4 }" d="M1002 182 V228 Q1002 244 986 244 H825" />
      </g>
      <circle class="verification-junction formalization-reveal" :class="{ 'is-revealed': $clicks >= 4 }" cx="648" cy="228" r="3.5" />
      <circle class="verification-junction formalization-reveal" :class="{ 'is-revealed': $clicks >= 4 }" cx="825" cy="244" r="3.5" />
      <path class="review-link formalization-reveal" :class="{ 'is-revealed': $clicks >= 3 }" d="M620 373 H112 Q88 373 88 349 V182" :marker-end="`url(#${reviewArrowId})`" />
    </svg>

    <span class="intent-refinement-label">Refine</span>
    <section class="formalization-node intent-node"><h2>Intent</h2></section>
    <section class="formalization-node informal-node"><h2>Informal spec</h2></section>
    <div class="formal-spec-stage formalization-reveal" :class="{ 'is-revealed': $clicks >= 1 }" :aria-hidden="$clicks < 1">
      <span class="spec-refinement-label">Refine</span>
      <section class="formalization-node formal-node">
        <h2>Formal spec</h2>
        <p>e.g. Lean, Alloy, SMT</p>
      </section>
    </div>

    <div class="spec-check-stage formalization-reveal" :class="{ 'is-revealed': $clicks >= 2 }" :aria-hidden="$clicks < 2">
      <span class="spec-check-label">Verify spec<small>Against formalized intent<br />Before implementation</small></span>
      <section class="formalization-node verification-node">
        <h2>Verification evidence</h2>
        <p>Results · counterexamples</p>
      </section>
    </div>
    <span class="review-label formalization-reveal" :class="{ 'is-revealed': $clicks >= 3 }" :aria-hidden="$clicks < 3">Validate requirements</span>

    <div class="implementation-stage formalization-reveal" :class="{ 'is-revealed': $clicks >= 4 }" :aria-hidden="$clicks < 4">
      <span class="guidance-label">Guide</span>
      <section class="formalization-node implementation-node"><h2>Implementation</h2></section>
      <span class="verification-label">Verify implementation<small>Property tests · proofs</small></span>
      <div class="refinement-remark test-generation-remark">
        <strong>Specs can help agents write better tests.</strong>
        <div class="system-property">
          <strong>People decide what must hold, agents help formalize it.</strong>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.formalization-path { position: relative; height: 506px; margin-top: 30px; }
.formalization-links { position: absolute; inset: 0; width: 100%; height: 480px; overflow: visible; }
.formalization-reveal { opacity: 0; visibility: hidden; pointer-events: none; transition: opacity 240ms ease, visibility 0s 240ms; }
.formalization-reveal.is-revealed { opacity: 1; visibility: visible; pointer-events: auto; transition-delay: 0s; }
.forward-links path, .verification-inputs path, .review-link { fill: none; stroke: var(--teal); stroke-width: 2.5; }
.verification-junction { fill: var(--teal); }
.review-link { stroke: var(--coral); }
.formalization-node { position: absolute; display: flex; flex-direction: column; align-items: center; justify-content: center; top: 58px; height: 124px; padding: 18px; border: 1px solid #b8cbbf; border-radius: 8px; background: #edf0e8; text-align: center; }
.formalization-node h2 { margin: 0; font-size: 31px; line-height: 1.2; font-weight: 550; letter-spacing: -0.5px; }
.formalization-node p { margin: 14px 0 0; font-size: 21px; line-height: 1.25; color: var(--muted); }
.intent-node { left: 0; width: 176px; }
.informal-node { left: 240px; width: 220px; }
.formal-node { left: 524px; width: 248px; background: var(--teal); border-color: var(--teal); color: var(--paper); }
.formal-node p { color: #d0e8df; font-size: 19px; }
.implementation-node { left: 852px; width: 300px; }
.verification-node { left: 620px; top: 318px; width: 410px; height: 110px; border-color: #d6ada0; background: #f0e8df; }
.verification-node h2 { font-size: 28px; }
.verification-node p { font-size: 20px; }
.intent-refinement-label, .spec-refinement-label, .guidance-label, .spec-check-label, .verification-label, .review-label { position: absolute; font-size: 23px; line-height: 1.25; }
.intent-refinement-label, .spec-refinement-label { top: 82px; font-size: 18px; color: var(--teal); }
.intent-refinement-label { left: 181px; }
.spec-refinement-label { left: 465px; }
.guidance-label { left: 789px; top: 82px; font-size: 18px; color: var(--teal); }
.spec-check-label { left: 388px; top: 226px; width: 240px; text-align: right; }
.verification-label { left: 845px; top: 250px; }
.spec-check-label small, .verification-label small { display: block; margin-top: 4px; font-size: 18px; line-height: 1.25; color: var(--muted); }
.review-label { left: 166px; top: 333px; color: #ab4433; }
.refinement-remark { position: absolute; top: 429px; font-size: 23px; line-height: 1.2; }
.refinement-remark strong { display: block; color: var(--teal); font-weight: 550; }
.system-property { display: flex; align-items: baseline; gap: 8px; width: max-content; margin-top: 12px; white-space: nowrap; }
.system-property em { font-size: 22px; line-height: 1.2; color: var(--muted); }
.test-generation-remark { left: 0; width: 552px; }
.property-selection-remark { left: 620px; width: 532px; }
@media (prefers-reduced-motion: reduce), print {
  .formalization-reveal { transition: none; }
}
</style>
