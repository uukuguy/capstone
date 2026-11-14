# Report delivery repair implementation plan

**Goal:** Repair the saved summer-report case and enforce the accepted template
library failure contract: requested rendering without confirmed files cannot
be reported as completed.

**Architecture:** Publish the renderer's content contract and actionable errors.
The application host tracks actual presentation requests and checks receipts
against collected artifact hashes before completion. No Kernel policy, topic
routing, new ledger, business fact generation or source-query replay.

This implements the failure behavior in the accepted
[template-library design](../specs/2026-11-08-presentation-template-library-design.md)
and the user's direct instruction to fix the observed failure.

## Executable content contract

- [ ] Add failing contract/field/section diagnostic tests to existing renderer
  and presentation SDK tests; reproduce the saved input failure.
- [ ] Add renderer `--contract` and tool `operation=contract`, with supported
  formats, role defaults and a complete agenda/section example. Keep strict
  field checks and return precise locations and missing/unknown names.
- [ ] Run focused checks and commit the verified unit.

Files: tools/native_presentation_library.py, tools/native_report.py,
presentation-templates.mjs and their existing focused tests. No new dependency.

## Truthful product completion

- [ ] Add failing host tests for render rejection, missing requested PDF,
  success claims without saved bytes, and successful repair of the same source.
- [ ] Track render starts/results in the existing task record. Verify the last
  request for each source spec/bundle against collected artifact hashes.
- [ ] Preserve files on failure; propagate the named required-product failure
  through the existing fatal receipt path. Ordinary data/tool errors retain
  their current limited-answer behavior.
- [ ] Run host/application-consumer checks and commit the verified unit.

Files: general_pi_server.py, native_product_roles.py, delegated_runtime.py,
failure_delivery.py and their existing tests. Keep public codes allowlisted.

## Recovery and deployment

- [ ] Hash-check saved slides/CSVs/figures, preserve original versions and data
  gaps. Recover under new names without inventing a current-year analysis.
- [ ] Canonical local rebuild; bounded real model verification using saved
  inputs only, successful products, truthful failure and refresh.
- [ ] Deploy the exact source to dky3-dev, preserve configuration/data/backups;
  verify saved-input recovery and products. Keep failed attempt history intact.
- [ ] Update receipts, canonical state and graph. CI remains unapproved; extend
  only the affected focused route and do not create a PR that starts CI.
