<template>
  <div class="future-directions" role="list" aria-label="Future research and product directions for IntentBond">
    <section role="listitem">
      <h2>Empirical evaluation</h2>
      <p>Measure intent preservation, effort, and cost.</p>
    </section>
    <section role="listitem">
      <h2>Requirements discovery</h2>
      <p>Use concrete behaviors to clarify intent.</p>
    </section>
    <section role="listitem">
      <h2>Semantic change analysis</h2>
      <p>Detect weakened properties and changed assumptions.</p>
    </section>
    <section role="listitem">
      <h2>Production feedback</h2>
      <p>Link intent and decisions to their observed effects.</p>
    </section>
  </div>
</template>

<style scoped>
.future-directions { margin-top: 56px; }
.future-directions section { display: grid; grid-template-columns: 360px minmax(0, 1fr); gap: 32px; align-items: center; min-height: 108px; border-bottom: 1px solid var(--line); }
.future-directions h2 { margin: 0; color: var(--teal); font-size: 31px; font-weight: 600; line-height: 1.3; letter-spacing: -0.5px; }
.future-directions p { margin: 0; font-size: 30px; font-weight: 400; line-height: 1.35; }
</style>
