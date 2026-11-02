# Native report renderer implementation plan

## Current successor checkpoint — 2026-10-19 05:20 CST

The renderer trials remain failed-quality evidence, not an accepted baseline.
The successor independent-review path is now offline verified and locally
deployed on backend 04030070 / native a8c31c5b; new real quality and overhead
validation are pending. Full identities and current checks are in the
[delivery-review plan](../plans/2026-10-19-delivery-review.md).
Earlier deployment/source checkpoints below are historical.


> **For agentic workers:** Use the already assigned backend/parent owners and TDD
> task by task. Do not spawn more workers or commit without parent instruction.

**Goal:** Reduce repeated report HTML generation and presentation-conversion
errors with an optional generic native renderer, then measure the result.

**Architecture:** A standard-library CLI renders a free JSON spec using existing
CSV and image files in the authorized native workspace. Native build receipts
advertise only an installed and smoke-tested command. Existing Work/Attempt,
research CAS and artifact admission remain unchanged.

**Tech stack:** Python standard library, current native Docker image and manifest,
pytest, existing real App/Provider task path for final verification.

**Design:** [Accepted bounded candidate](../specs/2026-10-19-native-report-renderer.md).

## Current verification — 2026-10-19 04:27 CST

Canonical rebuild /tmp/native-report-rebuild.log exited zero. API and three workers
share image 4553721e20ab922d89ba7f77e9c5db554a292a4ae1a1afe9d8cc600f1a103dd3;
native image is 8ccd4e9af7713610073123bea2520aa4e91cc478c7a3ea5aa04594f7594be9a0.
UID 65534 used installed PATH capstone-report 1.0.0 to render actual local CSV/SVG,
preserving 79.37% and 001 plus valid anchors. The root-readable receipt belongs to
the host and successfully supplies helper context; its permissions are intentional.
Context red-to-green 10 tests, combined renderer/environment 33 tests and one
actual-SDK offline split-only scenario passed. Do not add overlapping selections.

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

## Global constraints

- No App source/layout/font changes. Retain formal/process/metadata 12 / 11 / 10 px.
- No new pip dependency, ledger, planner, research policy change or Authority grant.
- Free section/paragraph/bullets/CSV table/figure composition; no demo-specific schema.
- CSV table cells preserve exact source strings. Numbering/TOC and embedded bytes
  share one owner; semantic factual and causal claims still require review.
- Existing initialized capacity and sandbox boundaries remain authoritative.
- Preserve dirty work, failed runs, frozen retries and all correct source metrics.
- Do not call source/offline checks deployment or measured research acceptance.

## Task 1: Renderer and actual native installation

**Owner:** backend worker.

**Files:**
- Create `tools/native_report.py`.
- Create `tools/tests/test_native_report.py`.
- Modify `deploy/general-pi.Dockerfile`.
- Modify `configs/runtime/native-analysis.json` and `tools/native_analysis_smoke.py`.
- Update owning environment tests only as needed; preserve hash-locked dependencies.

**Interfaces:** CLI `capstone-report --spec <workspace JSON> --output <workspace HTML>`;
spec uses title/subtitle/sections and typed blocks as defined by implementation
tests. Emit a compact source-bound JSON receipt. Do not publish a task product.

- [x] Write and observe failing tests for lexical CSV preservation, escaping,
  image identity/order, anchors, safe SVG, invalid fields/paths, source overwrite
  rejection and explicit failures.
- [x] Implement only the generic stdlib renderer; retain nonzero failures and
  prior valid outputs. Verify no semantic recomputation or business fixture data.
- [x] Wire native image installation and add real functional smoke using
  local synthetic CSV/image input. Derive command/capability counts from the
  effective manifest; do not repeat the previous 14 / 20 counts after changes.
- [x] Freeze backend source after 85 combined scoped checks and staged-container
  smoke: 21 capabilities / 24 packages / 15 commands. No new pip dependencies;
  only the lock manifest-hash comment changed. Renderer pyright passed.
