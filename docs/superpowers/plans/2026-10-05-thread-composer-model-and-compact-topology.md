# Composer model menu and compact topology plan

**Goal:** Put model selection beside input settings and give the topology a denser control area with a proportionate canvas.

**Architecture:** Reuse the typed directory and existing Thread command path in the existing Composer control slot. Add an optional compact NetworkView presentation for Thread; legacy Case presentation remains governed by its existing layout.

**Design:** A borderless model icon/text/caret trigger sits beside Settings in the Composer footer. Its bounded panel opens upward and retains catalog search, family filtering, explicit switch, unavailable/history/running guards, Escape and outside dismissal. Menu keyboard events cannot send the Composer draft. The left pane keeps brand artwork, one9px description paragraph (one size below the previous10px), optional model history, and the topology. The topology has a title/model/ordinal row and a source/count/control row, icon zoom/fit/focus controls with accessible labels, a width-based canvas and compact provenance legend. Phone controls wrap and keep44px targets. Authority coordinates, numerical facts and instruction ownership are unchanged.

## Tasks

User refinements: group directory rows by engine and naturally sort model IDs;
show IDs first. Match the Composer toolbar's10px font in the entire popup and
reduce padding. Size popup height against the actual clipping ancestor as well
as the viewport. Keep phone controls44px despite compact text and spacing.

- [x] Add meaningful regression coverage for placement, menu dismissal and draft isolation; preserve catalog and switch tests.
- [x] Move directory composition from ThreadModelPane to ThreadFixtureApp's Composer controls. Refine its trigger/panel and remove obsolete pane props.
- [x] Add compact NetworkView controls and scoped CSS. Merge introductory descriptions into one paragraph.
- [x] Run focused then full App tests/build. Inspect local desktop, compact and phone views, including open menu, model activation and instruction graph switching.
- [x] Use the checked-in local rebuild, verify readiness, review the changes, record evidence and commit task-owned paths.

Verification: [review](../../reviews/2026-10-05-thread-composer-model-and-compact-topology.md).

Checks: `npm test --prefix packages/capstone-app`,
`npm run build --prefix packages/capstone-app`, `make capstone-local-rebuild`,
`git diff --check`. Receipts go under ignored `runs/capstone-page-refinement/`;
screenshots go under ignored `output/playwright/`.
