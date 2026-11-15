# Harness chain verification plan

Owner: capstone-agent/capstone-app. Destination: dev. User approved the
end-to-end verification scope. No implementation branch is active for this
verification slice. Existing closeout receipts remain outside its ownership.

Goal: establish current behavior with one real task and its continuation before
selecting a justified execution-chain change.

- [x] Map submission, Harness admission, native events and App restoration seams.
- [x] Run focused Harness/step/bridge and App projection/progress checks.
- [x] Submit a real simulated CSV/report task through the existing local API.
- [x] Continue the same Work, preserve originals and generate derived products.
- [x] Download products and verify sizes, digests and independent CSV totals.
- [x] Trace copied-product source lineage against the existing series contract.
- [x] Reuse an existing Capstone browser tab to check products and refresh.
- [ ] Select a concrete failure/cancellation/recovery slice from measured gaps.

Evidence and limits: [baseline report](../../capstone-app/2026-11-15-harness-chain-baseline.md).
Any behavior change first needs a regression reproducer and an exact scoped
implementation plan. Local source changes require the canonical rebuild before
runtime validation. CI remains prohibited without fresh explicit approval.
