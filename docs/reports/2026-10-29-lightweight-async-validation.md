# Lightweight asynchronous execution validation

Implementation: b9a87970; frozen-version label correction:41bb19f2.
Canonical rebuild ready with backend image
`sha256:956bd0dc18e93ffa18a388307da9aa57075a600a9a5a955e313be9b30147bb34`.
API and workers share that image. Scoped cleanup receipts:
`cache-maintenance-20261029-174447-62383.log` and
`cache-maintenance-20261029-204953-98698.log`.

## Real parallel-call and early-file check

Submitted through a new conversation in the existing Vivaldi tab:
`thr_17b4f61cd2969e9e14ce`. Commercial DeepSeek Flash, DR off. Three explicitly
supplied demonstration records, no gateway or simulator facts.

- Completed25.587s;5parent model responses and2child model responses.
- Primary CSV captured/published at11.250s while both children were still running.
- Actual child responses2844ms and3898ms; overlapping started/finished intervals;
  each child made one model request, neither failed.
- Parent independently wrote the data description during child execution, then
  integrated actual returned answers. Three files downloaded; hashes match host
  descriptors and CSV has a header and3data rows.
- Separate immutable running/completed descriptors remain available. The initially
  selected running version remains a candidate; it must not say still generating
  after the task ends. The corrected label is candidate/usable version.

Evidence: ignored `runs/light-async-20261029/`. This validates wiring and early
availability. It is not a whole-research performance acceptance.

## Full summer-study repeat

Submitted the exact1,311-byte instruction in fresh Vivaldi thread
`thr_0850a2065d4ec8905a29`. SHA256:
`d3f126381daf74a6d46cd9a3fb1aa8b9cde84813702c305c73ddea0c7ab2e03f`.
Same selected commercial model; DR off. No LLM child jobs were submitted in this
run. Parallel gateway/program calls do not establish parallel LLM execution.

| Measurement | Prior repeat | Async candidate |
| --- | ---: | ---: |
| Total seconds | 384.959 | 480.158 |
| Parent model requests | 77 | 50 |
| Model response seconds, sum | 328.607 | 392.756 |
| Output tokens | 59,650 | 70,487 |
| Uncached input tokens | 787,348 | 383,633 |
| Total reported tokens | 4,462,102 | 3,067,368 |

The candidate did **not** pass speed acceptance. Fewer requests and tokens did
not reduce total elapsed time. Query/output scope is stochastic; this is not a
controlled proof of either cache or throughput improvement.

Live readable files were published before task completion:

| First publication | Seconds from attempt start |
| --- | ---: |
| daily_load.csv / daily_weather.csv / hourly_profile.csv | 184.59–184.68 |
| aligned load summary | 228.74 |
| core metrics CSV | 398.31 |
| first PPT version | 445.96 |
| revised PPT version | 465.13 |
| primary-marked completed PPT/CSV | 477.92–477.94 |

The model deferred the primary manifest until finalization. The current UI's
primary-only automatic selection therefore did not show those interim files
automatically. Early API publication must not be reported as early automatic
display. User reported this gap; current follow-up changes select new readable
versions without requiring a primary label and distinguish candidates from
completed products.

The longest model calls wrote expanded programs:52.473s generating a combined
chart/CSV/deck script;47.317s generating a second deck assembly script;35.793s
generating an18-query combination. The next implementation targets reusable
report layout and compact program loops over observed parameters. Adding more
concurrency alone does not fix long repeated program generation.

Actual downloaded final files:

- PPTX913,678bytes,15slides,9media entries; ZIP integrity passed. SHA256
  `4e9f7f47d964bda3ec522b3a572c3385573f06149c9327d67faeea2d6a0bf8e7`.
- CSV12,193bytes,21data rows,23columns, consistent widths. SHA256
  `bcf654d21aac7f579f6eed2777086bddaab701b586125cf369957eb443fcdb5f`.

Evidence: ignored `runs/light-async-summer-20261029/` includes public events,
per-model paths, downloaded files and hash/structure checks. These structural
checks do not certify all analytical conclusions or authorize simulator claims.

## Offline checks and review

Backend376passed/16skipped in31.74s; focusedApp77passed in7.42s; TypeScript,
build, doctor and affected Pyright passed. Tests include pinned SDK parent/child
contexts and full parent tool wiring, explicit assembly budgets, cancellation
capacity reservation and immutable artifacts across later failure.

Independent review closed blocking live transfer, unbounded capture close and
unbounded assembled dependency context findings. No cloud/demo/main deployment
or dev integration acceptance is claimed.
# Full summer request-pool repeat — 2026-10-30

Vivaldi existing tab, new thread `thr_f934d8b0481c8e7d0790`. The prompt is the
same 1,311-byte summer task used in the previous full repeat, including its
fixed reference date. DeepSeek Flash, DR off. Backend40fdeb28, Appbfe55afe.

