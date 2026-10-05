# Thread page refinement review

## Delivered behavior

Post-delivery correction: the user requested a permanently visible brand
artwork. It is restored as a normal section; history, directory and diagnostics
keep their compact behavior. The collapsed-artwork screenshots below record
the earlier layout, not this final preference.

The model toolbar and repeated current-model tab are removed. The topology
heading keeps the model identity. Framework artwork, model history and view
diagnostics use disclosures. Historical/selected-instruction notices remain
visible. The registered model directory opens on demand, supports name/ID
search and engine filtering, and keeps explicit opening through the existing
Thread command path. Hidden or unavailable selections cannot be opened.

The header GitHub link shows only the SVG, with its original destination,
accessible name and tooltip. Message actions retain their layout space while
fading on hover/focus; phone actions are visible, wrap and use44px targets.
Long answer identifiers and model names wrap.

## Verification

- App227 tests passed across21 files. TypeScript/Vite build passed.
- Local playwright-cli: direct preset, directory-based RTS opening, real AC
  flow, rank-only follow-up, old-answer graph, latest graph and historical
  read-only return passed using isolated finite Pi sessions and actual gridctl.
- Browser directory filtering also used the bounded81-model catalog read from
  the normal local API. PyPSA filtering and empty search passed; no PyPSA turn
  was sent through the isolated pandapower worker.
- Desktop1600×1050, compact900×900 and phone390×844 screenshots were inspected.
  No page horizontal overflow; phone actions meet44px; long text is not clipped.
  The same answer measured166.546875px high before and after hover.
- Final `make capstone-local-rebuild`, readiness, App200 and matching API/worker/
  worker-pypsa images passed. `make doctor`, relative CLAUDE symlink and diff
  checks passed. Existing user Thread remainedIEEE39/cursor76 during read-only
  verification.
- Independent source review approved the final diff with no open findings.
  Its initial phone-rule precedence finding was corrected and rechecked.

Receipts: ignored `runs/capstone-page-refinement/`. Screenshots: ignored
`output/playwright/thread-page-*.png`. The isolated browser assembly has two
known preview404 console errors because it omits the legacy Case preview
endpoint. This review does not claim a clean console for that assembly.

All test-only servers, CLI session and temporary auth file were removed.
Normal local ports8767/5173 remain available. No external Provider, cloud
deployment, authority change or user-history rewrite occurred. Prior full
release checks belong to the earlier instruction-view repair, not this
presentation-only change.
