# Enterprise research round-efficiency validation

## Rebuilt relay acceptance and real continuation

Normative local rebuild accepted image
`6dc91af39cd4ecf9d7b5b5d30d573ae93dd9d2b7143ef73530638d9a4f10230e`.
The same controlled long Provider request completed through the rebuilt relay:
57.326s,7,221,324 decoded SSE bytes,tool_calls finish and DONE, no errors.
This is protocol acceptance, not a research-performance result.
The actual UI continuation “前面已经有图表和数据了，请继续把能直接打开的报告完成。”
started attempt_e14a537c0fa29ee5 in thr_fa7dc16f4e5bd0b254c8 and is still running.
Reports, numeric quality and a fresh baseline comparison remain pending.
Safe probe logs are saved under root outputs/research-round-efficiency.

## Confirmed relay cutoff and context audit, 2026-10-18

A controlled real Provider call through the unchanged native relay reproduced
the disconnect: a long tool argument stopped at 39.708s, 4,193,456 bytes received,
without `finish_reason` or `[DONE]`. A scoped diagnostic wrapper caught the exact
local `ValueError('Provider response exceeds bounds')`. No credentials or model
content were logged. A shorter request through the same relay completed at
27.19s / 3,053,877 bytes. Direct 8192-token calls also completed normally at
24.930s / 2,555,608 bytes and 22.602s / 2,655,936 bytes. A fixed 45s model timeout
is therefore not established. The confirmed local defect is the 4 MiB cumulative
wire-byte limit: SSE repeats metadata for each token, so valid long tool calls
are cut before completion. Earlier failed task records cannot retrospectively
prove that every failure had this cause.

The relay now streams SSE without that cumulative document limit, while keeping
task deadlines, revocation, bounded chunks and the non-stream response cap.
Failure logs contain only task identity, HTTP status, byte count, elapsed time,
known finish metadata and exception class. A real HTTP regression failed before
the fix and passed after it; cancellation/slow-header/body cases remain covered.
Same-Work continuation now picks the latest saved version of each path across
terminal attempts, instead of discarding all earlier charts when a later failed
attempt saved only a script. Both memory and real PostgreSQL tests cover reuse,
replacement bytes and ownership. Combined focused suite: 103 passed.
Normative rebuild is running in `/tmp/capstone-relay-stream-rebuild.log`.

The traffic audit found 21 successful model-response records in the last failed
continuation: single-request input grew from 13,960 to 85,487 tokens; summed
submitted input was 1,066,056 tokens and output 36,717 tokens. These include
repeated cached history, not a single million-token source document. Three recent
rebuild logs explicitly account for about 1.4 GB of dependency downloads, excluding
unreported npm sizes. The user's 2 GB Clash total cannot be equated to model
context traffic. Historical request/response byte accounting is incomplete.
Bulk data stays in files; generated code and repeated tool observations also
grow the working context. Do not reduce upload size to address this issue.

## Final local checkpoint, 20:08

Local rebuild accepted image
`b1547560f6355ec07e3b9b484bb2c8c39692e1a584d034ac942a5e883b483264`.
The actual report download after the preview fix retains SHA256
`bb1b1e9dff616778706828c9ac2024ce0273152add1b1bee27ebfd2921779f68`.
Reduced motion selected `auto` scrolling; chapter 1 reached top -0.03125px.

A natural continuation, “请继续把报告做完，已有图表和分析能用的就保留。”,
started `attempt_311bffe17942d93b` in the existing optimized thread. It failed
after 437.593s and 27 model responses / 32 tool calls. Seven PNG charts and
metrics were generated, but no complete report was delivered. The private
fixed receipt says `model_transport`; the public result is
`native_transport_failed`. Several model responses failed with zero usage after
about 44–47s. This does not identify a network hop or prove a timeout setting.
The frame-overflow defect did not recur. The current source selection admitted
the latest saved script but omitted charts from an earlier attempt; this remains
an explicit continuation-quality gap. Raw original error text is not retained.
No Provider task is active. Do not count this failure as a performance gain.
Evidence: root `outputs/research-round-efficiency/recovery-after-frame-fix*.json`.

Regression checks completed in segments: 997 legacy-agent, 244 simulator,
61 issue, 642 Kernel, 144 domain, 86 generic-tool, 59 grid-tool, 683 App,
inventory/PyPSA/workbench suites passed. The main backend run had 1618 passes,
136 skips and five old assertions incompatible with coalesced deltas / bounded
cancel polling; those fixtures were corrected and 29 focused cases, including
real PostgreSQL, passed. An unrelated deployment test inherited external model
configuration; the isolated rerun passed. The aggregate was not one clean
`make test` run. The temporary test PostgreSQL container was stopped.
The next research work is model-transport diagnosis, source reuse across saved
attempts, then a fresh successful same-input comparison. No cloud/demo change
or merge into dev occurred.

## Report navigation repair, 19:52

