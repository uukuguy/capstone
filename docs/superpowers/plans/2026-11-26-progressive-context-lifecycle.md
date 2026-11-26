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
| Gateway identity and exact continuation | `gateway-integrated-matrix.json`, `joint-gateway-next-page.json`, `four-context-restart-next-page.json`, `joint-gateway-binding-gap.json`; restored-view expiry regression | A signed view expired after 60 seconds on a dedicated synthetic gateway. The 5174 continuation used the original reference, received `view_expired` and made no recovery dispatch. See `natural-ttl-expiry.json`. |
| File delivery from admitted evidence | `gateway-evidence-report-fields-1.json`, `gateway-evidence-report-fields-2.json` | Both Word reports matched the saved values and hashes with no new gateway dispatch. Optional conversion still occurred in some samples. |
| Offline diagnosis | `model-context-handoff-verification.json`, `joint-gateway-handoff-verification.json`, `history-selection-handoff-verification.json` | The original-call projection is available for the dedicated synthetic gateway. Deployments without registered evidence report a gap. |
| Per-type cost and instruction fit | `matched-enforced-ceiling.json`, `matched-contract-plan.json`, `gateway-integrated-matrix.json`, `gateway-short-preview.json` | Initial gateway discovery has mixed cost. Compare again on the promotion revision before enabling a broader rollout. |

The rollback switch is `CAPSTONE_THIN_INITIAL_CONTEXT`. Record promotions
separately from local checks. Keep the control available until the per-type
performance disposition has been accepted.

The candidate at `fd4efd52` passed both short-task sequences in
`acceptance-current.json`. The latest Word evidence replay passed its hashes
and facts with no gateway dispatch in `acceptance-report-current.json`, while
the request count rose to nine. The PPTX smoke in `acceptance-ppt-current.json` passed the slide count, text
and hash checks with the legacy guide flag off. The thin-mode guide then
loaded on demand in `thin-guides-ppt.json`. Its default cover caused the
explicit one-slide request to fail. After the renderer and guide accepted
explicit cover omission, `thin-single-slide.json` passed completion, slide
count, text and download hash at `c8815c3d`. It used six model calls and
rendered twice, so the delivery pass does not establish a cost improvement.

At `6b1723a7`, `thin-guides-ordinary.json` passed without guide calls.
`thin-guides-gateway.json` loaded the gateway guide on the first turn and
reused the contract on a narrower-window follow-up. Both calls matched the
requested arguments and saved values. Record PPTX cost alongside Word
delivery and initial gateway discovery on the promotion revision.

Same-image comparison at `c8815c3d` is recorded in
`matched-acceptance-c881.json`. Both modes passed the window, source values
and downloaded report checks. Neither report queried the gateway again.
The figures below are one matched pair per case.

| Case | Model calls, control to thin | Uncached input tokens, control to thin | Elapsed seconds, control to thin |
| --- | --- | --- | --- |
| Single-slide PPTX | 5 to 5 | 10,816 to 4,794 | 13.93 to 8.04 |
| First gateway query | 4 to 5 | 15,648 to 20,613 | 9.60 to 9.31 |
| Narrower window | 5 to 3 | 13,971 to 9,437 | 12.71 to 7.67 |
| Word report from saved evidence | 4 to 5 | 11,392 to 6,410 | 19.21 to 14.79 |

Two additional thin PPTX runs each made one render and passed download
verification. The first-query path still adds a model call and uncached
input in this pair. The thinner prefix also reduced cached input in all
four cases. Use the receipt's separate cache counters when comparing cost.

At `9d426e77`, both cold query trials skipped the long guide but still took
five requests. Both narrower-window turns preserved the expected arguments
and avoided describing the view again. One initial call lacked a timezone
offset and required correction. The published exact schema accepted both
forms. See [the gateway window contract handoff](../../reports/2026-11-27-gateway-view-window-contract-handoff.md)
and `thin-bounded-guide.json`.


At `09afb501`, both four-candidate trials completed the first query and
the narrower window with exact parameters and matching values. The first
queries took five and six calls. Uncached input was 14,622 and 15,180 tokens,
versus 21,263 and 19,412 in the previous two samples. The follow-ups took four
and three calls with one gateway dispatch each. This cross-revision comparison
measures payload reduction with variable turn count. See
`thin-four-candidates.json` and `four-candidate-attribution.json`.

The same revision passed a synthetic gateway continuation after Pi service
restart. The first request returned SYN000. The next turn read the saved
observation and sent the exact arguments in its next-page action. It returned
SYN001. Each turn made one dispatch. The live check covers an offset carried
in the gateway action. The isolated restored-view regression covers expired
opaque view references.

Two new control threads on the same `09afb501` image complete the comparison
in `matched-four-candidates.json`. Both first queries in each mode sent exact
arguments and returned the required data. First-query calls averaged 5.5 in
both modes. Mean uncached input fell from 16,035 to 14,901 tokens. Elapsed
time ranged from 9.71 to 12.74 seconds in control and 11.41 to 13.52 seconds
in thin mode. This sample supports smaller input. It shows variable elapsed
time and no first-query call reduction.

The thin follow-ups took 4 and 3 calls and each made one correct gateway
dispatch. Control took 6 and 4 calls. One control follow-up needed a second
dispatch after the timezone-free argument rejection. All final values
matched. Cached token counts and individual elapsed times remain in the
receipt. These measurements cover the local model profile and gateway
publication. The same image was restored to thin mode after the comparison.

The deployment default remains `CAPSTONE_THIN_INITIAL_CONTEXT`. Set
`CAPSTONE_THIN_CONTEXT_PROFILES` to a JSON object from registered profile IDs
to booleans for individual overrides. For example,
`{"commercial-deepseek-flash":false}` rolls that profile back when the global
default is enabled. Omitted profiles use the global default. The override
changes task admission without changing the frozen model identity.


At `21c4f796`, Thread `thr_1af396e8814dda5a018a` used a separate SQLite
synthetic gateway with a 60-second signed-view lifetime. The first turn
followed the preparation job and obtained a ready view. The next turn waited
past its recorded expiry and made one devices read with the original signed
reference. The gateway returned `view_expired`. No reopen or source refresh
was dispatched. The evidence receipt retains the reference digest and the
verified argument match.

At `fff316b1`, the combined gateway and automatic compaction test in
`fixed-gateway-compaction.json` returned SYN000 before compaction and SYN001
on the next instruction. The host resolved the retained observation and
copied the entire next-page argument object, including explicit null filters
and ordering. Each instruction made one gateway dispatch. The prior direct
model call returned the expected row but omitted those fields. The fix
merged in PR 294 and the temporary profile was removed from local-dev.
