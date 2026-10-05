# Thread client recovery and cloud-dev verification

## Candidate and release boundary

The current implementation candidate is
`188abe3536722623c2e85d596195de6f60401a16`. It includes client repair
`6b8eba8bf5fe0ce30cd4ef081ddd08f5d4889e6e`, hosted lease repair
`a1f028de4da1951599029b1cb7388e15db449ce8`, configuration diagnostics
`5dc0cd4`, and shared Harness Provider resolution.
Candidate 6b8eba8 passed M11 and browser checks, but failed normal PyPSA
acceptance; it must not be promoted. The a1f028d full release gate and cloud-dev
provider-free automatic acceptance pass. Human acceptance found missing normal
Provider configuration, recorded below; demo is unchanged.
The new shared-source local image and App checks pass; its full release gate
is recorded in the [Harness local record](2026-10-06-harness-provider-configuration-local-verification.md).
Further cloud deployment is held for local verification. Cloud-dev remains
on a1f028d in normal mode.
Cloud operations target only the
`capstone-cloud-dev` Railway project. Demo promotion requires completed
cloud-dev verification and the user's manual acceptance. No real Provider
validation is authorized in this work.

## Cause and change

A reconnect cleared the same-Thread snapshot and unmounted the Composer.
This discarded unsent input. A command whose server receipt was lost also
remained unresolved, without a way to check its original identity. A failed
event catch-up could make an already accepted command look unsent.

The App now keeps its same-Thread snapshot and mounted Composer during recovery.
Reconnect submits the exact unresolved command, with its original command ID,
idempotency key, payload, run and cursor. The server's existing command ledger
returns the original receipt. Fresh commands stay blocked until that receipt
is known. Accepted receipts remain accepted if event catch-up needs another
reconnect.

The Composer clears only the matching accepted submission, once. Rejected or
unconfirmed submissions retain their text. Model-directory actions and reruns
preserve an unrelated draft. This change stays in the App and preserves the
existing authority and current-run evidence contracts.

The extended switch/reopen rollback tests give the failed Context its own
distinct topology. Live recovery and reload restore the exact prior diagram,
layer and focus. Existing production code passes these tests; no further
topology change was needed.

## Client repair verification (6b8eba8)

- Seven recovery regressions failed before repair. Final App coverage passes
  255 tests in 21 files; the focused recovery suites pass 118 tests.
- TypeScript and Vite build pass. Vite retains its existing large-chunk warning.
- Relevant server transition, command and PostgreSQL contracts pass 16 tests;
  nine optional PostgreSQL tests skip without their separate test configuration.
- `make test-e2e`, `make validate` and `make doctor` pass. Registered E2E checks
  cover 39 cases and three worker checks; static-analysis coverage is 24/24.
- The full `make check-release` passes, including installed package smoke
  checks and fresh source setup. The existing npm setup audit reports one
  moderate and two high dependency findings; this task does not change dependencies.
- The real browser test let the server commit a command, then dropped its HTTP
  receipt. The draft remained. Reconnect recovered that original command and
  cleared the matching draft. Exactly one admitted Turn completed, with its
  authority-backed topology visible.
- The final `make capstone-local-rebuild` passed. API and both workers use
  `sha256:d1a758ac2d7ce05469c965f124b6804cfc754f0f49938d14e0c7531674b44a1b`.
  The user's local API and App remain running. Isolated browser test services
  are stopped and their task-owned credential file is removed.
- Independent reviewer dispatch failed because the collaboration tool reported
  an unavailable model. Self-review and the checks above completed; this record
  does not claim an independent review.

Local receipts are under ignored `runs/thread-client-recovery/`. The inspected
screenshot is `output/playwright/thread-client-recovery-local.png`. Induced
transport errors and isolated-preview 404s remain in that browser's test log.

## Rejected predecessor cloud verification (6b8eba8)

All four cloud-dev services deployed from predecessor 6b8eba8. The API
followed successful worker deployments. Their source messages identify the
same full revision; Railway built each service separately. The App's served
asset is `/assets/index-CerBb1pX.js`, SHA-256
`d83a4875fe733228f9f786a3f42cfb0d43679b86cde287642104e05af40ff339`.
It contains the new recovery code.

