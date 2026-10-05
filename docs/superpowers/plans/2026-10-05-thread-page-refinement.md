# Thread page refinement implementation plan

**Goal:** Reduce repeated model information, keep the grid prominent, and show only the GitHub icon in the header.

**Architecture:** Presentation changes in the React App. Registered catalog data and existing Thread commands remain the model-selection boundary. Instruction graph selection remains local presentation state.

**Tech stack:** React, TypeScript, existing CSS, Vitest, local playwright-cli.

## Design and scope

User correction after delivery: keep the brand artwork permanently visible.
Only model history and view diagnostics use disclosures; the directory still
opens on demand.
The next user correction restores the original Case-page CAPSTONE description
below the artwork and adds a compact description of the Thread conversation,
natural-language model opening, analysis and answer-linked grid/evidence views.

The user now authorizes the model-area simplification deferred in the
[instruction-view plan](2026-10-05-thread-preset-ranking-and-task-view.md).
Keep one model identity in the topology heading. Move the model selector into
an on-demand directory with text search and implementation-family filtering.
Show historical-model navigation only when history exists, behind a compact
disclosure. Fold framework artwork and technical Context/selection/cursor
information into separate disclosures. Historical and selected-instruction
notices remain visible because they explain the current graph and send limits.
The header link keeps its destination and accessible name but shows only its SVG.

The [approved Web contract](../specs/2026-10-01-capstone-thread-web-ui-main-contract.md)
and recent user requests still require direct preset execution, per-answer
graph actions, readable Markdown, compact Composer, and responsive layout.
Reserve message-action space so hover/focus does not change message height;
use 44px action targets and allow wrapping on phones.
These are existing behavior to verify, not new backend work. Earlier active
architecture discussions and Provider/cloud follow-ups are outside this layout
change. No authority fact, model registration, command, or saved user history
may be fabricated or rewritten.

## Tasks

- [x] Add tests for an initially closed directory, search/family filtering,
  unavailable models, and the existing switch/history command guards.
- [x] Add `ThreadModelDirectory.tsx`; consume typed registered models and
  existing target/change/switch callbacks. Keep filtering local and opening
  explicit. Render a bounded scroll area and a helpful empty state.
- [x] Refine `ThreadModelPane.tsx` and `styles-light.css`: collapsed artwork,
  directory/history controls, one topology identity, collapsed diagnostics.
- [x] Make `AppHeader.tsx` icon-only with accessible name and title.
- [x] Run App tests and TypeScript/build; inspect desktop and phone with local
  playwright-cli, including filters, history and instruction-view controls.
- [x] Rebuild the actual local entry point with `make capstone-local-rebuild`;
  verify readiness and App availability, review source, update durable state,
  and commit only task-owned files.

Verification commands: `npm test --prefix packages/capstone-app`,
`npm run build --prefix packages/capstone-app`, `make capstone-local-rebuild`,
`make doctor`, and `git diff --check`. Screenshot receipts live in ignored
`output/playwright/`; operational receipts live in ignored `runs/`.
