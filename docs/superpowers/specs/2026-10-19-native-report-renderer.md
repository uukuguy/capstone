# Native report renderer: accepted bounded candidate

## Current successor checkpoint — 2026-10-19 05:20 CST

The renderer trials remain failed-quality evidence, not an accepted baseline.
The successor independent-review path is now offline verified and locally
deployed on backend 04030070 / native a8c31c5b; new real quality and overhead
validation are pending. Full identities and current checks are in the
[delivery-review plan](../plans/2026-10-19-delivery-review.md).
Earlier deployment/source checkpoints below are historical.


**Status:** User direction accepted; renderer locally deployed and functionally
verified. Canonical rebuild /tmp/native-report-rebuild.log exited zero. API and
three workers use image 4553721e20ab922d89ba7f77e9c5db554a292a4ae1a1afe9d8cc600f1a103dd3;
native uses 8ccd4e9af7713610073123bea2520aa4e91cc478c7a3ea5aa04594f7594be9a0.
Actual non-root UID 65534 used the PATH launcher to generate a CSV + SVG report,
preserving 79.37% / 001 strings and valid TOC anchors. Host/root-only receipt
reading and helper context passed. Context 10 tests, combined renderer/environment
33 tests and one actual-SDK offline split-only test passed; do not sum overlapping
scopes. Prior staged smoke remains separate evidence.

Both real trials have now completed without quality acceptance. First draft:
304.280305 s / 37 parent / 0 child / 39 tools / 11 failures; 869 numeric
comparisons passed, but prose, captions and timezone claims failed. Natural
revision attempt_e50328c5e341f630 took 553.179527 s / 68 parent responses.
All 36 files passed integrity checks; 345 recomputations produced 337 passes and
eight failures. Denominator/coverage, aggregation, caption and correlation errors
remain. These checks have different scopes and are not additive. The earlier
350.524 s / 41-response reference stays unchanged. Independent evidence is in
ROOT/outputs/research-round-efficiency/enterprise-question-cycle/
thr_19f3d38d9a4a6eacf1cc/revisions/attempt_e50328c5e341f630/independent-content-check.md.
The next independent-review candidate is implementing, not deployed.

## Problem and evidence

Thread `thr_425aec0650141837cbf6`, Attempt `attempt_c7b63063f74a71d6`, completed
from 2026-10-18T19:44:21.370670Z to 19:51:18.683512Z in 417.312842 s. Terminal
usage records 52 parent / 0 child responses, 53 tools and 15 failed calls
(14 script calls and one record call with an extra field). No task_step_error
was reported. This restores execution; it does not establish accepted research.

The 288 main-CSV metrics plus 183 daily prices passed all 471 independent checks.
The workbook's 288 comparisons confirm consistency with those metrics and must
not be counted as another independent source-data check. Correct CSV/workbook
values must remain unchanged while presentation errors are repaired.

HTML quality still fails:

- Output shares correctly stored as 79.4%, 75.5% and 80.8% become roughly 0.8%
  in prose and 0.79 / 0.75 / 0.81 under a percent heading. The actual denominator
  is the full-period observed maximum, not a separate maximum for every day.
- Formal curtailment rises from 7,160 to 7,902.5 MWh, but the monthly table says
  +29.8%; the checked change is +10.3701%. The summary's 5.4%–6.5% price-decline
  range omits the third province's 3.3% decline. Seven negative-price dates are
  inconsistently described as eight. Province-hours and deduplicated clock hours
  also need clear units.
- Actual embedded image bytes were decoded and matched by SHA-256. Their order
  is PNG 1, 2, 4, 5, 7, 3, 6; this is not sufficient to call the figures misplaced.
  Captions instead describe content absent from the bound images: grey quantile
  bands, a negative-price boxplot and floor-price segment, export-energy or sample
  labels, three-province/renewable panels and maintenance shading, logarithmic
  scale and intraday curtailment-rate plots. The daily-price caption even claims
  values below zero although all 183 daily means are positive (minimum 194.3096).
- Summary, caption and conclusion still claim causal effects or non-bottleneck
  status from descriptive co-occurrence. Later caveats do not cancel those claims.
  Missing load, bids, clearing/network information and counterfactuals remain real
  limits. A renderer cannot repair this semantic problem by itself.

Evidence is under ROOT/outputs/research-round-efficiency/enterprise-question-cycle/
thr_425aec0650141837cbf6/: independent-content-check.md/.json,
independent-html-evidence.json, independent-report-text.txt, terminal-observation.json
and timing-audit.json. Seven images are readable and self-contained; structure
alone does not establish content correctness.