- The private M11 preflight verified both real-Authority workers in bounded
  provider-free mode. Five Thread attempts passed: two pandapower attempts in
  one Context, two PyPSA attempts in one Context, and another PyPSA attempt in
  a freshly reopened Context. Result and evidence identities matched each
  selected model, revision and Context. Both families were available.
- Public registered pandapower and PyPSA cases ran concurrently with that
  matrix. Both completed. Results, reports and every returned evidence ref
  were readable. No worker interruption was reproduced.
- The cloud browser submitted a fresh IEEE-39 analysis, let the server commit
  it, and then dropped its HTTP receipt. Its draft remained. Reconnect returned
  the original accepted receipt and cleared the matching draft. The server
  recorded one accepted command, one completed attempt and nine events.
- Browser refresh retained one answer and the same 154 SVG geometry elements.
  The matrix Thread displayed five completed answers. Selecting an old
  pandapower answer showed its IEEE-39 view while keeping the active PyPSA
  Context. Selecting the latest answer restored the six-bus view. Both cloud
  screenshots were inspected. The induced transport failure produced one
  expected browser console error.

Task-owned receipts, deployment identities and before-state settings are
preserved below ignored `runs/thread-client-recovery/`:

| Receipt | Scope |
| --- | --- |
| `cloud-deployment.json` | Source, service identities, runtime modes and previous settings. |
| `cloud-m11-provider-free/m11-812585b9180f4ec0.json` | Five real-Authority Thread checks. |
| `cloud-m11-provider-free/concurrent-b711674156cb.json` | Both concurrent cases, reports and evidence reads. |
| `cloud-browser-summary.json`, `cloud-browser-events.json` | One accepted command and completed attempt. |
| `cloud-browser-ui-summary.json` | Lost draft recovery, refresh and historical views. |
| `normal-readiness.json` | Normal runtime, public denials and retained results/history after redeployment. |

The source archive contains only the committed candidate and six verified
model assets. It excludes authentication and existing runtime state.

Normal runtime restoration passed. Both workers started before the API was
redeployed from the same source. The private validation endpoint returns 404.
API readiness and App health pass, with both families available in the registered
catalog. Nine public-boundary checks pass: Provider mode/options, an unknown
case, private Thread creation and private Thread reads remain denied. All eight
recorded result projections survive, with the same final model Context. The
browser Thread retains its nine events, one completed attempt and exact diagram
reference. The subsequent fresh normal-mode case failure is recorded below.

| Historical 6b8eba8 normal role | Deployment ID |
| --- | --- |
| API | `5e91c7a5-dd77-40d7-8c81-27590f5bf041` |
| pandapower worker | `05358112-3dee-440b-a383-5f4d4c7933a8` |
| PyPSA worker | `ea90d329-9d0f-42cb-8a5b-7ba96b7ed3b4` |
| App | `33d879fb-174e-45d7-9413-6fa27596f521` |

Normal registered PyPSA acceptance then reproduced `worker_interrupted` in
`session-4e6ffbf1ff8380d331f4a48f`, with one accepted and zero completed turns.
The historical receipt and new failed session are preserved. Normal-mode
acceptance is incomplete for 6b8eba8 despite its passing readiness checks.

## Hosted lease root cause and repair

The host started its renewal timer only after blocking worker startup returned
ready, then waited another lease_seconds/3 before renewal. The lease itself had
already started at claim. A 30-second lease with a 10-second renewal interval
could expire before that first renewal when startup exceeded 20 seconds.
Blocking evidence reads in the same owner loop could also suspend renewal.

Database timing shows creation→ready at 22.53 seconds for the new failed
session, 23.56 seconds for the historical failure, and 10.16 seconds for the
passing concurrent case. Both failures stopped before their first answer. The
allowlisted normal worker logs show no container restart during this case.
The relevant host code is identical in the historical 26c5cbe and 6b8eba8
revisions. These timings and the reproduction identify the startup renewal gap.

