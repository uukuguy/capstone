# M11 federated Thread acceptance

Scope correction: this receipt covers the restricted scripted M11 matrix.
It does not establish ordinary conversation model-open correctness. The user
later reproduced a model/context mismatch. Its diagnosis, local repair and
verification are in the [Thread model state repair](2026-10-05-thread-model-state-repair.md).

Status: **complete**. All required M11 acceptance checks passed on 2026-10-05.
Local and cloud-development runtimes are restored to normal mode.
Provider validation was not run. The user-trial stage was not changed.

## Source and scope

- Tested and deployed runtime source: `26c5cbe151b85b6a11fbd677c50a2ac4270cd17c`.
- App send/parser fix: `4550444`; typed read-only history/focus guards: `26c5cbe`.
- Additional receipt-boundary and exact-Attempt rejection tests: `a421276`.
  This commit changes tests only; the deployed runtime remains `26c5cbe`.
- Main checkout contains the accepted implementation. No push or user-trial
  promotion was performed.
- Cloud-development project: `5eecde6b-fec2-40d2-8b26-427025b02b96`;
  Railway environment: `5afd6aeb-07a6-4320-92e9-4bf193a442cb` (`production`).
- Clean Git archive and six locally verified model assets formed the upload.
  Local authentication state was excluded.
- Manifest and exact image digests:
  `runs/capstone-m11/closeout-cloud/deployment.json`.
  Evidence under ignored `runs/` and `output/` is operator-local; a fresh
  checkout does not contain it.

## Required acceptance

Every row below passed. Local negative checks, real remote execution, browser
acceptance, and legacy reports are separate evidence.

| Requirement | Result | Evidence and limit |
| --- | --- | --- |
| Deployment identity | Passed | Four roles use the tested runtime source; manifest records deployment IDs, digests, prior settings and rollout order |
| Catalog and health | Passed | Actual private worker health on port 8080 binds each family; normal API/App healthy and both catalog families available |
| Family ownership | Passed | Real PostgreSQL matching-family claims and negative cross-family claims; remote matrix executes both actual workers |
| Context reuse | Passed | Five-step HTTP matrix repeats each current model without replacing its Context or prepared Authority binding |
| Switching and reopening | Passed | One Thread switches IEEE-39 to regional-six-bus; explicit reopen records a new Context and reason |
| PyPSA topology | Passed | Actual prepared Attempts emit admitted diagram/layer events at the matching Context/revision, six buses and seven branches |
| Results and evidence | Passed | Matrix binds current-run result/evidence refs and exact Attempt/model/revision; real local admission tests reject foreign refs |
| Web replay | Passed | Real cloud App restores five answers, admitted result cards, diagram and cursor 53 after reload and one aborted SSE request/manual reconnect |
| Safe focus | Passed | Separate real IEEE-39 result focuses admitted line:0 and changes the camera; actual history focus is declined; foreign-revision and unknown-element fixtures also pass locally |
| Retained history | Passed | Both workers restart from tested deployments; fresh process starts confirmed. Snapshot, 53 events, reports/results/evidence and six legacy network views retain identical fingerprints; actual Web replay matches |
| Reports and artifacts | Passed | Both public registered legacy cases complete three turns and expose reports/evidence in validation and restored normal modes |
| Public access | Passed | Only registered scripted cases run; Provider mode/options and unknown cases return403; public Thread creation and private Thread reads/catalog/events/stream return404 |
| No Provider I/O | Passed | Early-selection/bypass tests and runtime preflight/receipts establish bounded deterministic execution with no Provider fallback. No Provider-backed command was submitted |

Primary current receipts:

- Local matrix: `runs/capstone-m11/closeout-local/m11-faf0287e278146e8.json`.
- Remote matrix: `runs/capstone-m11/closeout-cloud/m11-a26ef61e37b34c64.json`.
- Cloud Web: `web-replay.json`, `web-focus.json`, `web-after-restart.json`
  and `web-normal.json` in `runs/capstone-m11/closeout-cloud/`.
- Retention: `retention-before.json`, `retention-after.json` and
  `retention-normal.json` in the same directory; all three are identical.
- Worker restart proof: `worker-process-after-restart.json`;
  both process starts follow the pre-restart zero-active-work check.
- Legacy cases: `closeout-cloud/legacy-c56af052c042.json` and
  `closeout-cloud-normal/legacy-95dfb0689182.json` under `runs/capstone-m11/`.
- Normal restoration: `normal-readiness.json` and
  `private-health-closeout.json`; flags are empty, the private validation
  endpoint returns404, both workers report normal mode, and active work is zero.
