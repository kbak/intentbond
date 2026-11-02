<script setup>
import { useId } from "vue";

defineProps({ refined: Boolean });
const id = useId();
</script>

<template>
  <svg
    class="session-timeline"
    :class="{ 'is-refined': refined }"
    viewBox="0 0 1152 180"
    role="img"
    :aria-labelledby="`${id}-title ${id}-desc`"
  >
    <title :id="`${id}-title`">
      {{ refined ? 'The inactivity timer preserves the active session' : 'The login timer expires a recently active session' }}
    </title>
    <desc :id="`${id}-desc`">
      Login at minute zero, activity at minute twenty-five.
      {{ refined ? 'Still active at minute thirty; expires at minute fifty-five if there is no further activity.' : 'Incorrect expiration at minute thirty, after only five minutes of inactivity.' }}
    </desc>
    <defs>
      <marker
        :id="`${id}-arrow`"
        markerWidth="8"
        markerHeight="8"
        refX="7"
        refY="4"
        orient="auto"
      >
        <path d="M0,0 L8,4 L0,8" fill="#a9b6bd" />
      </marker>
    </defs>
    <line
      x1="60"
      y1="82"
      x2="1090"
      y2="82"
      stroke="#a9b6bd"
      stroke-width="2"
      :marker-end="`url(#${id}-arrow)`"
    />
    <path class="wrong-interval" d="M60 82 H590" fill="none" stroke="#ce543e" stroke-width="6" />
    <g class="intended-interval" :aria-hidden="!refined">
    <path
      d="M500 82 H1040"
      fill="none"
      stroke="#16816f"
      stroke-width="6"
      stroke-dasharray="8 7"
    />
    <path
      d="M500 52 V32 H1040 V52"
      fill="none"
      stroke="#16816f"
      stroke-width="2"
    />
    <text
      x="770"
      y="23"
      text-anchor="middle"
      fill="#126655"
      style="font-size: 18px"
    >
      30 min of inactivity
    </text>
    </g>
    <circle cx="60" cy="82" r="8" fill="#182a36" />
    <circle
      cx="500"
      cy="82"
      r="8"
      :fill="refined ? '#16816f' : '#182a36'"
      stroke="#f6f3eb"
      stroke-width="3"
    />
    <circle
      cx="590"
      cy="82"
      r="11"
      :fill="refined ? '#16816f' : '#ce543e'"
      stroke="#f6f3eb"
      stroke-width="3"
    />
    <circle class="intended-interval" cx="1040" cy="82" r="8" fill="#16816f" />
    <text x="60" y="119" text-anchor="middle" class="timeline-time">00:00</text>
    <text x="60" y="148" text-anchor="middle" class="timeline-label">
      Login
    </text>
    <text x="470" y="119" text-anchor="end" class="timeline-time">25:00</text>
    <text x="470" y="148" text-anchor="end" class="timeline-label">
      Activity
    </text>
    <text x="608" y="119" class="timeline-time" :fill="refined ? '#126655' : '#b54633'">30:00</text>
    <text x="608" y="148" class="timeline-label" :fill="refined ? '#126655' : '#b54633'">
      {{ refined ? 'Still active' : 'Wrong expiry' }}
    </text>
    <g class="intended-interval" :aria-hidden="!refined" fill="#126655">
    <text x="1040" y="119" text-anchor="middle" class="timeline-time">
      55:00
    </text>
    <text x="1040" y="148" text-anchor="middle" class="timeline-label">
      Expires
    </text>
    </g>
  </svg>
</template>
