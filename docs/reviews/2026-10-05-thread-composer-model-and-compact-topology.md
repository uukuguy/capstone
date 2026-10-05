# Composer model menu and compact topology review

## Delivered behavior

The model directory opens beside Settings in the Composer footer. Search,
engine filtering and explicit model activation use the existing typed catalog
and Thread command path. Rows sort by engine and natural model ID; IDs appear
first. The panel, search, filters and rows use10px text, matching the Composer
toolbar, with smaller padding and gaps. Its scrollable height follows the
Composer and clipped card bounds, including short windows and resize.

Escape restores trigger focus. Outside interaction and opening Settings close
the panel. Enter in search cannot submit the conversation draft; Enter on the
switch button still activates the model. Existing history, unavailable-model
and running-state guards remain enforced.

The brand image stays visible. Its introduction is one9px paragraph. The left
pane no longer has a model directory button. Thread topology uses a compact
heading and metadata/control row, labelled icon controls and a width-based
canvas. Phone controls retain44px touch targets. Authority coordinates,
numerical overlays and answer-owned graph selection retain their contracts.

## Verification

- App230 tests across21 files passed; TypeScript/Vite build passed. The existing
  large-chunk build warning remains.
- Independent source review approved the final diff and reran67 focused tests.
  Short-window menu clipping and a phone switch-target size defect found
  during review were fixed and rechecked.
- Local playwright-cli checked1600×1050,900×900,390×844 and1440×600 views.
  Screenshots were inspected. The image and single9px paragraph are visible;
  menu and trigger both compute10px. No page horizontal overflow was observed.
- Menu search, natural sorting, outside dismissal, Escape focus, draft
  isolation and switch-button Enter passed. The short-window menu stays within
  its clipping boundary and scrolls internally.
- An isolated finite Pi session with real gridctl verified direct preset,
  directory activation of RTS, AC flow, rank-only follow-up, previous-answer
  graph selection and return to the current graph. Model/context identities
  and numerical projections came from the authority.
- Final `make capstone-local-rebuild` passed. Readiness, App HTTP200 and the
  registered81-model catalog passed. API, worker and worker-pypsa share image
  `sha256:8a6f6311c6489d43cfed768ca4024b05a71c8d220dc58acc070b3400f1845bdd`.
  Read-only inspection found the original user Thread atIEEE39/cursor76.
- `make doctor`, relative CLAUDE symlink, documentation links and
  `git diff --check` passed.

Receipts are under ignored `runs/capstone-page-refinement/compact-*` and
`local-runtime.json`. Screenshots are under ignored
`output/playwright/thread-compact-*.png`. The isolated browser assembly omits
the legacy Case preview endpoint and emits two known404 console errors.
Finite sessions do not validate arbitrary Provider planning.

Test-only servers18761/18762, both task browser sessions and their temporary
auth file were removed. Normal local API8767 and App5173 remain available.
No external Provider, cloud deployment, authority change or user-history
rewrite occurred. This is an App presentation check, not a new release gate.
