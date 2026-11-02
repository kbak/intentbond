<script setup>
import { useSlideContext } from '@slidev/client';

const { $clicks } = useSlideContext();
</script>

<template>
  <div class="change-validation" role="group" aria-label="IntentBond-guided validation of a change against intent">
    <section class="review-guidance" aria-label="IntentBond guides review through linked requirements and intent">
      <h2>IntentBond-guided review</h2>
      <p>Code against <strong>(linked) intent; ask when unclear</strong></p>
    </section>

    <div class="behavior-comparison" role="group" aria-label="Compare current, requested and changed idle-timeout behavior">
      <section class="comparison-side current-side">
        <h2>Current</h2>
        <div class="comparison-card">
          <p>All sessions</p>
          <div class="timeout">30 <span>min</span></div>
        </div>
      </section>

      <section class="comparison-side requested-side validation-reveal" :class="{ 'is-revealed': $clicks >= 1 }" :aria-hidden="$clicks < 1">
        <h2>Requested</h2>
        <div class="comparison-card requested-change">
          <p>Privileged sessions</p>
          <div class="timeout">5 <span>min</span></div>
        </div>
      </section>

      <section class="comparison-side changed-side validation-reveal" :class="{ 'is-revealed': $clicks >= 2 }" :aria-hidden="$clicks < 2">
        <h2>Changed</h2>
        <div class="comparison-card proposed-change">
          <p>All sessions</p>
          <div class="timeout">5 <span>min</span></div>
        </div>
      </section>
    </div>

    <section class="agent-finding validation-reveal" :class="{ 'is-revealed': $clicks >= 3 }" :aria-hidden="$clicks < 3">
      <h2>Agent action</h2>
      <p>Restore <strong>30 min for ordinary sessions</strong>, then rerun checks.</p>
    </section>
  </div>
</template>

<style scoped>
.change-validation { position: relative; height: 506px; margin-top: 24px; }
.validation-reveal { opacity: 0; visibility: hidden; pointer-events: none; transition: opacity 240ms ease, visibility 0s 240ms; }
.validation-reveal.is-revealed { opacity: 1; visibility: visible; pointer-events: auto; transition-delay: 0s; }
.review-guidance { padding: 17px 24px 19px; border-left: 4px solid var(--teal); background: #e5ece3; }
.review-guidance h2, .agent-finding h2 { margin: 0; color: var(--teal); font-size: 22px; line-height: 1.25; font-weight: 550; }
.review-guidance p { margin-top: 8px; font-size: 32px; line-height: 1.25; font-weight: 550; }
.review-guidance strong { color: var(--teal); font-weight: inherit; }
.behavior-comparison { position: absolute; top: 155px; left: 0; right: 0; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 28px; }
.comparison-side h2 { margin: 0 0 13px; font-size: 25px; line-height: 1.25; font-weight: 550; }
.comparison-card { height: 180px; padding: 24px; border: 1px solid #b8cbbf; border-radius: 8px; background: #edf0e8; }
.comparison-card p { font-size: 32px; line-height: 1.2; font-weight: 550; letter-spacing: -0.4px; }
.requested-change p { color: var(--teal); }
.proposed-change { border-color: #d6ada0; background: #f0e8df; }
.proposed-change p { color: #ab4433; }
.timeout { margin-top: 16px; font-size: 54px; line-height: 1.1; font-weight: 550; }
.timeout span { font-size: 28px; font-weight: 400; }
.agent-finding { position: absolute; top: 431px; left: 0; right: 0; }
.agent-finding p { margin-top: 9px; font-size: 30px; line-height: 1.25; }
.agent-finding strong { color: var(--teal); font-weight: 550; }
@media (prefers-reduced-motion: reduce), print {
  .validation-reveal { transition: none; }
}
</style>
