<template>
  <svg class="factory-loop" viewBox="0 0 1152 452" role="img" aria-labelledby="factory-title factory-desc">
    <title id="factory-title">IntentMade runs development and PR review with IntentBond-guided agents</title>
    <desc id="factory-desc">The IntentMade boundary contains specification, build, validation, draft-PR publication, and a separate review path for someone else's PR. IntentBond guides the agents in both paths. The build workflow loops through repair and fresh checks. An external PR passes CI with IntentBond checks before a GitHub event triggers IntentMade's review against intent. Passing review leads to approval. CI failures and requested review changes share a return path to the author, who updates the PR; the updated PR passes through CI and, when checks pass, review again.</desc>
    <defs>
      <marker id="factory-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto">
        <path d="M1 1 L9 5 L1 9" fill="none" stroke="var(--teal)" stroke-width="1.5" />
      </marker>
      <marker id="repair-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto">
        <path d="M1 1 L9 5 L1 9" fill="none" stroke="var(--coral)" stroke-width="1.5" />
      </marker>
    </defs>

    <!-- One ownership boundary; CI and the incoming PR remain outside it. -->
    <path d="M12 1 H1140 Q1151 1 1151 12 V396 Q1151 408 1140 408 H732 Q720 408 720 396 V276 Q720 264 708 264 H12 Q1 264 1 252 V12 Q1 1 12 1 Z" fill="none" stroke="#b8cbbf" stroke-width="2" />
    <text x="24" y="38" class="owner-label" fill="var(--ink)">IntentMade</text>
    <text x="1128" y="38" text-anchor="end" class="guidance-label" fill="var(--teal)">Agents guided by <tspan font-weight="650">IntentBond</tspan></text>

    <g fill="none" stroke="var(--teal)" stroke-width="2.5" marker-end="url(#factory-arrow)">
      <path d="M252 133 H328" />
      <path d="M556 133 H632" />
      <path d="M860 133 H936" />
    </g>
    <g fill="#edf0e8" stroke="#b8cbbf">
      <rect x="24" y="78" width="228" height="110" rx="8" />
      <rect x="328" y="78" width="228" height="110" rx="8" />
      <rect x="632" y="78" width="228" height="110" rx="8" />
    </g>
    <rect x="936" y="78" width="192" height="110" rx="8" fill="var(--teal)" />
    <g text-anchor="middle" class="diagram-label" fill="var(--ink)">
      <text x="138" y="126">Specify</text>
      <text x="442" y="126">Build</text>
      <text x="746" y="126">Validate</text>
      <text x="1032" y="126" fill="var(--paper)">Publish</text>
    </g>
    <g text-anchor="middle" class="diagram-note" fill="var(--muted)">
      <text x="138" y="162">Intent · spec · plan</text>
      <text x="442" y="162">Code · tests</text>
      <text x="746" y="162">Checks · review</text>
      <text x="1032" y="162" fill="var(--paper)">Draft PR</text>
    </g>

    <path d="M746 188 V214 Q746 232 728 232 H460 Q442 232 442 214 V188" fill="none" stroke="var(--coral)" stroke-width="2.5" marker-end="url(#repair-arrow)" />
    <rect x="542" y="214" width="104" height="36" fill="var(--paper)" />
    <text x="594" y="239" text-anchor="middle" class="repair-label" fill="#ab4433">Repair</text>

    <!-- External PR review enters the same factory through a distinct path. -->
    <text x="0" y="347" class="source-label" fill="var(--ink)">Someone else’s PR</text>
    <rect x="318" y="290" width="238" height="96" rx="8" fill="var(--paper)" stroke="#b8cbbf" />
    <rect x="744" y="290" width="210" height="96" rx="8" fill="#edf0e8" stroke="#b8cbbf" />
    <rect x="1016" y="306" width="112" height="64" rx="8" fill="var(--teal)" />
    <g text-anchor="middle" class="diagram-label" fill="var(--ink)">
      <text x="437" y="330">CI enforces</text>
      <text x="849" y="330">Review</text>
    </g>
    <g text-anchor="middle" class="diagram-note" fill="var(--muted)">
      <text x="437" y="364">IntentBond checks</text>
      <text x="849" y="364">Against intent</text>
    </g>
    <g fill="none" stroke="var(--teal)" stroke-width="2.5" marker-end="url(#factory-arrow)">
      <path d="M250 338 H318" />
      <path d="M556 338 H744" />
      <path d="M954 338 H1016" />
    </g>
    <text x="650" y="319" text-anchor="middle" class="event-label" fill="var(--teal)">Pass</text>
    <text x="1072" y="347" text-anchor="middle" class="approval-label" fill="var(--paper)">Approve</text>

    <path d="M849 386 V412 Q849 430 831 430 H135 Q117 430 117 412 V360" fill="none" stroke="var(--coral)" stroke-width="2.5" marker-end="url(#repair-arrow)" />
    <path d="M340 386 V430" fill="none" stroke="var(--coral)" stroke-width="2.5" />
    <circle cx="340" cy="430" r="3.5" fill="var(--coral)" />
    <text x="327" y="416" text-anchor="end" class="event-label" fill="#ab4433">Fail</text>
    <rect x="356" y="412" width="416" height="36" fill="var(--paper)" />
    <text x="564" y="437" text-anchor="middle" class="repair-label" fill="#ab4433">Changes needed · author updates PR</text>
  </svg>
</template>

<style scoped>
.owner-label { font-size: 26px; font-weight: 650; }
.guidance-label { font-size: 25px; }
.diagram-label { font-size: 30px; }
.diagram-note { font-size: 22px; }
.repair-label { font-size: 23px; }
.source-label { font-size: 26px; font-weight: 550; }
.event-label { font-size: 21px; }
.approval-label { font-size: 25px; font-weight: 550; }
</style>