The real baseline report exposed an HTML preview defect. Relative chapter links
in `srcDoc` used the App URL as their base and opened an App document in the
frame. Preview-only parsing now binds fragment anchors to `about:srcdoc#...`,
removes their target override, and adds smooth scrolling with a reduced-motion
override. The empty sandbox and network/script CSP remain in place. Downloads
still use original verified bytes. A Blob document experiment was rejected:
the sandbox blocked its fragment navigation; no permission was widened.

An actual click on chapter 4 reached `about:srcdoc#s4` with section top -0.203px
and unchanged App URL. Eight preview checks, all 683 App tests and TypeScript
checks passed. Local rebuild remains pending in `/tmp/capstone-anchor-final-rebuild.log`.
The prior backend rebuild accepted image `658b1c40e187`; no Provider task is active.
The remaining full-test targets continue after updating old grid-tool test
fixtures for SDK event registration (59 passed). Earlier 997 agent, 244 simulator
and 61 issue checks passed; terminal retained-file checks passed all six cases.
This does not establish a successful optimized research performance result.

The user accepted the simpler execution approach and moved the validation focus
to long enterprise-research tasks. Ordinary-chat latency is accepted for this
stage; do not keep tuning it or treat its short-task timings as long-research
acceptance.

## Approved approach and ownership

Use the native executor's existing parallel tool batches. The installed Pi SDK
defaults to parallel execution within a model response, unless the tool or runtime
requires sequential execution. Independent actions can share a response; dependent
actions, shared-file writes and research revision mutations stay ordered. Known
deterministic parsing, calculation, exports and checks can be carried through in
one authorized action, without asking the model between every program step.
The model chooses the batches and reacts to actual results. No new scheduler,
extra planning model, mandatory stage sequence or worker pool is introduced.

The generic method belongs to
`packages/enterprise-research-domain-pack/src/enterprise_research/resources/research-method.md`.
The update asks for independent actions in one response, reuse of saved results,
affected-only rechecks after local corrections, and a final answer that does not
repeat all report tables. Registered professional tools and Authority boundaries
remain in force. This does not give a professional session arbitrary execution.
The application-owned isolated native executor keeps its existing grants.

## Acceptance plan

Create a fresh enterprise-research session in the actual App. Upload the four
original simulated 15-minute source files from the user-trial package through the
file chooser. Use an ordinary business request for a Chinese standalone report,
charts and key metrics, using only uploaded material. Do not supply procedural
repair prompts or create the report externally. Inspect public purposes, findings,
adjustments, failed calls, model rounds, true work-tool batches and total duration.
Do not count a progress call plus one work tool as parallel independent work.

Download and inspect the actual report. Compare price, channel and renewable
metrics with independent source calculations, preserving the README's units,
paired-data denominators and missing-data coverage. Check that the report opens
without external assets. Give ordinary human feedback to a material imperfection
or presentation need and verify its revision, preservation of valid work,
download and refresh recovery. A faster but incomplete report does not pass.

The existing successful full-source run (thread `thr_36dbeb15686568c7a3e6`, initial
attempt `attempt_5480ae54cfcc78d0`) is a historical wall-time reference, not a
controlled benchmark. The output scope, model responses and earlier runtime
telemetry differ. Measure new model-round/batch behavior directly; do not infer
missing old round counts or claim a fixed percentage improvement from one pair.

## Accepted baseline and findings

The user selected the actual full-source run as the comparison baseline:
**8 min 08 s (488.375 s), 77 model responses**. Thread
`thr_012b1ccf751d2c44e586`, attempt `attempt_9ce3f4cb9b1dcc9e` completed from
one ordinary business instruction and four actual UI uploads. No repair prompt,
extra skill or expected output was supplied. Source files were not replaced.
The runtime recorded 83 tool calls including progress/research bookkeeping,
76 calls in the App summary, 6 failed calls, and only one batch with multiple
actual work tools. These are different counters, not interchangeable timings.
The initial method-only guidance did not establish an efficiency improvement.

Actual downloads: `outputs/research-round-efficiency/guide-only-report.html`
and `guide-only-metrics.csv` in the root checkout. The HTML contains 8 inline SVG
charts and 16 tables, with no external assets. It rendered in the actual preview.
Independent source aggregates are retained in `expected.json`; no expected
results were sent to the agent. A source-backed quality comparison is in progress.

The task lacked pandas and plotting libraries in its main isolated Python.
It wrote a custom parser/chart/report implementation, repaired script errors,
then made many small checking and editing calls after producing a usable report.
These observations motivate both shared execution guidance and proportionate
research verification. They do not justify a task-specific pipeline or shorter
hard timeout.

## User-confirmed ownership and runtime requirement

Shared execution organization belongs below the application-specific research
method. A single neutral Pi extension now supplies batching, dependency ordering,
result reuse, consolidated checks and usable-output completion guidance to both
the professional tool extension and the isolated native SDK. This uses the
existing native parallel executor and adds no model, scheduler or tool grant.
Enterprise research retains its own source/definition checks and chooses the
depth needed for the requested deliverable. A second complete implementation of
every calculation is not mandatory. Partial fixes recheck dependent results.