The repair renews the existing token in a bounded independent thread from
claim through startup, evidence retrieval and report storage. Known lease loss
blocks fresh commands and late report persistence. Renewal stops on completion
or failure. The ledger retains its existing atomic token fence. No authority,
domain action, Provider or answer-admission contract changes.

Three original-code regressions failed for blocking startup, evidence reads and
lease loss. Final isolated PostgreSQL host/session/API/ledger tests pass 35,
including late-report fencing and a startup longer than its one-second lease
while a real stale reaper runs. The same cold-start test fails against the
original host implementation. Types pass with zero errors. The task-owned test
container and its anonymous data volume were removed; user data is unchanged.

The a1f028d local rebuild passed with matching API and worker image
`sha256:9d02fbda319c99a5b8b7a352e08ce96bbaf05fec7966e1e9ac2d82e736111844`.
Fresh normal local pandapower and PyPSA cases passed reports and evidence reads
through the real entrypoint. Their receipt is
`runs/thread-client-recovery-lease/local-normal-legacy/legacy-7e56b3354c3f.json`.
The full a1f028d `make check-release` passes, including 469 Capstone Agent
tests, App255, Kernel567, registered E2E39+3, installed package smoke checks,
fresh source setup and 24/24 static-analysis coverage. Its optional database
tests skip34; the separate isolated PostgreSQL checks above pass35.

New-candidate receipts are under ignored `runs/thread-client-recovery-lease/`.
The old `runs/thread-client-recovery/` records remain intact.

## Repaired candidate cloud verification (a1f028d)

All four services deployed successfully from the exact a1f028d source archive.
The API followed both ready workers. Five new real-Authority M11 attempts passed,
along with concurrent registered pandapower and PyPSA cases, reports and all
returned evidence reads. The new matrix Thread is `thr_91fb415ba95a59460130`.

The fresh browser Thread `thr_ca2d367e8dd6fdbc1640` retained its draft after a
committed command lost its HTTP receipt. Reconnect recovered the original
accepted receipt and cleared that matching draft. Server evidence records one
accepted command, one completed attempt and nine events. Refresh retained one
answer and the same 154 SVG geometry elements. The five-answer matrix's old
pandapower view preserved the active PyPSA Context; the latest answer restored
the six-bus view. Both new screenshots were inspected. The named test browser
is closed. No Provider call was made.

| New receipt | Scope |
| --- | --- |
| `cloud-deployment.json` | Exact source and cloud-dev service identities. |
| `cloud-m11-provider-free/m11-753c80043bf243ab.json` | Five real-Authority Thread checks. |
| `cloud-m11-provider-free/concurrent-50f9088cf465.json` | Concurrent cases, reports and evidence. |
| `cloud-browser-summary.json`, `cloud-browser-events.json` | One recovered command and completed attempt. |
| `cloud-browser-ui-summary.json`, `browser-refresh.log`, `browser-history.log` | Draft, refresh and model-history checks. |
| `private-health-acceptance-complete.json` | Ready workers and zero active work before normal restoration. |
| `normal-readiness.json` | Normal API/App, public denials and retained Thread projections. |
| `cloud-normal/legacy-d72936ae7d4c.json` | Fresh normal registered cases, three turns per family, reports and evidence. |
| `private-health-normal-complete.json` | Both workers normal/ready and zero active work after acceptance. |

Normal variables were restored after the zero-active-work check. Both workers
then deployed successfully before the API, using the same exact source. All four
latest service source messages match a1f028d. The final normal runtime and
public-boundary checks pass: API and App are healthy, both registered families
are available, the M11 endpoint is disabled, and nine public access checks deny
Provider options, unknown cases and private Thread operations.

All eight matrix result projections, the final active Context, and the browser's
nine events, completed attempt and exact diagram reference survive redeployment.
The served App asset and its SHA-256 match the recovery build recorded above.
Fresh normal pandapower and PyPSA cases each completed three turns, with readable
reports and all returned evidence. PyPSA session
`session-eee22ca8f3eb12b370669241` completed without lease interruption. Both
workers are normal/ready, with zero active Thread attempts and legacy sessions.

