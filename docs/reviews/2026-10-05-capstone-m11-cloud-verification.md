# M11 federated Thread acceptance

Status: implementation, local gates, remote HTTP acceptance and restart
retention passed. Cloud Web acceptance remains blocked by the browser connection.
Normal cloud mode is restored. M11 is not complete.
Do not treat this record as user-trial release approval or Provider validation.

## Source and scope

- Runtime/deployment source: `595e602`.
- Additional refusal tests: `e128789`; no runtime change.
- Implementation is integrated into the main checkout.
- Remote target: `capstone-cloud-dev`, project
  `5eecde6b-fec2-40d2-8b26-427025b02b96`, environment `production`.
- The exported deployment source contains tracked files and verified model
  assets. It contains no local authentication state.
- Provider validation was not run. The user-trial stage was not changed.

## Evidence

| Check | Result | Evidence and limit |
| --- | --- | --- |
| Public scripted admission and private session isolation | Passed locally | Focused Python/Thread creation: 29 passed; App client: 10 passed |
| Scope persistence and family-filtered PostgreSQL leasing | Passed locally | 19 tests on disposable `m11_test`; no application database cleanup |
| Real pandapower/PyPSA prepared execution | Passed locally | Each domain environment: 2 passed, 1 opposite-family skip |
| Refusal of foreign result refs, unknown instructions and exhausted sequence | Passed locally | Real admission checks plus bounded-context regression |
| M5 transport extraction compatibility | Passed locally | Existing real-Authority M5 checks passed in both environments |
| Full offline release gate | Passed | `runs/capstone-m11/check-release.log`; E2E 39 + 3, App 171, coverage 24/24, installed-package and source-setup checks |
| Current-source local rebuild | Passed | `runs/capstone-m11/local-rebuild.log`; API and workers share one image |
| Local cross-family Thread matrix | Passed, 5/5 | `runs/capstone-m11/local/m11-eaa0c4e146bd44f2.json` |
| Local legacy public cases, reports and evidence | Passed | `runs/capstone-m11/local/legacy-8598f41b55a3.json`; both registered cases completed |
| Local restoration to normal mode | Passed | `runs/capstone-m11/local-restore.log`; PyPSA health reports `normal` |
| Remote deployment/source identity | Passed | All four validation deployments use `595e602`; IDs below; manifest records digests and prior settings |
| Remote family readiness and no-Provider preflight | Passed | Private preflight verified both worker family identities and `m11-provider-free` mode before mutation |
| Remote Context reuse, switch and reopen | Passed, 5/5 | `runs/capstone-m11/remote/m11-750fa3caf36f4202.json`; production HTTP matrix |
| Remote admitted results and M10 topology | Passed | Same receipt binds exact Attempt, Context, revision and admitted refs; each PyPSA diagram has 6 buses and 7 branches |
| Remote public cases, reports and evidence | Passed | `runs/capstone-m11/remote/legacy-ff2198411ada.json`; both cases completed 3 turns; public Provider creation returned 403 |
| Local Web replay/focus regression and build | Passed | 32 tests; `runs/capstone-m11/app-focus-tests.log` and `app-build.log`; production build passed with a bundle-size advisory |
| Cloud Web refresh/reconnect and safe focus | Pending | Chrome connection still times out after approved new-window recovery; plugin reinstall requested. Positive live focus and historical-page checks are unverified |
| Committed history after worker restart | Passed | `runs/capstone-m11/remote/retention-before.json` and `retention-after.json` match: snapshot, 53 events, reports/results/evidence and six legacy network views; active work was zero before restart |
| Normal cloud runtime restoration | Passed | Validation opt-in cleared; private workers report `normal`; private validation endpoint returns 404; API/App healthy and both catalog families available. `runs/capstone-m11/remote/normal-readiness.json` and `normal-worker-health.json` |
| Normal-mode public scripted cases | Passed | Both applications completed 3 turns with reports/results/evidence; `runs/capstone-m11/remote-normal/legacy-08a7ec68d8dd.json` |
| History after normal-mode restoration | Passed | `runs/capstone-m11/remote/retention-normal.json` matches the before-restart fingerprint |

