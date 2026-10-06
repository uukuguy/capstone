# Demo load validation

The user requested direct load validation of the deployed demo. This run uses
the user-trial project `a7a503b3-9f48-480d-8090-f063bab3b8db`, API
`https://capstone-api-production-ec73.up.railway.app`, and App
`https://capstone-app-production-975e.up.railway.app/`.

Backend source is `4dfd79260fdf874ac26af67ccd94dcb8a93f6062`. Fresh deployment
status, 343-file source checks, runtime contract checks, readiness and open-root
checks pass. The API and both workers use the accepted backend. This test makes
no application, deployment, environment, credential, replica or limit changes.
The [promotion report](2026-10-06-demo-promotion-4dfd792.md) remains a separate
record of functional deployment acceptance.

## Test scope and evidence

Private receipts are stored under `runs/demo-load-validation-20261006/`.
The suite measures registered IEEE-39 AC power flow and two-bus economic
dispatch plus AC validation. Every numerical completion requires current-run
result and evidence references with authority admission and verified lineage.
The test covers ten sequential Threads, three simultaneous submissions, a
guarded increase to six submissions, and four follow-up turns in one Thread.
Additional checks cover empty Threads, write replay and conflicts, cancellation,
model switching, history pagination, subscription limits and idle cleanup.

Resource probes read cgroup memory, CPU usage, process counts and private health.
Working memory is `memory.current - inactive_file`. It is sampled rather than
continuously traced. CPU percentages use 100 percent for one CPU. Values cover
the API and two workers; database, object storage and total billed usage are
separate. Each backend container has its own eight-CPU and 8,000,000,000-byte
limit. These are not a shared whole-project eight-GB budget.

The two worker families provide two execution lanes. Three or six simultaneous
submissions test queueing; they do not imply three or six executing calculations.
The test creates only owned validation Threads, preserves existing reports and
evidence, and injects no process failure into the demo. No debug browser is opened.

## Observed functional failure

The initial catalog query completes, but its text says there are 21 registered
PyPSA models and omits `congested-two-bus`. A direct catalog read confirms that
all 21 models are registered. This is an incomplete LLM answer, not a missing
cloud model asset. Result and evidence references are empty as required for
informational answers. The exact terminal event and independent catalog are
preserved in `catalog-repeat-recovery.json` and `catalog-diagnosis.json`.

This failure is kept separate from numerical load results. It prevents a claim
that every demo function passed. Numerical load testing continues on the same
deployed revision; no cloud repair is performed during the run.

## Numerical load results

| Workload | Completed | End-to-end time | Longest queue | Combined sampled working-memory peak | Post-idle working memory |
| --- | --- | --- | --- | --- | --- |
| Separate sequential Threads | 10/10 | 34.2–60.6 s | 0.25 s | 1214.2 MiB | 684.6 MiB |
| Three simultaneous submissions | 3/3 | 35.5–69.6 s | 34.20 s | 1338.3 MiB | 684.2 MiB |
| Six simultaneous submissions | 6/6 | 38.1–157.8 s | 101.21 s | 1310.1 MiB | 686.6 MiB |
| Same-Thread follow-ups | 4/4 | 29.0–45.9 s | 0.26 s | 990.7 MiB | 687.9 MiB |

All 23 load turns complete with admitted results and evidence. Each phase has
a 75-second idle observation. Both workers return to zero retained and active
contexts, and initial/idle process counts remain two per role. Resource probes
have no errors. Actual maximum sample intervals range from 15.9 to 18.8 seconds;
shorter spikes may not appear in the samples. The maximum combined raw cgroup
memory sample, including file cache, is 1630.7 MiB.

PyPSA idle working memory rises from 130.0 to 243.4 MiB during the sequential
phase, then stays near 243 MiB after the next three phases. Pandapower idle
working memory moves from 305.6 to 308.4 MiB; API idle memory stays near 136 MiB.
This bounded run shows stable memory after warm-up. It does not prove the absence
of leaks during prolonged use or across all registered large models.

Sampled CPU peaks are 8.8 percent for API, 191.4 percent for pandapower and
158.9 percent for PyPSA. The two workers execute at most two overlapping
Attempts. The longer six-submission wait is caused mainly by queueing:
the last PyPSA Attempt queues for 101.21 seconds, then executes for about
55.97 seconds. Queue delay, rather than observed memory pressure, is the main
constraint in this run.

## Recovery and capacity checks

| Check | Observed result |
| --- | --- |
| Twenty empty Threads | No worker context allocation. |
| Write replay and conflicts | Identical replay creates no extra Attempt; conflicting, stale and overlapping commands are rejected. Resync permits new work. |
| Unknown model | Creation returns 422; failed switching preserves the selected context. |
| Cancellation | Queued and running Attempts terminate; the cancelled Thread accepts and completes new work. |
| Existing Thread model changes | PyPSA dispatch plus AC validation completes; switching back to pandapower permits a new AC calculation. |
| Long-history projection | 200 ordered, unique events across 20 pages; current diagram remains bounded to three events. |
| Event stream limits | Third same-Thread stream rejected; global test accepts 32 streams and rejects the 33rd. Disconnect restores capacity. |
| Prior stored report | Report/result hashes unchanged; evidence remains readable. |

The final idle observation exceeds 75 seconds; combined working memory is
692.6 MiB. Both workers are ready with zero
retained and active contexts. The database reports zero active Thread Attempts
and zero active legacy sessions. All three backend deployment IDs remain
unchanged and SUCCESS. The suite exits zero and seals
`runs/demo-load-validation-20261006/acceptance.json` with status
`passed_bounded_demo_load_with_catalog_issue`. The earlier catalog failure is
preserved; this receipt does not grant full functional acceptance.

For these two small registered models, the observed resource use supports basic
trial with a small number of users. Three simultaneous submissions finish in
about 36–70 seconds; six finish in about 38–158 seconds. Higher queue delay is
visible at six. This is a bounded demo test, not sustained production capacity
or large-model coverage. The independently measured demo results replace no
earlier [cloud-development receipt](2026-10-06-session-use-validation.md).

The memory chart is stored at
`runs/demo-load-validation-20261006/resource-memory.png` and was visually
inspected. Numerical pressure, protocol and resource checks pass. The incomplete
catalog answer remains a separate functional defect. A repair must follow the
[local-to-cloud release lifecycle](../architecture/capstone-development-lifecycle.md);
this test makes no direct change to the demo.

The later [catalog repair release](2026-10-06-catalog-completeness-promotion.md)
closes this observed defect on source `39007a1` after local, cloud-development and
demo verification. The load measurements and failed catalog receipt above
remain the historical record for `4dfd792`; the complete pressure suite is not
repeated for the catalog-only repair.
