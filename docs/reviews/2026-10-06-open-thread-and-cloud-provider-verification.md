# Direct Thread entry and cloud Provider recovery

The user requests direct workbench entry during function validation, using the
existing Provider credentials. The local App must pass before any cloud-dev
deployment. Demo promotion still requires human acceptance.

## Current acceptance: bounded Thread resources

Source `c68f6e1f9aab5d6b5e3781aff21903a8ce704ae2` is verified locally.
Cloud-dev acceptance for this source also passes at12:25 CST. Earlier cloud
results below apply to their stated revisions.

The shared runtime contract limits each model-context owner to four retained
contexts. Idle contexts expire after60 seconds; active Attempts pin their
resources. Workers sweep without new commands and close resources on shutdown.
Pi execution has a600-second deadline. Each API process allows32 live Thread
streams and two per Thread. Disconnects release capacity. Wake throttling uses
one timestamp instead of a growing session-key map.

| Current local check | Result and receipt |
| --- | --- |
| Final checkout rebuild | API and both workers share image `sha256:ad92c6dd93b2673b72969f180f29f476325a67713654371503bf245e5dab3a33`;343 backend source hashes match; `runs/thread-lifecycle-local-rebuild-final.log` and `runs/thread-lifecycle-local-verification/source-identity.json` |
| Shared startup contract | All three roles match contract `48d470f5626f3b2abfd8a7c483f569f7e32721384dd343142b71cafdb80fa5ef` and artifact `ee02a0309ea1e5f1966236f86a652d91ea240980e2c6675c2b2d1aafe1ac7d05`; `runtime-receipts.json` in the same directory |
| Backend and App gates |509 backend tests pass,35 optional database tests skip;266 App tests pass; types, boundaries, build and doctor pass |
| Integration gates |39 grid E2E tests and three registered worker tests pass; `make validate` passes; `runs/thread-lifecycle-integration.log` |
| Active and idle resources |Running calculations show an active pinned context. Both workers later show retained0/active0 while the App remains open; `resources-active.json`, `resources-pypsa-active.json` and `resources-final-idle.json` |
| Cold Thread reuse |The same Thread completes the exact PyPSA catalog question after context eviction;21 registered models, zero result/evidence references; `catalog-cold-accepted.json` |
| Retained history |Both owned Threads remain readable after eviction; `history-after-idle.json` |
| Actual calculations |Pandapower AC power flow completes with two result references and three evidence references. PyPSA dispatch and AC validation complete with six result/evidence references; `pandapower-accepted.json`, `pypsa-accepted.json` |
| Actual stream limit |An extra subscription receives503 with Retry-After2; closing an admitted stream permits another; `stream-capacity.json` |
| Small App controls |User/session list and automatic naming are deferred. The earlier-conversation action is12px; real paging works, desktop/mobile screenshots are inspected and320px has no horizontal overflow; `history-ui.json` |

The local acceptance receipt is `runs/thread-lifecycle-local-acceptance.json`.
The first attempted cloud preparation failed before any upload or variable change:
the documented Railway API endpoint failed its TLS handshake through the
configured proxy and a direct connection. Connectivity recovered at12:08;
an authenticated project read succeeded. The root cause of that connection
failure remains unconfirmed. The guarded rollout then aligned the six shared
resource-policy variables without automatic deployments and reused existing
credentials. Demo was not changed.