The local matrix Thread is `thr_9e1c5119b3188eb7d61c`. Its pandapower turns
share one Context; its two PyPSA turns share a second Context; explicit reopen
activates a third Context. Each PyPSA topology has six buses and seven branches.
The receipt binds all results and evidence to their completed Attempts.

## Remote identities

All entries below target cloud development and use source `595e602`.
The exact full revision and image digests are in the operator-local manifest
`runs/capstone-m11/deployment.json`. Receipts under `runs/` are ignored local
evidence; a fresh checkout does not contain them.

| Validation deployment role | Deployment ID |
| --- | --- |
| Unified API | `e666dbf9-128c-4f43-ae36-2088ef622d9f` |
| pandapower worker | `b5373c0b-3efb-41b7-9bc9-ddcdea204fac` |
| PyPSA worker | `b9f33710-a52b-470f-ace6-46014076847c` |
| App | `1c428e30-4f1c-4308-87cd-962b4fc337e7` |

The final normal-mode deployment IDs are API
`c7fe98e9-3e92-47ab-b826-2ca4af09f758`, pandapower worker
`8aa5840f-4d26-4477-a2d3-e120032a3786`, and PyPSA worker
`3e8348ab-31dc-4984-be26-c9775ad864c1`. The App deployment is unchanged.
The API reused its exact verified image. Both workers retain the same tested
source revision. `CAPSTONE_THREAD_VALIDATION` is empty on all backend roles;
no normal-mode Provider work was submitted. Public Thread creation and private
Thread reads return 404 with the demo credential.
The task-owned temporary SSH key registration and key files were removed.
The disposable PostgreSQL test container was stopped; application data was retained.

The remote matrix Thread is `thr_2353b828e0025c28f556`, with Run
`run_2353b828e0025c28f556`. Its successive Contexts are
`ctx_2353b828e0025c28f556` (pandapower), `ctx_ceeb37c861a5f2bc9742`
(PyPSA), and `ctx_bbcdf60b24f6dddb20df` (reopened PyPSA).
Legacy sessions are `session-f030e0539705eb58948a3bd1` and
`session-856a781ad34af75cc2ebdd7e`.

Restart verification reads committed history only. It does not establish
recovery of process-local Authority state or in-flight execution. No turn
was submitted on the old Context after restart.

## Remaining acceptance

The actual cloud App still needs refresh, reconnect, current diagram and
positive safe-focus inspection through the browser. The local 32-test suite
checks replay and refusal behavior but cannot close that row. Resume with the
remote Thread above after the browser plugin connection works. Do not enable
Provider execution to complete these read-only Web checks.

Open the existing Thread at
`https://capstone-app-production-83ef.up.railway.app/?thread=thr_2353b828e0025c28f556`.
Use the current cloud-development operator credential through the password
field. The local cached Railway operator token did not match the current
service; the failed 401 preflight created no Thread. Current credentials were
read from protected service configuration in memory only.

## Implementation findings

Inline source review checked the persisted public scope and creation hash,
private/public idempotency isolation, early validation selection in both
adapters, disabled ordinary routing in validation mode, prepared model and
binding identity checks, family-filtered leasing, and Attempt/Context/revision
matching in the HTTP matrix. No additional runtime change was required.
The PostgreSQL family-refusal checks ran against the disposable database;
the remote matrix separately exercised both production family workers.

The PyPSA application admits both the source and operations bindings. The M11
script therefore calls the existing `model.validate` on the prepared source
before dispatch. It does not open or derive an extra model or change admission.
Model switch and reopen commands first create pending state; the next submitted
message activates that state. The matrix checks this existing lifecycle.

The runtime has no Provider fallback in validation mode. A private readiness
endpoint checks the two configured worker identities before any driver mutation.
Validation state is bounded to 64 contexts and refuses new contexts at capacity.
Receipt files contain bounded IDs/counts and use mode 0600.
