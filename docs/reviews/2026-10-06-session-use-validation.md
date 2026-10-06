# Cloud-development user-use validation

The earlier cloud-development checks proved selected deployment and work paths.
They did not establish repeated-use and concurrent-use acceptance. A successful
catalog answer could depend on an unrelated tool call and hide a routing defect.
Expanded cloud-development automated acceptance now passes for the bounded
scope below. Demo remains at `c68f6e1`; it has not received these fixes.

## Candidate and defects

Backend candidate: `4dfd79260fdf874ac26af67ccd94dcb8a93f6062`.
The App source is unchanged from the existing hosted App.

| Defect | Cause and correction | Regression evidence |
| --- | --- | --- |
| New Thread rejected while a worker prepares a model | Health reads waited for the preparation lock. Publish immutable resource counts and read them without waiting for model I/O. | Failing blocked-preparation regression; actual cold-worker creation and cancellation pass after rebuild. |
| Unknown model returns HTTP 500 | Registration raises `LookupError`; handlers caught only `KeyError`. Catch the published lookup failure at creation and model-switch boundaries. | Four failing regressions; creation returns 422 and switching returns `model_unavailable` without changing the Thread. |
| Model-directory question intermittently fails | Auto routing treated every domain keyword as a calculation. A reference-free answer from the application catalog then failed `capability_required`. Route availability questions as information; mixed calculation requests stay professional. | Ten catalog routing regressions first fail; mixed calculation regression first fails; all pass after correction. Original question succeeds three times across both families. |

The repairs belong to the application. Authority calculations, Domain Pack
admission, current-run lineage and the Harness calculation evidence gate are
unchanged.

## Local prerequisite

Canonical rebuild passes. API and both workers share image
`sha256:10412070214996b8c49297ce35c44839049bb6df6a4fb2bbe30b4e8617e24e8d`;
343 backend source files match the checkout in each role. Runtime contract and
logical artifact hashes agree.

Final candidate checks: 531 backend tests pass, 35 optional PostgreSQL tests are
skipped, types and package boundaries pass, and `make doctor` passes. Final
integration checks pass: 39 E2E tests, three real registered-worker tests,
offline/scripted validation and application-instantiation validation. Full
`make check-release` also passed for preceding repair `b86a82a`; the receipt
distinguishes that full gate from the final affected and integration gates.

Final rebuilt runtime passes three original catalog requests, both families'
real calculations with current-run lineage, twenty empty Threads without
retained worker contexts, App reconnect/draft/mobile checks, and retained report
and evidence reads. Preceding `b86a82a` also passes actual write replay/conflict,
cancellation, cross-family switching, history paging, stream capacity and local
API/worker interruption and retry. These receipts retain their actual revisions.

Evidence directory: `runs/session-use-validation-20261006/`.
Local prerequisite: `local-acceptance.json`; cloud results use the separate
`cloud/` directory. No credentials are stored in the receipts.

## Cloud-development acceptance

All 17 phases complete with exit code zero. The backend source is frozen at
`4dfd792` throughout cloud validation. All 343 backend files match local in
the API and both workers. Runtime contract and logical artifact hashes match
local. Both workers report Provider readiness. The unchanged hosted App selects
only the cloud-development API origin.

| Role | Deployment | Final status |
| --- | --- | --- |
| API | `65d87af8-b734-492a-832e-5b9d5843de12` | SUCCESS |
| pandapower worker | `d0a148fe-65dd-44d0-b866-c0e17c193655` | SUCCESS |
| PyPSA worker | `af4e90af-3de9-4a63-8f92-40a3b22bcb7c` | SUCCESS |

