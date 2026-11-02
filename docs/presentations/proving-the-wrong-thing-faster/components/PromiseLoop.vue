<template>
  <svg class="promise-loop" viewBox="0 0 1152 280" role="img" aria-labelledby="loop-title loop-desc">
    <title id="loop-title">Iterative formalization</title>
    <desc id="loop-desc">AI proposes a candidate property from intent. Checks, counterexamples, questions, and stakeholder feedback inform another refinement.</desc>
    <defs>
      <marker id="loop-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
        <path d="M0,0 L8,4 L0,8" fill="#126655" />
      </marker>
    </defs>
    <g fill="none" stroke="#126655" stroke-width="2.5" marker-end="url(#loop-arrow)">
      <path d="M260 91 H431" />
      <path d="M700 91 H871" />
      <path d="M1012 150 V215 Q1012 232 995 232 H157 Q140 232 140 215 V157" />
    </g>
    <rect x="0" y="32" width="260" height="118" rx="8" fill="#182a36" />
    <rect x="440" y="32" width="260" height="118" rx="8" fill="#e4ece4" stroke="#b8cbbf" />
    <rect x="880" y="32" width="264" height="118" rx="8" fill="#e4ece4" stroke="#b8cbbf" />
    <g text-anchor="middle" class="diagram-label">
      <text x="130" y="103" fill="#f6f3eb">Intent</text>
      <text x="570" y="84">Candidate</text>
      <text x="570" y="119">property</text>
      <text x="1012" y="103">Checks</text>
    </g>
    <text x="350" y="65" text-anchor="middle" class="diagram-note" fill="#126655">AI proposes</text>
    <rect x="267" y="212" width="618" height="40" fill="#f6f3eb" />
    <text x="576" y="240" text-anchor="middle" class="diagram-note" fill="#52616b">Questions · counterexamples · stakeholder feedback</text>
  </svg>
</template>
