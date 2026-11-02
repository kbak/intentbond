<script setup>
import { computed, useId } from 'vue';
import { useSlideContext } from '@slidev/client';

const { $clicks } = useSlideContext();
const requirementUpdated = computed(() => $clicks.value >= 1);
const arrowId = useId();
</script>

<template>
  <div class="check-repair-loop" role="group" aria-label="Four-stage IntentBond check and repair cycle">
    <svg class="feedback-arrows" viewBox="0 0 1152 506" aria-hidden="true">
      <defs>
        <marker :id="arrowId" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto">
          <path d="M1 1 L9 5 L1 9" fill="none" stroke="var(--teal)" stroke-width="1.5" />
        </marker>
      </defs>
      <path class="feedback-reveal" :class="{ 'is-revealed': $clicks >= 2 }" d="M350 182 H401" :marker-end="`url(#${arrowId})`" />
      <path class="feedback-reveal" :class="{ 'is-revealed': $clicks >= 3 }" d="M751 182 H802" :marker-end="`url(#${arrowId})`" />
      <path class="feedback-reveal" :class="{ 'is-revealed': $clicks >= 4 }" d="M977 312 V330 Q977 350 957 350 H797 Q777 350 777 370 V408" :marker-end="`url(#${arrowId})`" />
    </svg>

    <section class="feedback-step edit-step">
      <h2><span>1</span> Agent edits</h2>
      <div class="feedback-artifact edited-files" :aria-label="requirementUpdated ? 'Updated specification and stale implementation annotation' : 'Original specification and matching implementation annotation'">
        <div class="file-label">spec.md</div>
        <div class="requirement-versions">
          <div v-for="revision in [1, 2]" :key="revision" class="requirement-version" :class="{ 'is-current': revision === (requirementUpdated ? 2 : 1) }" :aria-hidden="revision !== (requirementUpdated ? 2 : 1)">
            <div class="requirement-reference">
              <code class="requirement-id">req~timeout~<strong :class="{ 'current-revision': revision === 2 }">{{ revision }}</strong></code>
              <span class="revision-label">← revision</span>
            </div>
            <p class="requirement-meaning">Expire privileged sessions<br>after <strong :class="{ 'current-revision': revision === 2 }">{{ revision === 2 ? 5 : 30 }} minutes</strong> idle.</p>
          </div>
        </div>
        <div class="file-label implementation-label">Session.lean</div>
        <code class="annotation">-- [impl-&gt;req~timeout~<strong :class="{ 'stale-revision': requirementUpdated }">1</strong>]</code>
      </div>
    </section>

    <section class="feedback-step check-step feedback-reveal" :class="{ 'is-revealed': $clicks >= 2 }" :aria-hidden="$clicks < 2">
      <h2><span>2</span> First IntentBond check</h2>
      <div class="feedback-artifact rejected-report" aria-label="Condensed checker diagnostic">
        <div class="check-status">Rejected</div>
        <p class="diagnostic">Link target not found:</p>
        <code class="missing-target">req~timeout~1</code>
        <p class="passing-tests">Tests passed</p>
      </div>
    </section>

    <section class="feedback-step repair-step feedback-reveal" :class="{ 'is-revealed': $clicks >= 3 }" :aria-hidden="$clicks < 3">
      <h2><span>3</span> Agent repairs</h2>
      <div class="feedback-artifact repair-diff" aria-label="Implementation annotation repair after reviewing the revised promise">
        <p class="repair-review">Review the revised promise.</p>
        <div class="file-label repair-file">Session.lean</div>
        <div class="removed-line"><span>−</span><code>-- [impl-&gt;req~timeout~1]</code></div>
        <div class="added-line"><span>+</span><code>-- [impl-&gt;req~timeout~2]</code></div>
      </div>
    </section>

    <div class="rerun-stage feedback-reveal" :class="{ 'is-revealed': $clicks >= 4 }" :aria-hidden="$clicks < 4">
      <div class="rerun-action"><span>4</span> Check again after repair</div>
      <div class="feedback-artifact rerun-report" aria-label="Second check, after the repair: links and tests passed">
        <span>Links + tests <strong>passed</strong></span>
      </div>

      <div class="feedback-remarks">
        <strong>Impact analysis across artifacts.</strong>
        <strong>Coverage: detect traceability gaps.</strong>
      </div>
    </div>
  </div>
