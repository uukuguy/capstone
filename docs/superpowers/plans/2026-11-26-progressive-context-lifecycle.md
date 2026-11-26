# Progressive context implementation

1. Extend request observation in general-sdk.mjs and preserve the fields in
   general_pi_server.py. Test window and output allowance in the native
   context receipt test. Extend provider timing at the dispatch boundary.
2. Connect the current Thread state and admitted references to the existing
   request projection. Verify parameter and revision matching, dependencies,
   and stable ordering with identical inputs.
3. Apply the profile budget to the assembled request. Bound optional
   projections first. Exercise automatic compaction, restart and recovery
   through ordinary execution with a small model window.
4. Compare matched control and candidate runs using the design's instruction
   matrix. Check actual dispatch content against expected context and final
   products against tool receipts. Record per-type quality and cost before
   changing rollout defaults.

## Local acceptance evidence

Run the current candidate through the ordinary Thread entry point at port 5174.
Keep the model profile and image fixed within each control/candidate pair. The
following receipt names refer to the private local directory
`runs/progressive-context-5174/`. They are excluded from Git because they can
contain source observations and conversation excerpts.

| Requirement | Verified evidence | Remaining qualification |
| --- | --- | --- |
| Context selection and order | `explicit-history-selection.json`, `history-preview-only-dispatch-audit.json`, `same-topic-strong-dispatch-audit.json` | Exact IDs take precedence. Lexical ranking stays bounded and may defer bodies to on-demand reads. The same-topic replay still exposed old values in a preview. |
| Request budget and cache | `context-estimator-calibration.json`, `real-context-limit-encoding.json`, `prefix-usage.json` | The current encoder allowance is calibrated on local samples. First content and provider prefill are distinct. This provider did not report prefill. |
| Compaction and recovery | `real-context-compaction-verified.json`, `real-context-limit-encoding.json`; pinned SDK summary failure regression | Live threshold compaction, an oversized instruction and restart were exercised. Summary failure was injected in the pinned SDK test. |
| Gateway identity and exact continuation | `gateway-integrated-matrix.json`, `joint-gateway-next-page.json`, `joint-gateway-binding-gap.json`; restored-view expiry regression | Gateway reference expiry was exercised at the isolated gateway and relay boundaries. A naturally expired reference remains unverified in local-dev. |
| File delivery from admitted evidence | `gateway-evidence-report-fields-1.json`, `gateway-evidence-report-fields-2.json` | Both Word reports matched the saved values and hashes with no new gateway dispatch. Optional conversion still occurred in some samples. |
| Offline diagnosis | `model-context-handoff-verification.json`, `joint-gateway-handoff-verification.json`, `history-selection-handoff-verification.json` | The original-call projection is available for the dedicated synthetic gateway. Deployments without registered evidence report a gap. |
| Per-type cost and instruction fit | `matched-enforced-ceiling.json`, `matched-contract-plan.json`, `gateway-integrated-matrix.json`, `gateway-short-preview.json` | Initial gateway discovery has mixed cost. Compare again on the promotion revision before enabling a broader rollout. |

The rollback switch is `CAPSTONE_THIN_INITIAL_CONTEXT`. Record promotions
separately from local checks. Keep the control available until the per-type
performance disposition has been accepted.

The candidate at `fd4efd52` passed both short-task sequences in
`acceptance-current.json`. The latest Word evidence replay passed its hashes
and facts with no gateway dispatch in `acceptance-report-current.json`, while
the request count rose to nine. The PPTX smoke in `acceptance-ppt-current.json`
passed the slide count, text and hash checks. It did not load the distinct
presentation guide. The live guide flag was off. Verify the presentation
admission and on-demand guide path before closing the guide requirement.
