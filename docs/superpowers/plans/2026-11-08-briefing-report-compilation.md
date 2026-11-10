# Briefing report compilation implementation plan

**Goal:** Compile the main report from existing admitted data and products with a
chapter argument, an agenda, coherent evidence pages and a closing page.

**Architecture:** The application/native report tools own document composition.
The model owns the report argument and interpretation of admitted evidence.
The renderer checks literal fields, page roles and geometric capacity. This unit
does not change data acquisition, the Kernel, Authority results or the baseline.

**Tech stack:** Existing capstone-report, python-pptx, template masters, native Pi.

## Constraints

- Use saved evidence only; no new business queries or invented causal claims.
- Preserve all original and historical products. Do not force a 14-page target.
- Preserve template typography, logos and master styling; no silent pagination.
- Current work is report compilation. Upstream research planning is deferred below.
- No CI, push, PR, merge or remote deployment without its existing approval gate.

## Task 1 — Explicit page roles and chapter context

Files: tools/native_report.py, tools/native_presentation_layout.py,
tools/tests/test_native_presentation.py, capstone_agent/native_environment.py.

- [x] Add a failing real CLI test: template spec with role:agenda, content with
  section text, and final role:closing produces four slides including cover;
  closing reuses the cover master/pictures with light centered editable title.
- [x] Add failing checks for unknown role, a closing page before later content,
  unsupported closing visual blocks and role fields on the untemplated baseline.
- [x] Add optional slide role (content/agenda/closing) and section text. Existing
  slides default to content. Render chapter context at the right of the title bar; render a
  closing page with cover styling and one optional short paragraph.
- [x] Keep baseline parsing/rendering unchanged when new fields are omitted.
  Derive briefing text capacity from geometry instead of a separate ten-line cap.
- [x] Guide authoring: chapter question, claim, evidence, interpretation and
  supported implication. Do not mandate a fixed bullet count or infer causation.
- [x] Run focused renderer/environment checks, commit exact owned paths and
  canonical local rebuild. Keep native image grouping and layer count stable.

## Task 2 — Real report compilation

- [x] Assemble an immutable input bundle from existing render receipts and exact
  historical products. Verify every dependent file hash before upload.
- [x] Run Capstone on admitted existing results. First save a chapter/page argument plan;
  then compile a main report with cover, agenda, connected chapters, conclusions
  and closing. Each content page must explain how evidence supports its claim.
- [x] Use capstone-report inside Capstone, retain full notes and visible material
  limitations. Save source spec, input manifest, receipts and main PPTX.
- [x] Download/hash-check output, verify structural roles and inputs, inspect
  every rendered page, correct blocking defects through the runtime, and record
  nonblocking polish separately.
- [x] Record the verified local source, products and remaining gaps in the report,
  canonical worklist, journal and recovery checkpoint. Preserve mixed user work.

### Active refinement — Data-derived total/detail/total report

The user now requires this main report to follow a total/detail/total argument,
with the runtime generator deriving the themes from saved evidence. The agenda
is the main line; every opinion page belongs to one of its topics. Guided v2 is
retained as an intermediate experiment. A fresh Work receives only the original
pinned evidence/content bundle, without v2 or developer chapter names/count/order.
It saves its own argument plan, agenda/page bindings, interpretations and synthesis,
then renders through capstone-report. Check exact agenda/section labels,
contiguous chapter ranges, opening/detail/synthesis coverage, claims versus
evidence and all rendered pages. Latest user layout contract: agenda lists only
main chapter titles, without questions, slogans or method prose. The exact chapter
title appears on the right of each opinion page's title bar in22pt bold; its separate
27pt claim stays on the left. Reserve both rectangles and reject an overlong claim
instead of overlapping or shrinking. Unicode numeric ranges remain unbroken.
These corrections preserve the template and baseline. No new data acquisition.

## Autonomous compilation quality regression — v7 rejected

User review rejects v7's opinion-page depth. Autonomous execution and valid PPTX
output are not report-quality acceptance. Keep v6 as the reviewed reference;
do not replace it with v7. This is a generic reasoning/composition requirement,
not a requirement to copy v6's chapters, wording or page count.

Observed difference: v7 repeats figure/table readings as short bullets and keeps
the explanation in speaker notes. V6's visible text explains why the readings
support the page judgment. Current authoring guidance requests explanation but
also emphasizes a few short points; current structural/layout checks do not
verify semantic support. More text or a fixed bullet count is not the fix.

Next correction must make runtime self-review assess the visible page alone:
does it state the relevant evidence/comparison, explain the inference to its
title, and express a supported implication or material limit? Notes cannot
substitute for that visible reasoning. Do not force an operational recommendation
on every page or infer resource adequacy from load shapes. Layout overflow must
trigger recomposition without dropping the inference. Save per-page review and
revision records, then run a fresh no-outline trial. Developer review remains
independent; a mechanically valid file or a model's own passing score is not
sufficient acceptance. This correction is pending implementation and real-run
verification.