Timing audit uses saved server receive timestamps, not direct Provider spans.
Report-build took 208.600943 s, with 23 model responses, a 167.437708 s model
interval union, 22 tools and four failures. Whole-run model/tool unions were
359.403071 s / 26.279742 s. Terminal output was 89,129 tokens. Per-stage token
usage is unavailable in that ledger and must not be guessed. This failed-quality
run is an experimental comparison point, not a replacement for 350.524 s / 41.

## Accepted candidate and ownership

Add an application-owned native CLI, `capstone-report`, implemented with Python
standard library only. It is a reusable rendering utility in the isolated native
workspace, not a new Domain Pack semantic tool, planner, research method, store,
product ledger or Authority. Existing research policy remains frozen for this
experiment. No App typography, layout or product-viewer change is included.

It consumes a free report specification: sections, plain paragraphs, bullet
lists, CSV tables and figure files. The model retains responsibility for the
research structure, explanations, limitations and conclusions. It can use the
helper without hand-writing repeated HTML, CSS, TOC links and base64 plumbing.
No fixed read/calculate/report sequence or demo-specific sections are introduced.

The backend worker owns `tools/native_report.py`, its tests, native Docker
installation, manifest and smoke test. The parent owns verified environment
context/discovery and its tests. This document and its plan are control work;
their owner does not edit implementation or run Provider calls.

## Interface and data behavior

Frozen CLI: `capstone-report --spec report.json --output report.html`, plus
`--help` and `--version`. The current implementation tests define the executable
contract. A spec has title, optional subtitle and sections with unique id, title
and blocks; optional schema is `capstone-report/1`. Supported block fields are:

| Block | Data | Responsibility |
| --- | --- | --- |
| paragraph | text | Escape supplied text; no raw HTML injection. |
| bullets | items | Preserve order and escape every item. |
| table | csv, optional columns/caption | Read existing CSV cells as strings; preserve lexical values, units, decimal places and leading zeros. Do not recompute or silently multiply percentages. |
| figure | path, caption | Embed the exact local PNG/JPEG/safe SVG bytes with one ordered figure/caption/TOC owner. Do not infer what the image depicts. |

CSV data may already have been independently verified upstream. The renderer
binds the bytes it actually used; it does not certify an arbitrary CSV as correct.
Plain paragraphs can still contain wrong values or reasoning. Likewise, correct
image binding and numbering do not prove that a caption describes actual plotted
series, ranges, panels or causal evidence. Baked-in image titles remain the image
producer's responsibility and must be checked against the final caption.

Success produces one self-contained HTML file and a compact `capstone-report-receipt/1` JSON receipt with
output/source identities and section/figure counts. Figure order and anchor
identity derive from the same spec. Existing artifact collection, product-index,
research record CAS and task-delivery publication remain the sole persistence
and admission paths; a rendering receipt does not publish or accept a task.

## Confinement and errors

Read local files only inside the authorized private current workspace. Reject
URL sources, traversal, symlink escape and output aliasing a source/spec. Escape
text/CSV content; reject active or external SVG content. Do not grant new network,
host-file, model or Authority access. Existing browser iframe isolation remains.
No new pip dependency is needed.

The helper can render selected derived tables; it does not replace durable
resource references or require a GB-scale raw resource to be embedded wholesale.
Reuse application-initialized capacities where bounded processing is required;
do not introduce a hidden small business-file cap. Explicit failures preserve
input and previous valid output and report a useful safe cause. Rendering or
upstream command failures must retain nonzero exit behavior through pipelines.
No truncation or fallback file may masquerade as a complete successful report.

## Experiment and acceptance boundary

Keep the same model/provider configuration, four original source files with
matching digests, ordinary user instruction, frozen research policy and current
execution chain. Create a fresh task through the real UI. Only the renderer and
its verified availability/usage context change. Existing Harness autonomy remains;
record whether the model actually used the helper and any changed child activity.
Do not add a mandatory independent-child review at the same time. That is a
separate proposed quality experiment, so a combined rollout would confound this
comparison. If an additional failure-tail diagnostic change enters the same
candidate, record it as another observation variable; do not attribute all retry
or timing differences uniquely to the renderer.

Compare report-stage wall time, actual model-response spans/counts, script/spec
and generated-code bytes, and report-stage failures. Record whole-run terminal
output tokens and total usage separately. Use stage tokens only if an actual
saved source provides them; otherwise mark unavailable. Keep retries and failed
calls, not only the successful final renderer invocation.

Independently recheck final CSV values, all HTML numeric units/percentages/change
rates, actual embedded-image SHA mapping, caption-to-image facts, anchors,
self-contained assets and full summary/conclusion causal wording. Check browser
reading/print behavior separately. Fewer failures or shorter report generation
does not compensate for incorrect content. Acceptance requires preserved good
data, valid final products and honest quality/performance evidence; one trial
does not establish a general speed benefit. The candidate is not accepted yet.