</template>

<style scoped>
.check-repair-loop { position: relative; height: 506px; margin-top: 24px; }
.feedback-arrows { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }
.feedback-arrows > path { fill: none; stroke: var(--teal); stroke-width: 2.5; }
.feedback-reveal { opacity: 0; visibility: hidden; pointer-events: none; transition: opacity 240ms ease, visibility 0s 240ms; }
.feedback-reveal.is-revealed { opacity: 1; visibility: visible; pointer-events: auto; transition-delay: 0s; }
.requirement-versions { display: grid; }
.requirement-version { grid-area: 1 / 1; opacity: 0; visibility: hidden; transition: opacity 180ms ease, visibility 0s 180ms; }
.requirement-version.is-current { opacity: 1; visibility: visible; transition-delay: 0s; }
.feedback-step { position: absolute; top: 12px; width: 350px; }
.edit-step { left: 0; }
.check-step { left: 401px; }
.repair-step { left: 802px; }
.feedback-step h2 { margin: 0; font-size: 26px; line-height: 1.2; font-weight: 550; letter-spacing: -0.4px; }
.feedback-step h2 > span, .rerun-action > span { display: inline-block; margin-right: 10px; color: var(--teal); }
.feedback-artifact { border: 1px solid #b8cbbf; border-radius: 8px; background: #edf0e8; }
.feedback-step .feedback-artifact { height: 254px; margin-top: 15px; padding: 20px; }
.file-label { color: var(--muted); font-size: 20px; line-height: 1.2; }
.requirement-reference { display: flex; align-items: baseline; gap: 8px; margin-top: 6px; }
.requirement-id { display: block; font-size: 28px; line-height: 1.2; }
.revision-label { color: var(--muted); font-size: 20px; white-space: nowrap; }
.current-revision { color: var(--teal); font-weight: 700; }
.stale-revision { color: #ab4433; font-weight: 700; }
.edited-files .requirement-meaning { margin-top: 8px; color: var(--muted); font-size: 22px; line-height: 1.25; }
.implementation-label { margin-top: 28px; }
.annotation { display: block; margin-top: 8px; white-space: nowrap; font-size: 23px; line-height: 1.25; }
.rejected-report { border-color: #c99b8c; background: #f0e8df; }
.check-status { color: #ab4433; font-size: 35px; line-height: 1.15; font-weight: 550; }
.rejected-report .diagnostic { margin-top: 24px; font-size: 23px; line-height: 1.25; }
.missing-target { display: block; margin-top: 8px; color: #ab4433; font-size: 27px; line-height: 1.2; }
.rejected-report .passing-tests { margin-top: 28px; color: var(--teal); font-size: 23px; line-height: 1.25; }
.repair-diff .repair-review { font-size: 23px; line-height: 1.3; }
.repair-file { margin-top: 33px; margin-bottom: 14px; }
.removed-line, .added-line { display: flex; gap: 9px; align-items: baseline; font-size: 22px; line-height: 1.5; white-space: nowrap; }
.removed-line { color: #ab4433; }
.added-line { color: var(--teal); }
.rerun-action { position: absolute; left: 401px; top: 360px; font-size: 26px; line-height: 1.25; font-weight: 550; }
.rerun-report { position: absolute; left: 401px; right: 0; top: 408px; height: 88px; display: grid; place-items: center; text-align: center; font-size: 30px; line-height: 1.25; }
.rerun-report > span { color: var(--teal); }
.rerun-report strong { font-weight: 600; }
.feedback-remarks { position: absolute; left: 0; top: 435px; width: 380px; display: grid; gap: 12px; color: var(--teal); font-size: 23px; line-height: 1.2; }
.feedback-remarks strong { display: block; font-weight: 550; }
@media (prefers-reduced-motion: reduce), print {
  .feedback-reveal, .requirement-version { transition: none; }
}
</style>
