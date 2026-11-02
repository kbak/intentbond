<script setup>
defineProps({
  reference: String,
  tone: String,
});
</script>

<template>
  <div class="property-statement" :class="tone">
    <code>expired ↔ now − <strong>{{ reference }}</strong> ≥ 30 min</code>
  </div>
</template>