| Measurement | Previous full repeat | Actual request-pool repeat |
| --- | --- | --- |
| Total elapsed | 480.158 s | 511.863 s |
| Main model calls | 50 reported responses | 81 actual dispatched requests |
| Independent analysis requests | 0 | 0 |
| Model interval sum | 392.756 s | 434.495 s |
| Tool invocations | 134 | 138 |
| Tool errors | 6 | 23 |
| First CSV publication | 184.59 s | 246.864 s |
| First PPTX publication | 445.96 s | 401.830 s |

Dispatch counts include SDK requests; the older response count is not a new
request-pool measurement. Actual pool peak was one: all requests used the main
chain. This trial does not verify simultaneous expanded analysis rows and does
not pass performance acceptance. Runtime queue support alone did not cause the
model to decompose this task into independent analysis calls.

The pane automatically selected the generated PPTX before completion. The first
PPTX had31 slides because content blocks paginated; repeated script edits and
checks followed. The final file has14 slides and7 media objects. Downloaded
705,836 bytes; ZIP integrity passed; SHA-256
`9b0cdab0032110f1670c2b6eb0d8ec4404577d6c2f6fb1759d7e64c4e5a8761e`.
Final core CSV:10,869 bytes,22 rows including header,28 consistent columns;
SHA-256 `ee263b1a062294d0876fc8f0f12bf73e9968b2dd1f4f3ff82df19e7a12051817`.
Vivaldi shows the final14-page preview. These are file/structure checks, not a
full factual review of all report conclusions.

Observed friction: unloaded tool calls, oversized tool-load batch, incomplete
metric identities, one SQL timeout, invalid SQL selection/arguments, result
wrapper parsing, JSON serialization and generated report script syntax errors.
The reusable renderer avoided custom drawing code but its block pagination
triggered report rewrites. The trace also repeats main request metadata below
each main LLM row; record this presentation issue for the next scoped fix.
Evidence: ignored `runs/summer-request-pool-20261030/events.json`, `summary.json`,
downloaded products and Vivaldi screenshot
`296498c3-cfe5-4822-ba15-b264e88fb4e8-screenshot.png`.

# Actual request dispatcher trial — 2026-10-30

Existing Vivaldi tab, new thread `thr_5a6451c5b3e073de3301`, DeepSeek Flash,
DR off. Actual dispatch records show 25 requests: 20 main and 5 analysis calls.
Peak actual concurrency was 2. Both original independent analyses completed;
the dependent summary started after both returned. CSV was published during
execution. The right pane automatically selected the generated PPTX while the
attempt was still running; a screenshot confirms its rendered first slide.
Final PPTX was downloaded: 38,185 bytes, three slides, valid ZIP, SHA-256
`43d7a0d670c24039769844de6127cb3ff280f68152a0149f8e67f7639ba5d03b`.
Evidence is in ignored `runs/request-pool-20261030/`.

This is functional verification, not speed acceptance. The model repeated two
analyses after collecting an empty unread list, although their answers had
already been delivered asynchronously. Collection now supports explicit job
IDs to read saved results again without another model request. The regression
failed before the change and passed after it; 23 Node and 25 Python tests pass.
The correction was rebuilt and verified in a second live trial below. Repeated report revisions
to meet an exact three-page request also increased this trial's model count.

The first rebuild hit Docker's 128-layer limit. Combining related COPY steps
reduced the executor image to 122 layers. Failed Compose creation left unused
Created containers; only those containers were removed, without volume removal.
The canonical rebuild then passed readiness and API/worker image equality,
image `477cb2f3fd0223c028fd6dc046a9a2f498a305219a312a84c6e2f686bf191fef`.
Scoped cleanup receipt: `cache-maintenance-20261029-235818-41621.log`.

Second Vivaldi trial: `thr_3ee477748b1cbc964ace`, 21.979 seconds, six main
requests and exactly three analysis requests, peak two. All three completed.
Repeated explicit-ID collection returned saved answers without resubmission.
This smaller trial omitted PPT generation; its time is not a speed comparison
with the first trial or the summer study. Evidence:
`runs/request-pool-reread-20261030/`. Current backend image:
`bf9e3f4e26ea5e07fbb25a9359421365b53fba49fd850bf42c42b5a0698c3d13`;
canonical rebuild and scoped cleanup passed, receipt
`cache-maintenance-20261030-001357-75675.log`.
# 2026-10-30 closeout decision

The user accepted simplifying the default path. The request and independent
analysis pools are now gated by the backend `CAPSTONE_EXPERIMENTAL_LLM_POOL=1`
experiment. Default is off. Tool composition, incremental artifacts and normal
model timing remain enabled. Existing pool records remain readable.

The scoped default/opt-in and actual SDK tests passed: 220 passed, 32 skipped
in 5.45s. The direct SDK fixture writes a CSV and returns an answer without pool
tools, pool guidance or pool events; ordinary model timing boundaries remain.
Localhost tests require `NO_PROXY=localhost,127.0.0.1` in this workstation's
proxy environment. Canonical rebuild, live check and dev integration are pending
at this record's creation. No speed improvement is claimed.

The [enterprise research discussion](../superpowers/specs/2026-10-30-enterprise-data-research-analysis.md)
and [roadmap](../superpowers/plans/2026-10-30-enterprise-analysis-roadmap.md) record
accepted future scope, including mandatory user acceptance of a result revision.