- [x] Verify the installed image launcher through `capstone-report` on PATH as a
  non-root user after the final rebuild. Staged temporary storage was noexec, so
  staged smoke used the same Python argv and does not prove installed launcher
  execution. Evidence: /tmp/native-report-implementation-report.md and
  /tmp/native-report-container-smoke.log.

## Task 2: Verified discovery in the existing native context

**Owner:** parent.

**Files:**
- Modify `packages/capstone-agent/src/capstone_agent/native_environment.py`.
- Update `packages/capstone-agent/tests/test_native_environment.py` and narrow
  consumers as required by actual context composition.

**Interfaces:** Existing `environment_context(path)` consumes the successful
native-environment receipt. Advertise helper availability and concise generic
usage from verified command metadata, not an unverified hard-coded install claim.

- [x] Write and observe a failing test for verified command discovery and missing
  helper/receipt behavior.
- [x] Add concise generic usage context without changing frozen research policy,
  imposing a report template or granting network/tool capabilities.
- [x] Run context/isolated-image focused checks; combine with backend source only
  after both owners freeze. Record exact scoped results without adding overlaps.

## Task 3: Deployment and single-variable real experiment

**Owner:** parent/integration; docs worker records the receipt.

- [x] Use the canonical rebuild entrypoint with the existing explicit local env
  and model-library overrides. Preserve prior failures and data; verify API/all
  workers identity, general-pi identity, readiness, CLI availability and actual
  non-root renderer smoke. A source or build-only pass is not research acceptance.
- [x] Start a fresh UI task with the same four original files and ordinary task
  request. Verify file digests, model settings and frozen research policy. Do not
  give the model the expected numerical corrections or a fixture-only script.
- [ ] Record actual renderer adoption, report-stage wall/model spans and response
  count, report-stage tool failures, generated script/spec/output bytes and total
  terminal usage. Per-stage output tokens remain unavailable unless a real saved
  source provides them. Record deviations/confounders, including child activity.
  If failure-tail diagnostics also change, record that additional observation
  variable; do not attribute all retry or speed differences to the renderer alone.
- [ ] Independently compare CSV/workbook/HTML content and actual image SHA bindings;
  test percentage scaling, change rates, date counts, missing plotted features,
  summary/conclusion consistency, evidence limits, offline assets and browser use.
- [ ] Decide quality and performance separately. Preserve good numeric results;
  do not accept a faster but incorrect report or generalize a single trial.
  Keep independent-child product review as a separate experiment for attribution.
- [x] Update canonical register/resume/journal and regenerate/check the graph once
  source/image freeze and verification results are known; sync owning docs only.
  This records the deployed/functionally checked checkpoint and running trial;
  the independent real-task result and acceptance items above remain incomplete.

## Comparison receipt: current failed-quality run

`thr_425aec0650141837cbf6` / `attempt_c7b63063f74a71d6`: completed 417.312842 s,
52 parent / 0 child responses, 53 tools / 15 failures (14 script, one extra-field
record rejection), zero task_step_error. CSV 288 + daily 183 = 471 / 471 passed;
workbook 288 consistency comparisons are not another independent total.

Report-build: 208.600943 s; 23 responses; model interval union 167.437708 s;
22 tools / four failures. Whole-run output 89,129 tokens; no per-stage token
measurements are available. Use timing-audit.json, not total-minus-tool estimates.

HTML fails percent scaling (roughly 0.8% vs correct 79.4 / 75.5 / 80.8%),
curtailment change +29.8% vs +10.3701%, incomplete price-decline range, 7/8-date
inconsistency, captions claiming absent bands/panels/series, and unsupported causal
or bottleneck conclusions. Embedded bytes were SHA-matched; do not label the
issue merely as figures placed in the wrong order. Full evidence is in the run's
independent-content-check.md/.json and independent-html-evidence.json.

The comparison run used image 03e64818 / native ef50fbc9. The renderer now has
verified local deployment on 4553721e / native 8ccd4e9a, as recorded above;
the running real trial has no accepted quality/performance result yet.
The accepted 350.524 s / 41-response reference remains unchanged.