### Execution unit — visible argument review

Standing user constraint: implement reusable report reasoning, not patches for
individual slide defects. Do not add this case's topic labels, metric names,
thresholds, preferred conclusions, page count or accepted prose to runtime policy.
V6 is an independent quality reference only. The same review must work for other
audiences, subjects and admitted evidence; no keyword routing or numeric-only
quality heuristic. Semantic adequacy stays with the model and independent review.

Files: `packages/capstone-agent/src/capstone_agent/native_environment.py` and
`packages/capstone-agent/tests/test_native_environment.py` in the existing
isolated runtime and presentation recovery trees. No Kernel or Authority change.

- [x] First add a failing environment-capability test: verified template support
  supplies a visible-body argument review; absent template support does not.
- [x] Replace ambiguous short-point guidance with concise connected reasoning.
  Keep claim/evidence/inference/limit in visible blocks. Notes hold derivations.
  Describe a generic weak-versus-supported example without case-specific themes.
- [x] Require runtime to read back saved spec and actual slide text excluding
  notes, review page-to-title and page-to-chapter support, and save defects,
  revisions, final spec digest and unresolved checks. At most two repair rounds;
  semantic review is model reasoning, not keyword/count validation in renderer.
- [x] Run focused environment and direct renderer checks, commit owned source,
  port to recovery tree, then canonical local rebuild. Reuse image groups.
- [x] Start fresh v8 with original immutable evidence only and same natural
  report request. Do not provide v6 wording, topic names, outline or page count.
  No developer feedback during generation; independently inspect final content
  and rendered pages against v6 quality, not v6 wording.
- [x] Record passing/failing pages, source hashes, actual runtime review and
  final product links. If weak reasoning survives, keep acceptance open and
  revise the runtime mechanism rather than manually editing the trial deck.

V8 outcome: completed16 slides without developer steering, using the original
bundle. It preserved visible inference prose and performed two repair rounds.
Independent review found that field completeness was still treated as semantic
acceptance. V8 remains a candidate, not the replacement for v6. Runtime9766b7a7
adds skeptical reading: consider contrary interpretations/missing comparisons,
preserve population/window/measure/aggregation/comparison basis, distinguish
observations/change/causation/forecast/recommendations and test chapter coherence.
These are general reasoning criteria; no case-specific corrections enter policy.
Fresh v9 must use the same original-only protocol after rebuilding this source.

### Contract fallback if guidance-only authoring remains unstable

The saved argument plan must be an executable composition input, not a separate
essay whose reasoning can disappear into notes. Add a backwards-compatible
`capstone-presentation/2` briefing contract: template required; each ordinary
content record has `argument: {explanation: <nonempty literal text>}`. The
renderer appends that explanation as visible prose and applies the existing
overflow checks to it. Agenda/closing records have no argument. Version1 and the
untemplated baseline stay unchanged. Optional additional fields are unnecessary
for this unit; evidence and limits can stay in existing visual/text blocks.

This validates presence and renders authored reasoning. It cannot determine
whether reasoning is true or adequate. Keep the skeptical semantic review and
source/visual review separate, with no keyword, business or word-count heuristic.

Files: `tools/native_report.py`, `tools/tests/test_native_presentation.py`, and
the existing native environment guidance/test. Reuse existing Docker COPY groups.

- [x] Add failing real CLI tests for v2 explanation in visible text (not only
  notes), missing/blank/non-text explanation preserving prior output, agenda and
  closing compatibility, and explicit overflow from an overlong explanation.
- [x] Accept schema2 only with a template; validate exact argument fields and
  inject a literal paragraph into a copied content record before layout. Keep
  the original spec hash in source receipts. Return visible argument page/hash
  bindings as mechanical provenance, with no semantic certification.
- [x] Update verified-template guidance to use schema2 for evidence briefings;
  explanation derives from the page argument and is never optional notes-only
  material. Update CLI help; keep ordinary schema1 examples intact.
- [x] Run focused renderer/environment checks and commit/port before rebuilding.
  Start a fresh original-only trial. Do not repair the previous deck by hand or
  supply case-specific feedback to the new trial.

Implementation16845b10 (isolated port0925e641) passes106 focused checks in10.36s.
The initial eight contract tests failed on unsupported schema2, then passed.
Build smoke reads actual visible text and explanation digests; capability
`argument_presentations` is advertised only after this smoke. CLI version1.2.0.
V9's final inference review corrected some comparisons but left explanation in
the separate argument/review products rather than the page, so it is not accepted
as v6-level visible reasoning. Fresh v10 verifies the executable contract's
mechanical presence guarantee; its semantic gaps lead to the reader unit below.

