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
