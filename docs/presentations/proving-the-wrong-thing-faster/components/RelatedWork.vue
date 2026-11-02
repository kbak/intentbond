<template>
  <div class="related-work">
    <table aria-label="Direct comparison of related tools with IntentBond">
      <colgroup><col class="tool-column"><col class="alternative-column"><col class="intentbond-column"></colgroup>
      <thead><tr><th>Related tool</th><th>Their approach</th><th>How IntentBond differs</th></tr></thead>
      <tbody>
        <tr><th scope="row"><a href="https://github.com/OathTech/covmap">Covmap</a></th><td>Tracks mapping coverage and drift</td><td>Requires implementation and test links</td></tr>
        <tr><th scope="row"><a href="https://tracey.bearcove.eu/guide/ai-integration/">Tracey</a></th><td>Links requirements to code/tests</td><td>Links and aligns intent with requirements</td></tr>
        <tr><th scope="row"><a href="https://github.com/Looted/kibi">Kibi</a></th><td>Builds a structured knowledge base</td><td>Links existing docs, code &amp; tests</td></tr>
        <tr><th scope="row"><a href="https://github.com/spolu/code-contracts">Code Contracts</a></th><td>Guides agents with prose contracts</td><td>Runs checks and records evidence</td></tr>
        <tr><th scope="row"><a href="https://openspec.dev/">OpenSpec</a></th><td>Agent infers correspondence</td><td>Maintains and checks versioned links</td></tr>
      </tbody>
    </table>
    <div class="foundation"><a href="https://github.com/itsallcode/openfasttrace">OpenFastTrace</a> machinery + agent guidance + execution + review</div>
    <div class="usage">Open source · inline or external mappings · standalone / CI / factories</div>
  </div>
</template>

<style scoped>
.related-work { margin-top: 38px; }
table { width: 100%; table-layout: fixed; border-collapse: collapse; font-size: 23px; line-height: 1.25; margin: 0; }
.tool-column { width: 205px; }
.alternative-column { width: 450px; }
th, td { text-align: left; padding: 20px 20px; border-bottom: 1px solid var(--line); vertical-align: middle; }
th:first-child { padding-left: 0; }
thead th { padding-top: 0; padding-bottom: 14px; color: var(--muted); font-size: 21px; font-weight: 500; }
tbody th { font-weight: 600; color: var(--teal); }
td:last-child { background: #e5ece3; }
thead th:last-child { color: var(--teal); font-weight: 600; }
.foundation { margin-top: 28px; font-size: 23px; line-height: 1.3; }
.usage { margin-top: 20px; font-size: 23px; color: var(--muted); }
</style>