| Current cloud-dev check | Result and receipt |
| --- | --- |
| One verified-source rollout |All four services succeed from `c68f6e1`: worker `9aa3e6ed`, PyPSA worker `2d494a7c`, API `3080cdb9`, App `9cdf0b94`; `runs/thread-lifecycle-cloud-verification/cloud-deployment.json` |
| Local/cloud alignment |343 source files match in each backend role; the contract and artifact hashes above match all three roles; `backend-source-identity.json`, `local-runtime-by-role.json`, `cloud-runtime-by-role.json` |
| Root App and existing Thread |Direct open mode, both families ready, old history retained, old draft survives deployment, small12px New control works; new owned empty Thread is archived after the check; `readiness.json`, `browser-ui.json` |
| Exact reported question |The original Thread, kept open across the API update, completes “有哪些 PyPSA 的电网模型？” with21 registered models; attempt `attempt_c45da07a19a46e35`, zero result/evidence references; `catalog-accepted.json` |
| Current-run calculations |Pandapower AC power flow succeeds with one result and two evidence references, attempt `attempt_09b6b8ef67ba713f`; PyPSA dispatch and AC validation succeed with five result/evidence references, attempt `attempt_717458778ce34efd`; both authority-backed and their calculation projections complete |
| Active-work protection |Private worker health reports retained1/active1 during each family's calculation; `private-health-pandapower-active.json`, `private-health-pypsa-active.json` |
| Cold Thread reuse |After the pandapower cache reaches0, the same Thread completes another catalog Turn, attempt `attempt_e4a79b351814b0ec`; `private-health-after-physics.json`, `catalog-cold-accepted.json` |
| Idle cleanup with page open |Both worker caches reach retained0/active0, with zero active Thread Attempts and compatibility sessions; old histories still read; `private-health-final-idle.json`, `history-after-idle.json` |
| Stream cleanup |Actual extra stream receives503/Retry-After2; closing an admitted stream permits another200; `stream-capacity.json` |
| Small history action |Actual API pages limited to10 events exercise earlier-message loading,12px text/26.5px action,32px row and320px no overflow; `history-ui.json`; cloud desktop/mobile screenshots were inspected |
| Cases, reports and evidence |Both registered cases execute again, close and produce readable reports/evidence; `scripted/legacy-0867fe602b9c.json`. Previously retained reports match their hashes and evidence replays; `report-evidence-replay.json` |

Cloud receipt paths in this table are relative to
`runs/thread-lifecycle-cloud-verification/`. The final acceptance receipt is
`runs/thread-lifecycle-cloud-acceptance.json`. Four actual AI Turns were submitted;
scripted checks use no Provider. Two operator-check mistakes were corrected:
runtime receipts were initially keyed by service names instead of contract
roles, and a bundle-string check matched a retained transport error message.
The source/hash comparisons and actual absence of the deferred UI passed.
Human acceptance remains pending before demo promotion.

## Control-plane transport follow-up

The user's next request is to handle the connection fault instead of treating
recovery as its resolution. Local evidence confirms that the configured HTTP
proxy route completes TLS and reaches the Railway endpoint, and the existing
CLI account login reads the selected project. A subprocess with proxies removed
and NO_PROXY set to `*` reproduces a TLS connection reset with the same login
state. This is a network-path failure; changing credentials cannot repair it.