### Independent reader for semantic critique

V10 establishes the schema2 mechanical guarantee on13 content pages, but its
self-review can identify a contrary interpretation while leaving the stronger
visible claim unchanged. Semantic acceptance remains open. Reuse the existing
application-selected text-only LLM pool, not a case-specific repair or a new
Authority path. Runtimee639baf4 asks a granted isolated reader to inspect bounded
actual visible text/chapter bindings and admitted source facts, excluding author
notes, argument plan and previous self-review verdicts. The parent verifies
returned concerns against sources, revises when warranted and saves actual
critique/dispositions with reviewed/final spec digests. Keep at most two repair
rounds; no unchanged repeated review or inferred child success.

This local candidate explicitly enables the existing experimental pool flag in
ignored local configuration. Production defaults remain disabled. The exact
registered policy limits and tool grants stay unchanged; children get no tools,
files, new source grants or Authority status.58 Python/10 Node checks pass;
19 isolated environment checks pass. First run with a dependency-light uv command
failed collection; project uv environment resolves it. No CI/remote change.

- [x] Rebuild sourcee639baf4 and verify actual pool publication.
- [x] Run fresh v11 and, after the generic waiting correction, v12 under the
  same original-only natural request. Confirm actual
  independent reader submission/return, source-scoped input, defect dispositions
  and final visible reasoning. Do not provide developer case defects to the run.
- [x] Independently inspect final facts, inference, chapter flow and every page;
  retain v6 if quality still fails. Native visual/PDF support remains separate.

### Runtime ownership

Ownership clarification: Capstone's report-generation workflow must derive topic
classification, chapter organization, page arguments and appropriate composition
at runtime. Developers provide generic mechanisms and quality criteria, not a
case-specific outline. The guided v2 experiment was given a suggested three-part
outline by the developer; it verifies guided compilation only. It does not prove
autonomous report organization. Autonomous acceptance must withhold chapter
names/count/order and use a fresh Work context, so a prior outline cannot leak
into the supposedly autonomous result. Fresh-context compilation is now active
for the main report; report-led acquisition remains a separate later unit.
The deterministic capstone-report CLI
validates/renders documents; report reasoning belongs to the model-facing report
workflow rather than hardcoded topic classifiers in that CLI or the Kernel.

## Deferred — Report-led data planning (accepted, not implemented here)

Before future data acquisition, derive a report argument from the user's audience,
purpose and decisions. Map chapter questions to candidate claims, required metrics,
comparators/windows/units, evidence sources, planned visuals and missing-data
conditions. Use this map to select relevant data work; revise claims when evidence
does not support them. Save the map and its revisions with the Work. Do not make
report writing retroactively determine or fabricate results.

Acceptance for that later unit: a real new task saves this evidence plan before
relevant acquisition, obtains targeted admitted data, records gaps and revisions,
and compiles a report traceable to the plan. Test on more than this summer-load
case. No hardcoded chapter names, business fields, fixed tool first action or
keyword router in the application/Kernel. Current source-only recompilation does
not count as acceptance of this upstream planning behavior.


## Selected-call wait correction and V12 acceptance

V11 submitted a real critic but cancelled it while still pending, without a reply.
The collect tool accepted ids plus wait_ms but ignored the wait. Source4a638740
adds exact selected-ID waiting in the neutral async pool and LLM collection tool.
Unrelated completion does not satisfy it; timeout leaves work running and does
not cancel/retry. Two regressions failed first.22 pool and14 request-consumer Node
checks plus58 Python checks pass. Port3afb60f9 preserves the older branch's tool
role metadata. Its missing ignored SDK was repaired by setup/install-pi/doctor;
36 Node and19 environment checks then pass. No auth was copied.

Fresh V12 used the same natural request and original bundle as V7–V11, without
prior trial products, outline or developer page feedback. Three scoped readers
returned actual critiques; the generator recorded dispositions, revised its own
spec and rerendered. The final16 pages have13 visible authored explanations.
Developer inspection covers all16 previews and unchanged input hashes. This
meets the current existing-results briefing-depth benchmark for user comparison;
it does not establish universal semantic reliability or runtime visual acceptance.
See the [verification report](../../reports/2026-11-08-presentation-template-generator.md).

- [ ] Nonblocking generic typography follow-up: balance cover subtitles and short
  final CJK lines without shrinking text or dropping reasoning. Verify on varied
  content, not by patching this report's specific wording.
- [ ] Broaden autonomous quality tests to other topics before claiming default
  reliability. The isolated text pool remains a local opt-in candidate.
