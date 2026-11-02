# Proving the Wrong Thing, Faster

A 12-minute talk by Kacper Bak on intent, validation, and keeping requirements aligned as software evolves. The Slidev deck contains a holding screen, twelve main slides, and four extra slides.

## Present and export

Run these commands from this directory with Node.js and npm installed. The
presentation toolchain is separate from IntentBond's Python setup.

```sh
npm ci
npm run dev
```

Open the printed URL. Use `Space` / `Right` to advance and presenter view for speaker notes and timing.

```sh
npm run build
npx playwright install chromium  # once, if needed
npm run export
```

The static build is in `dist/`; serve it over HTTP. The PDF is [exports/proving-the-wrong-thing-faster.pdf](exports/proving-the-wrong-thing-faster.pdf), with 31 pages covering 17 slides and 14 reveal steps. Export already uses `--with-clicks`; do not add `--per-slide`, which skips reveals in the installed Slidev 53 print mode. To use an existing browser:

```sh
npm run export -- --executable-path /absolute/path/to/chromium
```

Fonts, diagrams, and the favicon are bundled locally. Only opening external source links needs a connection.

## Editing

- [slides.md](slides.md): slide content, source links, speaker notes, and timing.
- [style.css](style.css): colors, typography, and layout styles.
- [layouts/talk.vue](layouts/talk.vue): shared slide frame and numbering.
- [components/](components/): diagrams and interactive examples.
- [public/](public/): fonts, licenses, favicon, and IntentBond QR code.
- [evidence/slide-8-feedback.json](evidence/slide-8-feedback.json): retained output for the check/repair example.

Keep the Unicode escapes in the evidence JSON: they preserve the recorded strings
while preventing OFT from treating historical annotations as live product links.

The talk moves from a verified misunderstanding to evolving requirements, then IntentBond’s Connect → Guide → Validate → Refine workflow, future work, and continuous alignment. Keep each projected slide understandable without its notes; put extended references and qualifications in the notes. After editing, rebuild and refresh the PDF, checking all reveals and text for clipping.

## Scope and references

The session example illustrates an intent-to-specification error; no session proof is claimed. Passing trace and test checks does not establish semantic correctness or acceptance: the repair example still requires review. Lean, Alloy, and SMT illustrate refinement options, not an implemented prose-to-verified-software pipeline.

Sources and related work are linked in the speaker notes. See also the [IntentBond README](../../../README.md), [development-review contract](../../development-review.md), [property-testing guide](../../property-testing.md), and [model-checking guide](../../model-checking.md).