- Browser screenshots: `output/playwright/m11-cloud-web/`.
  The result card, Authority diagram and positive focus were visually inspected.

## Deployment and replay identities

| Role | Validation deployment | Final normal deployment |
| --- | --- | --- |
| Unified API | `21e0b3d0-ad3a-431d-bc66-ba83c27455a6` | `816c1e1d-e362-4781-97b0-769863fd7d96` |
| pandapower worker | `8bdd7b85-fe23-4d32-a565-4212020e8e94` | `dd1e748d-40fd-4a64-bb58-a3cf737f25e7` |
| PyPSA worker | `b798945b-45dc-4cfd-867e-be53fdffe37e` | `fdf697fd-62d6-4998-9c27-dd431b08c01a` |
| App | `e5a5c711-9ff3-416e-aaab-5b52bed66f17` | Same deployment |

Backend application selectors are respectively `capstone`, `pandapower`
and `pypsa`; all backend ports are 8080. Both workers remain one running
replica. API startup followed verified worker readiness. Final deployments
all report success and the recorded runtime source. The App build selects
only the API origin.

The remote matrix Thread is `thr_f644a1c24eb95426d20c`, Run
`run_f644a1c24eb95426d20c`; active reopened PyPSA Context is
`ctx_945c70653649e26a6387`. Its model revision is
`revision:sha256:062d4fbd54bc4b45f0d53a84a9739b798adeb1e71de8b678a878492b2ee538cf`.
The browser receipt agrees with the HTTP receipt and cursor 53.

Positive focus uses Thread `thr_f6f93c79e02e16c83e53`, Attempt
`attempt_bd256326158d3364`, and its actual admitted element `line:0`.
No fabricated event entered the shared ledger. Restart checks read committed
history only; no turn was sent on an old process-local Context.

The task-owned SSH registration, local key copies and browser sessions were
removed. Temporary PostgreSQL tests used a separate container, which was
removed. Main `var/`, application databases, buckets and completed replay
data were retained.

## Local fixes and gates

- Unknown model phrases now retain their text and submit through `send_auto`.
  This fixes the confirmed “打开 case24_ieee_rts 电网模型” interception.
  The requested model remains absent from the registered catalog; it was
  not invented or added by this fix.
- Commands use unique identities after refresh. Explicit rejections are shown
  and restore the input draft. Normal `model_switch` events parse correctly.
- Typed history restores model tabs and matching Context/model/revision views.
  Missing retained topology has an explicit unavailable state. History blocks
  sends, model/profile changes, retry and result focus; live cancellation remains.
- App: 191 tests and TypeScript/Vite build passed. Local current-source rebuild
  and doctor passed; API and both workers share the normal local image.
- Full `make check-release` passed, including E2E 39 + 3, capability coverage 24/24,
  installed-package smoke and frozen source setup:
  `runs/capstone-m11/closeout-local/check-release.log`.
- Disposable PostgreSQL checks:11 Thread,16 ledger/worker and9 API/artifact tests
  passed. Required added validation checks:17 tests and type check passed.
- Independent task, App and full backend/deployment reviews approved the source.
  Review artifacts are in ignored `.superpowers/sdd/`; receipt-test task
  compliance and test quality were also approved.

## Failed attempts and limits

The earlier cloud App rejected `model_switch`; the local regression reproduced
and fixed that parser defect. A browser initially reused old cached HTML
(`index-FZWKSbUZ.js`) after rollout. Loading current resources
(`index-CDljbaik.js`) removed the fault. Fresh real Web checks then passed.
The published asset fingerprint is in `app-source-check.json`.

The first parallel legacy smoke completed pandapower, then PyPSA session
`session-c51b61a1f1e0591176d531f3` became `worker_interrupted`.
This failed attempt is retained in `legacy-initial-failure.json` and
`legacy.log`; its root cause is not established. Same-source serial
validation and normal-mode legacy checks subsequently passed. M11 does not
claim concurrent legacy/Thread reliability from that failed attempt.

The historical IEEE Context has no retained diagram, so the real Web displays
explicit unavailability. Historical projection retention is additionally
covered by local typed fixtures. PyPSA has no result focus target in this
scenario; positive focus is proved with the separate actual IEEE result.
`model.validate` explicitly lacks a result presentation projector.

Remaining client follow-ups are draft recovery after uncertain transport
failure and exact cached-diagram restoration after live model rollback.
They predate these changes and do not block the bounded M11 acceptance.
Provider natural-language behavior, process-local execution recovery and
user-trial promotion remain separate actions.