The user identified missing generic analysis tools as a runtime design omission.
Capstone must provide a tested common capability baseline: programming and data
analysis, Chinese charting, document processing, and compatible skills/MCP.
Availability includes the executable dependencies, not merely a visible skill
name. Application selection and professional Authority boundaries still apply.
Version pins belong to the existing owning manifests; readiness must test actual
imports or tool execution and report missing capabilities. Runtime preparation
must not depend on each business task probing, installing or rebuilding basic
tools. The outer-network switch remains off by default and does not disable
registered internal search tools. This is an accepted platform requirement;
complete document/skill/MCP baseline coverage is not yet verified.

The present increment installs only generic numpy/pandas/matplotlib, using
`configs/runtime/power-samples.lock.json` constraints, plus Noto CJK fonts and
headless plotting. It does not install simulator roots into the generic runtime.
The image build runs a real Chinese SVG smoke check. Broader baseline coverage
remains explicit work, not an implied acceptance claim.

## Current state

The baseline finished before rebuild. Runtime libraries were imported and a
Chinese chart generated in the rebuilt isolated image. Shared execution and
research-method updates passed focused tests; a final source rebuild and the
same full-source task comparison are in progress. Implementation remains an
unmerged local candidate; cloud and demo environments are unchanged.

## First optimized run: not accepted

Local image `a4939d24ea0bada56b62275a0f9a805be3c14fc10b8737ec84c581a9aa8a34bc`
passed readiness. A fresh actual UI session (`thr_fa7dc16f4e5bd0b254c8`) received
the same four files and exactly the same business instruction. No optional skill,
expected values or procedural prompts were provided. Attempt
`attempt_6e231d5068978875` failed after **430.943 seconds and 39 model responses**.
It issued 39 tool calls, including two true multi-work-tool batches, used pandas
and plotting, and recorded a source-backed observation after generating eight
charts. It did not deliver the requested integrated report. This result is not
an accepted speed improvement despite fewer rounds.

The last three model responses had zero usage and no tool execution. The private
fixed receipt records `model_turn_incomplete`; original provider error text was
not retained, so a more specific cause cannot be reconstructed from this record.
Do not claim a timeout, output-token limit or network fault as a proven cause.
The failure also exposed a reporting defect: failed assistant messages containing
partial tool calls were marked as completed tool organization. Shared projection
and step tracking now label such messages as failed model responses, retain an
error finish reason and link the following continuation to the failed step.

Failure delivery now distinguishes an incomplete model turn from a generic system
exception. Safe classification covers interrupted streams, service failures and
explicit content rejection without publishing arbitrary provider text or secrets.
The runtime font configuration also removes the commented default font entries
before adding the selected defaults, preventing duplicate-key warnings when
matplotlib builds its default parameters. Focused tests and a canonical rebuild
of these corrections are in progress. A completed fresh long-task comparison,
download, source checks and ordinary-feedback revision remain required.

## Recovery test exposed two shared infrastructure defects

After the diagnostic rebuild (`dcddcc1ae9476942da4aedd7b26a6608c7db1e6eeb8c00d69afbd7e7c63a5d7d`),
the actual user-style follow-up was only: “刚才中断了，请继续把报告做完，已有图表和分析能用的就保留。”
Attempt `attempt_cfae03c5d057742f` failed after 165.186 seconds / 16 model responses.
Its explicit terminal code was `native_response_too_large`. The last actions read
two PNG charts in one model turn. No completed report was delivered.

The native SDK retained original image observations, but its tool events and turn
completion repeated those payloads over the bounded runtime frame. `rpcEvent`
now keeps only turn boundaries and assistant-message type/usage metadata, drops
unused tool-progress payloads, and replaces built-in tool image bytes with their
MIME type, size and SHA256 for runtime receipts. The original SDK model context
and saved image files remain intact. External MCP final results are unchanged.
This repairs the transport projection instead of increasing the frame limit.
A real pinned-SDK acceptance performs two parallel reads of a generated large
PNG, asserts both original images remain in the SDK model context, and completes
through the actual `GeneralPiProcess` frame reader. Only model responses are
scripted; no Provider is used in this check.

The follow-up also said that its current directory had none of the old outputs
and rebuilt the analysis. Saved files had not been lost: automatic historical
selection excluded failed/cancelled attempts and short-text material slots
omitted further files and binary charts. The application now admits immutable
same-Work files from terminal attempts. Files beyond the legacy inline material
projection use the existing chunked resource staging and read-only input paths,
not conversation-text copies or a new model/planner/tool. Their source attempt,
artifact identity, Work and incomplete/completed status are explicit. The worker
rechecks the frozen descriptor, same-Work binding, size and digest before use;
foreign Work/Thread references and altered versions fail. Explicit selected
products retain their existing selection contract. Sources are observations,
not current Authority results, and saved partial files are not accepted reports.

167 focused checks passed with an isolated real PostgreSQL, including normal
uploads, product selection, research bridge, staging and task transport. New
checks cover more than four historical files, binary charts from a failed
attempt, actual saved bytes, changed digests and foreign Work rejection.
Full repository regression and the final source rebuild are in progress.
No live Provider task is active. Both failed attempts remain in the ledger and
in `outputs/research-round-efficiency`; neither counts as optimization acceptance.
