<script setup>
import { computed, useId } from 'vue';
import { useSlideContext } from '@slidev/client';

const { $clicks } = useSlideContext();
const detailed = computed(() => $clicks.value >= 1);
const linkId = useId();
</script>

<template>
  <div class="requirement-trace" :class="{ 'is-detailed': detailed }" role="group" aria-label="Intent linked to a specification, implementation and tests">
    <svg class="requirement-trace-links" viewBox="0 0 1152 472" aria-hidden="true">
      <defs>
        <symbol :id="linkId" viewBox="0 0 24 24">
          <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71 M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
        </symbol>
      </defs>
      <g class="trace-link-intent">
        <path class="trace-edge trace-edge-intent" d="M550 141 H602" />
        <circle class="trace-link-backing" cx="576" cy="141" r="17" />
        <use :href="`#${linkId}`" x="564" y="129" width="24" height="24" />
      </g>
      <g>
        <path class="trace-edge trace-edge-implementation" d="M750 282 V291 Q750 300 741 300 H284 Q275 300 275 309 V318" />
        <circle class="trace-link-backing" cx="512" cy="300" r="16" />
        <use :href="`#${linkId}`" x="500" y="288" width="24" height="24" />
      </g>
      <g>
        <path class="trace-edge trace-edge-test" d="M1004 282 V291 Q1004 300 995 300 H886 Q877 300 877 309 V318" />
        <circle class="trace-link-backing" cx="940" cy="300" r="16" />
        <use :href="`#${linkId}`" x="928" y="288" width="24" height="24" />
      </g>
    </svg>

    <section class="trace-snippet trace-intent" aria-label="Intent Markdown excerpt">
      <div class="trace-overview" :aria-hidden="detailed">Intent</div>
      <div class="trace-detail" :aria-hidden="!detailed">
      <h2><strong>intent.md</strong><span>Desired outcome</span></h2>
      <pre><code><span class="trace-intent-id">`intent~abandoned-sessions`</span>

User should not leave an unattended
account accessible indefinitely.

Needs: req</code></pre>
      </div>
    </section>

    <section class="trace-snippet trace-requirement" aria-label="Specification Markdown excerpt">
      <div class="trace-overview" :aria-hidden="detailed">Specification</div>
      <div class="trace-detail" :aria-hidden="!detailed">
      <h2><strong>spec.md</strong><span>Concrete requirement</span></h2>
      <pre><code><span class="trace-id">`req~session-expiration`</span>

Expire after 30 minutes of inactivity.
expired ↔ inactivity ≥ 30 min

Covers:
- <span class="trace-intent-id">`intent~abandoned-sessions`</span>
Needs: impl, utest</code></pre>
      </div>
    </section>

    <section class="trace-snippet trace-implementation" aria-label="Linked implementation">
      <div class="trace-overview" :aria-hidden="detailed">Implementation</div>
      <div class="trace-detail" :aria-hidden="!detailed">
      <h2><strong>Session.lean</strong></h2>
      <pre><code><span class="trace-id">-- [impl-&gt;req~session-expiration]</span>
def expired (idle : Nat) : Bool :=
  decide (idle ≥ 30 * 60)</code></pre>
      </div>
    </section>

    <section class="trace-snippet trace-test" aria-label="Linked test excerpt">
      <div class="trace-overview" :aria-hidden="detailed">Tests</div>
      <div class="trace-detail" :aria-hidden="!detailed">
      <h2><strong>SessionTests.lean</strong></h2>
      <pre><code><span class="trace-id">-- [utest-&gt;req~session-expiration]</span>
#guard expired <span class="trace-boundary">1799</span> == false
#guard expired <span class="trace-boundary">1800</span> == true</code></pre>
      </div>
    </section>
  </div>
</template>

<style scoped>
.requirement-trace { --trace-requirement: #8a5b12; position: relative; width: 100%; height: 472px; margin-top: 20px; }
.requirement-trace-links { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; color: var(--trace-requirement); }
.requirement-trace-links path { fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.trace-link-intent { color: #55509a; }
.trace-link-backing { fill: var(--paper); }
.trace-edge { transition: d 450ms ease; }
.trace-edge-intent { d: path("M475 141 H677"); }
.trace-edge-implementation { d: path("M750 197 V291 Q750 300 741 300 H284 Q275 300 275 309 V339"); }
.trace-edge-test { d: path("M1004 197 V291 Q1004 300 995 300 H886 Q877 300 877 309 V339"); }
.is-detailed .trace-edge-intent { d: path("M550 141 H602"); }
.is-detailed .trace-edge-implementation { d: path("M750 282 V291 Q750 300 741 300 H284 Q275 300 275 309 V318"); }
.is-detailed .trace-edge-test { d: path("M1004 282 V291 Q1004 300 995 300 H886 Q877 300 877 309 V318"); }
.trace-snippet { position: absolute; width: 400px; height: 112px; padding: 16px; border: 1px solid #b8cbbf; border-radius: 7px; background: #edf0e8; transition: left 450ms ease, top 450ms ease, width 450ms ease, height 450ms ease; }
.trace-intent { left: 75px; top: 85px; }
.trace-requirement { left: 677px; top: 85px; }
.trace-implementation { left: 75px; top: 339px; }
.trace-test { left: 677px; top: 339px; }
.is-detailed .trace-snippet { width: 550px; }
.is-detailed .trace-intent { left: 0; top: 0; height: 282px; }
.is-detailed .trace-requirement { left: 602px; top: 0; height: 282px; }
.is-detailed .trace-implementation { left: 0; top: 318px; height: 154px; }
.is-detailed .trace-test { left: 602px; top: 318px; height: 154px; }
.trace-overview { position: absolute; inset: 0; display: grid; place-items: center; font-size: 36px; line-height: 1.2; font-weight: 600; transition: opacity 180ms ease; }
.is-detailed .trace-overview { opacity: 0; }
.trace-detail { opacity: 0; visibility: hidden; transition: opacity 220ms ease, visibility 0s 220ms; }
.is-detailed .trace-detail { opacity: 1; visibility: visible; transition-delay: 200ms, 0s; }
.trace-snippet h2 { display: flex; justify-content: space-between; align-items: baseline; margin: 0 0 10px; font-size: 21px; line-height: 1.2; letter-spacing: 0; }
.trace-snippet h2 strong { color: var(--ink); font-weight: 600; }
.trace-snippet h2 span { color: var(--muted); font-size: 20px; font-weight: 400; }
.trace-snippet pre { margin: 0; padding: 0; background: transparent; font-family: 'Ubuntu Mono', monospace; font-size: 22px; line-height: 1.2; white-space: pre; overflow: visible; }
.trace-snippet code { font: inherit; }
.trace-intent-id { color: #55509a; }
.trace-id { color: var(--trace-requirement); }
.trace-boundary { color: var(--ink); }
@media (prefers-reduced-motion: reduce), print {
  .trace-snippet, .trace-edge, .trace-overview, .trace-detail { transition: none; }
}
</style>
