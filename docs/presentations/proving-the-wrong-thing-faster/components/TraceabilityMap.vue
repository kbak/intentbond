<template>
  <svg class="traceability-map" viewBox="0 0 1152 250" role="img" aria-labelledby="trace-title trace-desc">
    <title id="trace-title">One promise connected through a change</title>
    <desc id="trace-desc">The goal of limiting idle access informs a thirty-minute inactivity requirement. That requirement is linked to expiration logic and boundary tests, with evidence and review retained for the change. The session requirement, logic, and tests are real IntentBond example artifacts; goal and review are conceptual workflow context.</desc>
    <defs>
      <marker id="trace-arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto-start-reverse">
        <path d="M0,0 L7,3.5 L0,7" fill="#126655" />
      </marker>
    </defs>
    <g stroke="#126655" stroke-width="2" marker-start="url(#trace-arrow)" marker-end="url(#trace-arrow)">
      <line x1="242" y1="125" x2="294" y2="125" />
      <line x1="552" y1="125" x2="604" y2="125" />
      <line x1="862" y1="125" x2="914" y2="125" />
    </g>
    <rect x="0" y="42" width="230" height="166" rx="8" fill="#e4ece4" stroke="#b8cbbf" />
    <rect x="306" y="42" width="234" height="166" rx="8" fill="#182a36" />
    <rect x="616" y="42" width="234" height="166" rx="8" fill="#e4ece4" stroke="#b8cbbf" />
    <rect x="926" y="42" width="226" height="166" rx="8" fill="#e4ece4" stroke="#b8cbbf" />
    <g text-anchor="middle" class="diagram-label">
      <text x="115" y="115">Limit idle</text><text x="115" y="151">access</text>
      <text x="423" y="115" fill="#f6f3eb">30 min of</text><text x="423" y="151" fill="#8be1c5">inactivity</text>
      <text x="733" y="115">Expiration logic</text><text x="733" y="151">Boundary tests</text>
      <text x="1039" y="115">Evidence</text><text x="1039" y="151">Review</text>
    </g>
  </svg>
</template>