| Final normal role | Deployment ID |
| --- | --- |
| API | `6193fd06-5413-4004-882e-0cbf747ad078` |
| pandapower worker | `1331b5df-223a-46c5-83ff-c6c91aff7292` |
| PyPSA worker | `6b23957a-d08a-4060-8482-ba313796d454` |
| App | `36737cc1-62ef-46ea-afab-6a244d1addf8` |

Manual review can use the retained
[cloud-dev matrix Thread](https://capstone-app-production-83ef.up.railway.app/?thread=thr_91fb415ba95a59460130)
with the existing cloud-dev operator login, and the
[registered-case page](https://capstone-app-production-83ef.up.railway.app/old).
The matrix allows read-only history, results and evidence review in normal mode.
New private Thread analysis and real Provider behavior are outside this
provider-free acceptance. Do not submit a new private instruction without
separate Provider authorization.

Demo remains unchanged until manual acceptance of the completed cloud-dev
candidate.

## Manual review: normal Provider configuration gap

The user logged in and submitted “有哪些 PyPSA 的电网模型？”. Two Attempts in
Thread `thr_2e360be463f03926b5d4` failed at runtime construction, including retry:
`attempt_9c3df4681e20436f` and `attempt_442e699d91bda7de`. The active Context
remained IEEE-39/pandapower. Both failed with `capability_context_preparation_failed`.

Read-only SSH checks of both cloud-dev workers reproduce `ConfigurationError`
during Provider resolution. Both select DeepSeek; neither has DEEPSEEK_API_KEY.
No new Provider request was made. Task evidence is under ignored
`runs/thread-runtime-diagnosis/inspection.json` and `failure-metadata.json`.
The prior provider-free matrix and scripted-case checks do not cover normal
Provider configuration. Their passing receipts remain valid for that scope.

The deployed a1f028d worker labels every prepared factory exception as a capability
failure. Repair that classification at the application/Harness seam, preserve
the prepared model Context for configuration errors, and show safe configuration
repair guidance. Regressions must cover both families and the App. Run focused
checks, rebuild the actual local API/worker/App, then verify a new exact candidate
on cloud-dev. Normal real-Provider smoke requires a dedicated cloud-dev key and
explicit authorization; never copy demo credentials or publish secrets.
Manual acceptance and demo promotion remain blocked until this gap is closed.

## Configuration error repair (5dc0cd4)

Both application composition roots translate Provider `ConfigurationError` into
neutral `HarnessRuntimeConfigurationError`. The worker persists only the fixed
`runtime_configuration_invalid` code. It does not roll back a valid prepared
Context for that error. Actual capability preparation failures retain the existing
rollback behavior. The App explains that AI configuration needs administrator
repair before retrying. Raw exception text, credentials and their values remain
outside public events and reader-facing answers.

Three new regressions fail against the previous source, then pass after repair.
The family suites pass 3 pandapower and 5 PyPSA checks. Relevant Thread worker,
application and attempt checks pass 48, and the conversation component passes 34.
The 5dc0cd4 local rebuild passed with API and both workers using image
`sha256:bc01b2cba0567988838b9c44375b8d1e0534fc5994ec975d7a50f72f451bd0e0`.
Real hosted factories in isolated in-memory sessions inside that image pass both
missing-configuration checks. Their evidence is
`runs/thread-runtime-config-repair/local-missing-configuration.json`. Those
checks use a deliberately absent credential in the isolated process and make
zero Provider requests; user sessions and protected stage settings are untouched.

The first source archive remains preserved under ignored
`runs/thread-runtime-config-repair/`; it was not deployed. The user then required
shared Harness ownership and local App verification before further cloud work.
`188abe3` centralizes Provider resolution in Capstone and makes both historical
adapters delegate. Its verification and the local-first release gate are in the
[Harness local record](2026-10-06-harness-provider-configuration-local-verification.md).
Normal cloud conversation still requires the missing dedicated cloud-dev
Provider key and authorized real-Provider validation.