The local Clash core runs in global mode with TUN disabled. Its transport log
shows a configuration reload at11:54:26; Railway requests in the original
11:57–11:59 failure window and12:07 recovery window all use GLOBAL. The reload
is a correlation, not proof of the earlier proxy-path disconnect's cause.
[Railway's status page](https://status.railway.com/) currently reports operational
service and notes that isolated faults may not appear. Neither source identifies
the exact upstream hop that failed during the original proxy-path interruption.

`deploy/railway/control_plane.py` now reuses the existing CLI login. Explicit
queries and lists retry transport errors at most three times; authentication,
permission and certificate errors stop with distinct safe codes. Writes invoke
the CLI once; lost responses require deployment/variable-state reconciliation.
The active rollout helper uses these functions. No new credential, proxy-global
change, App gate, upload or Provider call was introduced.

Ten focused tests pass, including transient-read recovery, bounded failure,
credential-safe error output and no duplicate write invocation. The actual
proxy project check succeeds; the direct reproduction returns
`network_unavailable`, route direct, attempts3. A deployment-state read through
the integrated helper still reports the four verified deployments as SUCCESS.
Receipts: `runs/railway-control-plane-{red,green}.log`,
`runs/railway-control-plane-live-{proxy,direct}.json`,
`runs/railway-control-plane-rollout-read.log`,
`runs/railway-network-diagnosis.json`. This handles transient reads and diagnosis;
it does not claim to repair an unidentified upstream proxy outage.

## Retained state and scope

Eviction releases runtime resources; it does not delete durable history,
results or evidence. Storage retention and cleanup of expired history/artifacts
remain planned work with explicit preservation rules. This acceptance does not
claim that old authority-result references can be reused in a fresh workspace.
Independent reviewer creation failed due to the tool's unavailable model;
the root agent reviewed the change and ran the checks above.

## Change

`CAPSTONE_THREAD_OPEN_ACCESS` selects anonymous Thread access. Local Compose
defaults to open mode; cloud-dev selects it explicitly. The App reads only the
mode from `/api/v1/thread-access`, creates one Thread under StrictMode and sends
no browser token in open mode. Provider secrets stay in worker environment
variables. The older scripted-demo credential retains its separate scope.

New conversation sits beside the conversation heading.
The user defers the user system and history-session management. The active
App keeps a small New conversation action; list/archive controls and automatic
LLM title requests are removed. The former user/title checks below are historical
receipts, not acceptance of the current reduced scope.
The active App keeps new conversation, bounded history, draft and reconnect
paths. Existing server archive records are retained.

Local real acceptance also found two PyPSA failures in the shared Thread bridge:
an unused operations Pack downgraded verified model observations, and published
guide reads lacked calculation provenance. Admission now uses participating
Packs and treats reference-free published guide reads separately. Unknown tools,
unowned references and failed participating Packs retain their rejection rules.

The Thread runtime also omitted the existing Kernel model-handoff contract.
The Application bridge now prepares typed, current-workspace receipts under
declared grants, verifies the bound model or its descendants, persists/replays
the receipts and gives Pi the private index. Target tools receive only the
granted handoff. No domain semantics or raw models were moved into the Kernel.

## Local verification

| Check | Result and receipt |
| --- | --- |
| Actual root App | Empty browser authentication enters directly at5173; `runs/thread-open-local-browser-layout.log` |
| Navigation and drafts | New/switch/reload drafts pass; `runs/thread-open-local-browser-session-result.log` |
| Archive and restore | Restored metadata is active and composer accepts input; `runs/thread-open-local-browser-archive-final.log` |
| Mobile layout |390px and320px have no horizontal overflow; both controls44px; `runs/thread-open-local-mobile.log`; inspected screenshots under `output/playwright/thread-open-local-mobile-*` |
| App tests |267 pass in full release log; TypeScript and production build pass |
| Thread admission |45 pass, including two red/green regressions and fail-closed ownership checks; `runs/thread-open-admission-green.log` |
| Real authority handoff |Base and derived PyPSA dispatch, replay and foreign-reference rejection pass; `runs/thread-open-handoff-derived.log` |
| Current backend and boundaries |489 pass,35 skip; package boundaries pass; `runs/thread-open-final-admission-gates.log` |
| PyPSA tests |39 pass; `runs/thread-open-final-pypsa-tests.log` |
| Types and doctor |Pass; `runs/thread-open-final-types-verified.log`, `runs/thread-open-doctor.log` |
| Full release |`make check-release` exits0; `runs/thread-open-local-release.log`; later bridge changes have the focused gates above |

The local catalog question and pandapower AC power flow complete in real AI
Turns. Local success is a regression result; the original missing-key fault is
cloud-only. Final source `9846d48093cefa64907c34ed1c5e95018722eba2` rebuilds with
shared image `sha256:22599a9903ea44f356fbdbeb772f7aca0f4ad1992309d39ddbf6952c2e0f0511`.
All341 Python source files match in API and both workers. Actual PyPSA model
opening, economic dispatch and AC validation complete with current-run authority
references and completed result projections. Both registered scripted cases,
reports and evidence reads pass. Six real local AI Turns were submitted; two
failed discovery Turns preceded the repair. Final acceptance is recorded in
`runs/thread-open-local-acceptance.json` and the referenced command receipts.
Earlier failed local QA Turns remain in their owned histories; they are not
successful acceptance receipts.

## Cloud-dev acceptance

The first cloud rollout uses locally verified source `9846d48` in normal mode.
All four deployments succeed and341 Python files match in API and both workers.
Both workers resolve the existing Provider credential from protected variables.
The actual hosted root enters without a browser token. The exact reported
question, “有哪些 PyPSA 的电网模型？”, completes with21 registered models.
Local catalog success was only a regression check; this cloud receipt is the
proof of recovery from the cloud-only configuration failure.

Pandapower AC power flow completes with current-run result/evidence references
and a completed bounded projection. Both registered scripted cases, reports and
evidence reads pass. New conversation, switching and reload retain separate
drafts. The original interrupted PyPSA open attempt is retained: at30.1s it
fails with `lease_expired`, so this rollout is not accepted as a complete
functional release. Receipts remain under `runs/thread-open-cloud-verification/`.

## Attempt lease repair

The Thread worker renewed only through runtime callbacks. Preparation, authority
observation, continuous runtime events and post-answer admission can block or
starve those callbacks. Cloud model opening exposed this fault. Local five-phase
tests fail before the repair and pass after it. The Application now renews an
owned Attempt independently through routing, preparation, startup, prompt,
admission and projection. The direct Harness entry uses the same guard. Lost
leases fence prompt/event/commit work; renewal stops when the Attempt ends.
The existing database token and expiry checks remain authoritative. A failed
worker iteration now returns to polling instead of killing its background
thread; a regression verifies that the next admitted task can complete.

The isolated local PostgreSQL check passes with a1s lease and each of the five
phases blocked for1.25s; it makes no Provider calls. Real local PyPSA opening
and economic dispatch complete with current-run references. Final source
`9cbdc13c40523e4a8b9060851abe703e8c01df46` rebuilds as shared API/worker image
`sha256:be80cb8647c92e475eb12b7efc31a55cf0399def48f0403cb8fc4eb26da2b214`;
all342 Python files match. The existing browser reconnects after the rebuild
and the same Thread completes economic dispatch plus AC validation. Both
operation projections are completed. Current backend498 tests (35 optional
database skips), focused48, types, boundaries and doctor pass. Earlier full
release gates remain the baseline; the lease repair has these current checks.
The exact-source receipt `runs/thread-lease-local-acceptance.json` passes before
any new cloud upload. Three additional real local AI Turns cover this repair.

Cloud preflight finds no active Attempt/session, but detects the previous
PyPSA worker health as unavailable after its polling thread exits. The repaired
rollout uploads only the three backend roles; the unchanged verified App stays
on9846d48. Existing protected Provider configuration is retained. Final cloud
acceptance is pending under `runs/thread-lease-cloud-verification/`.

## Configuration and startup parity

Cloud9cbdc13 backend deployments succeed and all342 Python files match. Both
workers are healthy with normal Provider configuration, but API readiness
acceptance rejects PyPSA model availability. API startup captured the worker
before it was ready and never refreshed the snapshot. No actual AI requests
were submitted after this failed readiness check.

Local regression coverage now checks family health recovery and loss without
API restart, for both memory and PostgreSQL service projections. The shared
versioned workbench profile and launcher fix role commands and runtime
selectors, validate worker Provider presence and wait for both workers before
API startup. Base images use registry-verified multi-platform digests. Private
receipts record source/config/lock/package/model alignment without secrets;
`deploy/verify_host_runtime.py` rejects any local/cloud mismatch. Infrastructure
origins, credentials and capacity remain stage-specific. These repairs require
fresh local App acceptance before a further cloud rollout.

Final local source `1c8073f427f2e2c3eb9bddd5d64222eff55bb42c` passes a new
rebuild as `sha256:36cebe04e5ef8f2325466d422030c2a8462f20093f81358ce4a3b03968931d85`.
All342 Python files match. The three startup receipts match contract
`14a004387954e1e32653077302d57d9b6955e5c8f1f1972e5fb4872257d3053e`
and logical artifact
`7cb83ec64c938fbb57a522b58edce2dbcbae83ef7762e59ad8292dc8461c5d9d`.
Actual PyPSA worker stop/recovery changes model availability without API restart.
The existing browser reconnects and its Thread remains usable. In that Thread,
catalog attempt `974716ea0edf1d89` lists every registered PyPSA model and explains
application switching instead of inferring global unavailability from scoped
tools. Opening attempt `1ad6be1b628a24df` and dispatch/AC attempt
`1bb1fc2bbf7c3d80` complete with current-run results/evidence. The two calculation
projections are completed. The owned QA Thread is archived with history retained.
The final desktop screenshot was inspected. Full `make check-release` passes,
along with25 startup checks and502 focused backend checks, types, boundaries and
doctor. Exact-source local receipt `runs/runtime-parity-local-acceptance.json`
passes before cloud configuration or uploads.

The subsequent cloud rollout selects only the runtime profile with automatic
deployments skipped and retains existing credentials. It gates API upload on
both new workers reaching SUCCESS with healthy normal runtimes and matching
local artifact/contract hashes. Cloud actual functional acceptance remains
pending under `runs/runtime-parity-cloud-verification/`.

Demo remains unchanged. This record does not claim human release approval.