| Check | Observed result |
| --- | --- |
| Empty Threads | Twenty new records retain no worker context. |
| Original catalog question | Three separate Threads across both families return all 21 registered PyPSA model IDs without result or evidence references. The visible App submission also completes. |
| Sequential work | Ten distinct Threads alternate pandapower AC power flow and PyPSA dispatch plus AC validation. All complete with current-run authority and lineage checks. |
| Concurrent submissions | Three, then six submissions complete. Actual execution peaks at two tasks. Each answer retains its own Thread/run/model lineage. |
| Long use and models | Four follow-ups complete. The same Thread switches to PyPSA, calculates, returns to pandapower and calculates. History paging returns 190 events over 19 ordered pages without duplicates. Current diagram projection contains three events. |
| Write conflicts and stale clients | Identical replay admits one Attempt; conflicting replay, stale cursor and overlapping same-Thread work return their specific conflicts. Resync permits subsequent work. |
| Unknown model | Creation returns HTTP 422; switching reports `model_unavailable` and preserves the selected context. |
| Cancellation and cold preparation | Creation succeeds during cold worker preparation. Queued and running cancellation reach terminal states; fresh work then completes. |
| Stream capacity | A third same-Thread subscription is rejected. Global limit is 32; the driver admits 31 of 33 subscriptions while an existing browser occupies capacity. Disconnect restores capacity. |
| App recovery | Root entry and the visible New button work. Offline/online and reload preserve the draft and completed answer; composer recovers. Screenshots are inspected. Widths 320 and 390 have no horizontal overflow. |
| Reports and retained data | Both families' registered scripted cases, report/result hashes and evidence replay pass. Prior reports and terminal Thread events survive redeployment unchanged. Scripted public credentials remain unable to use the Provider. |
| Final idle state | With the App still open, both workers report zero retained and active contexts. Active Thread Attempts and legacy sessions are zero. |

## Resource measurements

The table reports sampled combined working memory of the API and two workers.
Working memory is cgroup current memory minus inactive file cache. It is not
the complete stage memory or a billing measurement.

| Workload | Completion range, seconds | Actual peak executing | Peak working MiB | Post-idle working MiB |
| --- | --- | --- | --- | --- |
| Ten sequential Threads | 25.6–72.1 | 1 | 1063.7 | 515.0 |
| Three simultaneous submissions | 25.0–67.6 | 2 | 1189.2 | 513.4 |
| Six simultaneous submissions | 35.2–216.0 | 2 | 1304.6 | 527.5 |
| Four same-Thread follow-ups | 31.6–44.4 | 1 | 1101.1 | 530.8 |

Initial combined working memory before sequential work is 509.0 MiB. Idle
memory remains about 0.5 GiB after repeated work; process counts return to two
per role. All four workload observations report zero retained and active worker
contexts after a 75-second idle observation. The selected cache idle policy is
60 seconds. Sample intervals include remote probe time; their maximum ranges
from 16.5 to 18.3 seconds, with zero probe errors. Peaks between samples are
not measured.

Three submissions have a maximum queue wait of 24.15 seconds. Six have a maximum
queue wait of 137.92 seconds and total latency of 216.0 seconds. This demonstrates
bounded queueing with two execution lanes, not six simultaneous calculations.
Sampled CPU peaks across these runs are 8.7% for the API, 191.1% for pandapower
and 155.6% for PyPSA, where 100% means one CPU. Raw combined cgroup current
memory peaks at 1576.1 MiB in the six-submission run.

The current cloud
limit is eight CPUs and 8,000,000,000 memory bytes per backend container. This
does not mean the entire stage has a shared eight-GB limit.

Destructive process faults are tested locally against owned work. This rollout
also checks that retained cloud Thread answers and reports survive redeployment.
It does not deliberately kill cloud workers during user work.

These representative registered calculations establish basic trial behavior
within the tested load. Larger models, prolonged production traffic, database
and object-storage growth, and total cloud cost need separate measurements.
Persistent Thread history and evidence remain stored; idle eviction releases
runtime resources and does not delete records.

The sealed receipt is `runs/session-use-validation-20261006/cloud-acceptance.json`.
Metrics, phase receipts, screenshots and the standalone memory chart are under
`runs/session-use-validation-20261006/cloud/`. All six agent-owned debug Chrome
sessions are closed after capture and the final idle check.

See the [validation plan](../superpowers/plans/2026-10-06-session-load-and-recovery-validation.md)
and [release lifecycle](../architecture/capstone-development-lifecycle.md).

The cloud-validation task itself did not update demo. After this validation,
the user explicitly requested demo deployment. The
[separate promotion report](2026-10-06-demo-promotion-4dfd792.md) records that
release and its deployed checks.
