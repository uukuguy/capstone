# M11 Cloud-development Federated Thread Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Prove remote pandapower/PyPSA Thread execution, Authority topology,
result admission, and Web replay in the isolated cloud-development stage,
without Provider calls.

**Architecture:** Keep the existing federated API and family-filtered workers.
Inject source-registered deterministic sessions at the prepared session-builder
boundary for validation; retain the real PostgreSQL, Harness, Domain Packs,
Authority binders, result admission, and M10 topology provider. Correct public
demo access before remote testing.

**Tech Stack:** Python 3.12+, uv-managed separate domain environments,
FastAPI, psycopg/PostgreSQL, React/TypeScript/Vitest, Docker Compose, Railway.

**Approved specification:**
[M11 design](../specs/2026-10-05-capstone-m11-cloud-federated-thread-design.md).
The user approved the written specification on 2026-10-05.

## Global Constraints

- Only API and App have public domains.
- Existing cloud-dev data is retained.
- Unknown instructions and unsupported scenarios fail explicitly.
- This mode must not fall back to a Provider.
- Keep deterministic scripts in validation-owned source.
- Default runtime behavior remains unchanged.
- Provider billing, user-trial promotion, data migration, source-trigger changes,
  and secret rotation are excluded.
- Three backend roles use one tested source revision or one exact image digest.
- Model facts, numbers, revisions, results, and evidence come from Authorities.
- Retained replay after a restart does not prove recovery of process-local
  Authority state. Do not claim that recovery.
- Preserve main-worktree `var/`, ignored credentials, and unrelated changes.
- Local API, worker, or App changes require `make capstone-local-rebuild` before
  remote validation. A skipped required check never counts as a pass.

## File and responsibility map

| Task | Files | Responsibility |
| --- | --- | --- |
| 1 | `packages/capstone-agent/src/capstone_agent/{host_api,ledger,hosting}.py`, their tests; `packages/capstone-app/src/{api.ts,api.test.ts}` | Scripted-only public admission and persisted access scope |
| 2 | `validation/thread/{scripted_session,m11_session}.py`, `validation/thread/provider_free_host.py`, `validation/test_m11_session.py` | Extract the existing deterministic transport; add bounded M11 scenarios |
| 2 | `packages/capstone-agent/src/capstone_agent/hosted_validation.py`, both domain adapters' `hosted.py` and tests | Select validation sessions before any Provider resolution |
| 2 | `packages/capstone-agent/src/capstone_agent/{cli,host_api,worker_wake}.py` and tests | Private, bounded validation-mode readiness before Thread creation |
| 3 | `validation/thread/m11_matrix.py`, `validation/run_m11.py`, `validation/test_m11_matrix.py`, `Makefile` | Remote Thread driver, bounded evidence receipt, explicit pass/fail/skip |
| 4 | `deploy/railway/README.md`, `deploy/railway/cloud-dev.variables.example`, `compose.yaml`, `tools/tests/test_deploy_entrypoint.py` | Role-specific deployment settings, local validation mode, remote rollout |
| 5 | Existing Web regression suites; `docs/reviews/2026-10-05-capstone-m11-cloud-verification.md`; state files | Browser/restart acceptance and durable closeout |

No Domain Pack or Kernel semantic changes are planned. If real Authority
acceptance fails, diagnose the cause before widening scope or weakening checks.

## Task 1: Enforce the public scripted-session boundary

**Modify:**

- `packages/capstone-agent/src/capstone_agent/host_api.py`
- `packages/capstone-agent/src/capstone_agent/ledger.py`
- `packages/capstone-agent/src/capstone_agent/hosting.py`
- `packages/capstone-agent/tests/test_public_demo_api.py`
- `packages/capstone-agent/tests/test_host_ledger.py`
- `packages/capstone-agent/tests/test_hosting.py`
- `packages/capstone-app/src/api.ts`
- `packages/capstone-app/src/api.test.ts`

**Interfaces:** Add `SessionRecord.public_demo: bool = False` as the last
dataclass field, and `public_demo: bool = False` as a keyword-only argument to
`Ledger.create_session`. The API sets it from authenticated request state;
request JSON must not set it. Do not expose it in the public status projection.

- [x] **Step 1: Replace the existing inverted public-demo regression.**

Use `DemoLedger`, `WorkerSpec`, and `TestClient` in `test_public_demo_api.py`.
Extend the fake ledger signature to retain the server-owned `public_demo` flag.
The positive request must be:

```python
created = client.post('/api/v1/sessions', headers=demo, json={
    'application_id': 'pandapower-static-analysis',
    'mode': 'scripted-demo', 'case_id': 'pandapower-scripted-task',
})
assert created.status_code == 201
record = ledger.sessions[created.json()['session_id']]
assert record.public_demo and record.provider is None and record.model is None
```

Parameterize rejected creation over `mode=provider`, explicit `provider`,
explicit `model`, and an unregistered case. Assert 403. An operator-created
scripted session with the same registered case is still private: demo status,
turn, close, disconnect, events, result, report, evidence, network, and
network-story requests must all return 404 before storage access. Also deny
private Thread creation/read/commands. Prove the operator can read its own
session and can still create Provider sessions without executing them.

- [x] **Step 2: Run the red tests.**

```sh
uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_public_demo_api.py -q
npm --prefix packages/capstone-app test -- src/api.test.ts
```

First change the App creation-key assertion to expect `scripted-demo`; both
suites must fail for the current Provider-oriented behavior.

- [x] **Step 3: Persist scope without migrating historical data.**

Use the existing `create_hash` text field. Preserve the exact legacy hash for
private requests and prefix only new public hashes:

```python
_PUBLIC_CREATE_PREFIX = 'public-demo:v1:'

def _creation_hash(application_id, mode, case_id, provider, model, *, public_demo):
    digest = hashlib.sha256(
        repr((application_id, mode, case_id, provider, model)).encode()
    ).hexdigest()
    return _PUBLIC_CREATE_PREFIX + digest if public_demo else digest
```

`_session` decodes `public_demo` from that prefix; absent/null or legacy hashes
mean private. Keep positional fields compatible. Use the scoped hash for the
existing idempotency comparison, so a public request cannot recover a private
session via a matching creation key. Do not change old rows, indexes, or schema.

Inside `create_session`, reject invalid public modes/options before ledger
mutation, pass `public_demo=request.state.public_demo`, and never inject fixed
Provider settings for a public request. `get_session` requires all of:

```python
record.public_demo
record.mode == 'scripted-demo'
(record.application_id, record.case_id) in public_cases
record.provider is None and record.model is None
```

Apply that check once in the shared accessor already used by all session
routes. `CAPSTONE_PUBLIC_DEMO=true` must no longer require Provider/model
configuration during startup. Preserve those optional environment names for
private hosted Pi defaults. Change `CapstoneClient.createSession` to send
`mode: 'scripted-demo'`; preserve its idempotency header and retry policy.

- [x] **Step 4: Verify persistence and compatibility.**

Add ledger tests for public scope surviving a fresh `Ledger` instance, old
private hashes remaining readable/idempotent, and same-key cross-scope
creation producing `Conflict`. Use a disposable local PostgreSQL database
with `CAPSTONE_TEST_DATABASE_URL` supplied from ignored state, never arguments.
Do not run fixture cleanup against cloud or user-trial databases.

```sh
uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_public_demo_api.py packages/capstone-agent/tests/test_host_ledger.py packages/capstone-agent/tests/test_hosting.py -q
npm --prefix packages/capstone-app test -- src/api.test.ts
```

Expected: all relevant assertions pass; database tests must run, not skip.

- [x] **Step 5: Commit only this task's eight files.**

Commit message: `fix: restrict public demo credentials to scripted sessions`.
Append the commit and verification result to `docs/status/JOURNAL.md`.

## Task 2: Add bounded validation sessions on the prepared runtime

**Create:** `validation/thread/scripted_session.py`,
`validation/thread/m11_session.py`, `validation/test_m11_session.py`,
`packages/capstone-agent/src/capstone_agent/hosted_validation.py`,
`packages/capstone-agent/tests/test_hosted_validation.py`.

**Modify:** `validation/thread/provider_free_host.py`,
`packages/grid-agent/src/grid_agent/hosted.py`,
`packages/pypsa-agent/src/pypsa_agent/hosted.py`,
`packages/pypsa-agent/tests/test_hosted_thread.py`,
`packages/capstone-agent/src/capstone_agent/cli.py`,
`packages/capstone-agent/src/capstone_agent/host_api.py`,
`packages/capstone-agent/src/capstone_agent/worker_wake.py`,
`packages/capstone-agent/tests/test_worker_wake.py`.

**Interfaces:** `select_validation_builder(environment, family)` in
`hosted_validation.py` returns `PreparedKernelSessionBuilder | None`.
`build_m11_session_builder(family)` in validation-owned `m11_session.py`
returns that same callable type. Both families use its existing signature:
`(claim, prepared_context, profiles) -> PiPromptSession`.

- [x] **Step 1: Extract the existing reusable transport without behavior changes.**

Move `_refs`, `_load_pandapower_questions`, `_load_pypsa_case`, and
`_ScriptedPiSession` from `provider_free_host.py` into `scripted_session.py`.
Keep their existing behavior for M5 and re-export the names used by M5 tests.
The extracted module must not import `TestClient`, `httpx`, or
`InMemoryThreadService`. Leave the M5 in-memory host in its original module.
Run `validation/test_m5_provider_free.py` separately in the two domain
environments; each environment is expected to skip only the other family.

- [x] **Step 2: Add red selector and denial tests.**

```python
def test_validation_requires_explicit_cloud_development_stage():
    import pytest
    from capstone_agent.hosted_validation import select_validation_builder
    with pytest.raises(ValueError):
        select_validation_builder({
            'CAPSTONE_THREAD_VALIDATION': 'm11',
            'CAPSTONE_DEPLOYMENT_STAGE': 'user-trial',
        }, 'pypsa')
    assert select_validation_builder({}, 'pypsa') is None
```

Also reject unknown validation values/families. Patch each adapter's
`resolve_llm`, `PreparedKernelPiRpcSessionBuilder`, and normal runtime-host
construction to raise if called; build and execute a validation Attempt with
dummy Provider values present. No patched callable may run. Test arbitrary
text, wrong model/family, stale prepared context, sequence exhaustion, and
state exhaustion as failures, never as Provider fallback.

- [x] **Step 3: Implement the selector and wire it before Provider resolution.**

```python
def select_validation_builder(environment, family):
    selected = environment.get('CAPSTONE_THREAD_VALIDATION', '')
    if not selected:
        return None
    if selected != 'm11':
        raise ValueError('Thread validation selection is invalid')
    if environment.get('CAPSTONE_DEPLOYMENT_STAGE') != 'cloud-development':
        raise ValueError('Thread validation requires cloud development')
    if family not in {'pandapower', 'pypsa'}:
        raise ValueError('Thread validation family is invalid')
    from validation.thread.m11_session import build_m11_session_builder
    return build_m11_session_builder(family)
```

Add proper `Mapping[str, str]` and `PreparedKernelSessionBuilder | None`
annotations using the existing production alias. Import only the fixed
validation module after selection; never import a caller-supplied module.
Source deployment already copies `validation/` into the image. Installed
normal packages must import successfully without that source directory.

In each hosted application factory, select the builder once. At the first line
of the nested `build_session`, return the selected validation builder when
present; otherwise follow the existing Provider path. Return the assembled
application with `ordinary_conversation_enabled=False` and `turn_router=None`
when validation is selected. Preserve the existing PyPSA
`network_projection_factory`; do not rebuild an alternate Harness.

Add a read-only preflight for the validation driver. Extend `create_wake_app`
with optional `runtime_mode` and `implementation_family` keyword arguments;
its private `/health` reports their bounded values with the existing status.
Set them from validated startup configuration in `cli.py`, not request input.
Normal mode is `normal`; selected deterministic mode is `m11-provider-free`.

Add optional `validation_status: Callable[[], Mapping[str, object]] | None`
to `create_host_app`, defaulting to None. Only a cloud-development API with
`CAPSTONE_THREAD_VALIDATION=m11` wires the callback from `hosted_validation.py`.
It probes the two configured family health origins with a two-second timeout
and an 8 KiB response limit. Require exactly the expected family identities,
ready health, and `m11-provider-free` mode from both workers. Serve its bounded
result on private `GET /api/v1/validation/m11`; demo access or an unwired
callback gets 404, mismatch/unreachable workers gets 503. Success is:

```json
{"schema":"capstone-m11-readiness/1","runtime_mode":"m11-provider-free","families":["pandapower","pypsa"]}
```

This endpoint accepts no runtime selector and can perform no work. Test it
with normal, missing, and wrong-family workers. The driver must check it before
creating any Thread or issuing any command, including after reconnect. A
preflight failure must produce zero mutating requests. Keep runtime settings
fixed while the matrix runs; restore mode only after the driver terminates.

- [x] **Step 4: Implement the M11 session as a strict transport specialization.**

Reuse `_ScriptedPiSession`'s executor invocation, semantic events, and
`_build_kernel_admission` callback. Override instruction/argument preparation
and state initialization for M11. Use these exact registered scenarios:

| Family/model | Instruction sequence | Published operations |
| --- | --- | --- |
| pandapower / ieee39 | `验证当前 IEEE-39 模型的交流潮流。`, then `复用当前 IEEE-39 Context 再次验证交流潮流。` | Each invokes `analysis.powerflow.ac.run` with the prepared `context_ref` and `algorithm=nr` |
| pypsa / regional-six-bus | `验证当前区域六母线模型的固定容量调度。`, then `复用当前区域六母线 Context 再次验证固定容量调度。` | Each invokes `model.validate`, then `operations.dispatch` through the existing source-to-operations reference handoff |

Initialize `context_ref`/`model_ref` from `profiles[0].model_binding.context_ref`.
Do not call `context.open`, `model.open`, or model derivation in these scripts.
The production binder already opened the model. Use the existing application
grant and `ReferenceHandoffService` for dispatch; do not invent a handoff ref.

Keep sequence state in the builder instance, keyed by
`(claim.run_id, claim.model_context_id, claim.selection_revision)`; verify the
full immutable prepared model identity before state access. Cap the map at
64 contexts; reject a new context at capacity instead of evicting/resetting an
existing sequence. A fresh reopened Context starts at step zero. Keep state
out of public snapshots and release it when the builder process exits.
Do not claim in-flight recovery across a validation-worker restart.

Answers use actual Authority results through the existing admission and result
projector. A nonnumeric completion statement is sufficient. Tool event call
IDs use `m11-<attempt_id>-<index>` to identify deterministic transport in the
remote evidence; do not add unknown fields to public protocol documents.

- [x] **Step 5: Exercise real Authorities and M10 wiring.**

In `validation/test_m11_session.py`, build each real hosted assembly in the
correct environment with an isolated workspace. Use production
`run_pending_attempt` and the actual prepared runtime. Assert admitted refs,
Context reuse over both steps, new Context on explicit reopen, and matching
PyPSA `network_diagram`/`network_layer` events. No fake admission or raw Network
fixture can satisfy these assertions. Add negative foreign-reference admission
and unknown-instruction tests using real contexts. Keep provider mocks as
tripwires only.

```sh
uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_hosted_validation.py -q
PYTHONPATH=. uv run --project packages/grid-agent pytest validation/test_m11_session.py validation/test_m5_provider_free.py -q
PYTHONPATH=. uv run --project packages/pypsa-agent pytest validation/test_m11_session.py validation/test_m5_provider_free.py packages/pypsa-agent/tests/test_hosted_thread.py -q
make check-types-validation
```

Expected: selector tests and both family-specific real execution tests pass;
only tests for the uninstalled opposite family skip.

- [x] **Step 6: Commit the task-owned transport, selector, adapter, and test files.**

Commit message: `feat: add bounded provider-free hosted Thread validation`.

## Task 3: Build the remote matrix and its receipt

**Create:** `validation/thread/m11_matrix.py`, `validation/run_m11.py`,
`validation/test_m11_matrix.py`. **Modify:** `Makefile`.

**Interfaces:** `run_matrix(session: HttpThreadSession) -> list[dict[str, object]]`
uses the production client from `capstone_agent.thread_http` (not the M5
in-memory host). `main() -> int` in `run_m11.py` reads environment only:
`CAPSTONE_M11_API_ORIGIN`, `CAPSTONE_M11_OPERATOR_TOKEN`,
`CAPSTONE_M11_RECEIPT_DIR` (default `runs/capstone-m11`).

- [x] **Step 1: Test terminal-state handling before writing the driver.**

Use `httpx.MockTransport` with the production client. Cover a rejected command,
missing or normal-mode preflight (assert no subsequent POST requests),
accepted command followed by `attempt_failed`, success followed later by a
matching topology event, cursor resync, stale foreign-context topology, and
deadline expiry. An accepted command or absent current Attempt is not proof of
successful completion. A success without matching M10 events fails topology.

```python
def test_missing_remote_configuration_is_not_success(monkeypatch, tmp_path):
    from validation.run_m11 import main
    monkeypatch.delenv('CAPSTONE_M11_API_ORIGIN', raising=False)
    monkeypatch.delenv('CAPSTONE_M11_OPERATOR_TOKEN', raising=False)
    monkeypatch.setenv('CAPSTONE_M11_RECEIPT_DIR', str(tmp_path))
    assert main() == 2
```

Run `PYTHONPATH=. uv run --project packages/capstone-agent pytest validation/test_m11_matrix.py -q`;
expect missing-module/function failures before implementation.

- [x] **Step 2: Implement this exact normal-API sequence.**

Before creating a Thread, perform `GET /api/v1/validation/m11`. Require the
exact readiness schema, runtime mode, and both family identities from Task 2.
Do not infer runtime mode from client environment or a deployment label.
Then create the Thread and check catalog availability for both required models
before submitting a command. `session.catalog()` requires the created Thread:

```python
snapshot = session.create('ieee39')
catalog = session.catalog()
assert all(any(model.model_id == required and model.available
               for model in catalog.models)
           for required in ('ieee39', 'regional-six-bus'))
first = session.command('send_professional', {
    'text': '验证当前 IEEE-39 模型的交流潮流。',
})
```

Retain the created IDs and require `first.status == 'accepted'`.
Read `first.target` and ordered
events to bind the exact Attempt. Use a monotonic deadline of 180 seconds per
Attempt, 1-second polling, and the client's bounded 10-second HTTP timeout.
Fetch all event pages until caught up; require `attempt_completed`, reject
failed/cancelled/interrupted outcomes. Keep collecting after completion until
the corresponding topology events arrive or the deadline expires.

Then submit the second IEEE-39 instruction and compare active Context IDs.
Switch with `session.command('switch_model', {'model_id': 'regional-six-bus'})`.
Refresh the snapshot after each command. Do not require control commands to
create an Attempt. Run both PyPSA instructions; assert the same PyPSA Context
and exact revision and admitted result projection. Explicitly reopen using:

```python
receipt = session.command('reopen_model_context', {
    'model_id': 'regional-six-bus',
    'reason': 'M11 validation requires a fresh Authority context',
})
```

Submit the first PyPSA instruction to activate the pending reopen. Then require
a new Context ID and a `model_context_reopened` event. Validate topology with the existing normalizers in
`capstone_agent.thread_network` and `capstone_agent.network_diagram` and match
event Attempt/context identity. Compare projections to snapshot-admitted refs;
do not accept refs mentioned only in answer text.

On failure, attempt cancellation only of the driver's own active Attempt.
Preserve already committed history. Do not enumerate or cancel unrelated work.

- [x] **Step 3: Emit a bounded receipt and add the Make entry.**

Receipt schema is `capstone-m11-validation/1`; fields are `api_origin`,
`runtime_mode` (`m11-provider-free`), `thread_id`, `run_id`, `checks`, and
`provider_validation` (`not_run`). Each check contains `id`, `status`
(`passed|failed|skipped`), and a bounded `details` object of IDs/counts/error
codes. Include the context/revision, Attempt, diagram, result, and evidence
refs needed for replay. Do not serialize client/exception objects, raw HTTP
headers, environment mappings, full network documents, or credential values.
Maximum 64 checks and 256 KiB receipt; write mode 0600 under a directory with
mode 0700. Fail on size overflow rather than truncate evidence silently.

Exit 0 only for all required automated checks passed; exit 1 for any failure;
exit 2 for missing setup or skipped required checks. Browser/restart and
deployment-identity evidence are separate acceptance records, not falsely
passed fields in this HTTP driver.

```make
validate-thread-m11:
	PYTHONPATH=. uv run --project packages/capstone-agent python validation/run_m11.py
```

Add the target to Make help and `.PHONY` declarations. Add tests for secret
exclusion, receipt byte bounds, terminal failure, and nonzero missing setup.

- [x] **Step 4: Run tests and commit.**

```sh
PYTHONPATH=. uv run --project packages/capstone-agent pytest validation/test_m11_matrix.py -q
make check-types-validation
```

Commit message: `test: add remote federated Thread acceptance matrix`.

## Task 4: Validate locally and roll out the dual-worker cloud topology

**Modify:** `compose.yaml`, `deploy/railway/README.md`,
`deploy/railway/cloud-dev.variables.example`, `tools/tests/test_deploy_entrypoint.py`.

**Interfaces:** The selected runtime is controlled by
`CAPSTONE_THREAD_VALIDATION` and `CAPSTONE_DEPLOYMENT_STAGE`; topology uses the
existing application/family/health URL variables. No new model-facing tool or
HTTP runtime-selection field is allowed.

- [x] **Step 1: Complete deployment-contract tests and configuration.**

Extend `test_deploy_entrypoint.py` to prove `capstone api` selects the federated
module, both workers select their own adapters, worker family is fixed even if
the input environment requests another family, and `capstone worker` fails.
Keep the default `pandapower` compatibility test. Extend the fake `uv` script
to capture `CAPSTONE_THREAD_FAMILY` for those assertions.

Pass opt-in validation variables through Compose with empty defaults:

```yaml
CAPSTONE_THREAD_VALIDATION: ${CAPSTONE_THREAD_VALIDATION:-}
CAPSTONE_DEPLOYMENT_STAGE: ${CAPSTONE_DEPLOYMENT_STAGE:-local}
```

Update the cloud-dev checklist to separate common settings from per-service
overrides. API uses `CAPSTONE_HOSTED_APPLICATION=capstone`; workers use
`pandapower` and `pypsa`, respectively. All have explicit `PORT=8080`.
API health URL setting is exactly:

```text
CAPSTONE_FAMILY_HEALTH_URLS=pandapower=http://capstone-worker.railway.internal:8080,pypsa=http://capstone-worker-pypsa.railway.internal:8080
```

Workers receive `CAPSTONE_FEDERATED_CATALOG_CONTEXT=true`. Each own wake URL
matches its service and port; the API legacy wake URL targets capstone-worker.
Document that Thread polling requires running workers during this acceptance.
Retain the user-trial single-family example and its independent release policy.

- [x] **Step 2: Exercise the local real topology and database gates.**

```sh
uv run --project packages/grid-agent pytest tools/tests/test_deploy_entrypoint.py -q
git add compose.yaml deploy/railway/README.md deploy/railway/cloud-dev.variables.example tools/tests/test_deploy_entrypoint.py
git commit -m "deploy: define cloud-development federated Thread roles"
make check-release
CAPSTONE_THREAD_VALIDATION=m11 CAPSTONE_DEPLOYMENT_STAGE=cloud-development make capstone-local-rebuild
make validate-thread-m11
```

The driver gets local API origin and token from ignored environment state.
Run the public scripted case smoke too. Execute
`test_postgres_family_filter_claims_only_matching_threads` and scope persistence
tests against a disposable database using `CAPSTONE_TEST_DATABASE_URL`. Record
that they executed. If any runtime source changes after these gates, rerun
affected checks and rebuild before remote validation.

Restore normal local mode through the rebuild entrypoint after collecting the
local validation receipt. Do not overwrite the user's ignored local env file.

- [x] **Step 3: Record the deployment manifest before mutation.**

Use project `capstone-cloud-dev`, ID
`5eecde6b-fec2-40d2-8b26-427025b02b96`, environment `production`.
Re-read service settings and latest deployment metadata. Save only role names,
IDs, source revision/digests, explicit ports, application selectors, health
paths, and runtime mode to ignored `runs/capstone-m11/deployment.json`.
Keep secret values in memory/protected state only. Record prior settings for
rollback; do not assume previously observed deployment IDs are still latest.

The source revision to deploy is the just-tested implementation commit, not
the earlier `08f7366` baseline. Build from a clean checkout of that revision;
stage only verified ignored model assets required by the existing Dockerfile.
Do not copy authentication state. Record source provenance for all three
backend builds even if their image digests differ.

- [x] **Step 4: Deploy family workers, then API and App.**

Create the private `capstone-worker-pypsa` service if absent; configure its
protected database/bucket/operator references to the cloud-dev stage only.
Deploy both workers from the manifest revision, each with its fixed family.
Enable `CAPSTONE_THREAD_VALIDATION=m11` and
`CAPSTONE_DEPLOYMENT_STAGE=cloud-development` on the workers. Keep replicas at
one and Serverless sleep disabled for the matrix. Wait at most ten minutes
for deployment health, polling at bounded intervals.

After both private `/health` probes succeed, deploy the unified API with both
health origins, the same validation-mode/stage flags, and the App with its
existing API origin. Recheck private validation readiness and catalog
availability after API startup. Inspect real runtime ports; a successful
Railway deployment alone does not prove private worker connectivity.

Use the deployment CLI's current `--help` and structured metadata for exact
service selectors; never rely on a globally linked default target. Never pass
secret values in CLI arguments or print complete variable mappings. The user
approved this cloud-dev expansion; Provider execution and user-trial promotion
remain excluded.

- [x] **Step 5: Run remote HTTP and scripted-session acceptance.**

Run `make validate-thread-m11` with protected cloud-dev origin/token values.
Run registered `pandapower-scripted-task` and `regional-demand-stress` legacy
scripted sessions, wait for `ready` before each turn, and read report/result/
evidence/network endpoints after committed answers. Use the public credential
for one smoke; verify a Provider creation request returns 403 without being
enqueued. Keep these session receipts separate from the new Thread receipt.

On rollout failure, restore prior cloud-dev API/worker settings and exact
verified deployments from the manifest; retain database/bucket and completed
history. Stop test-owned work on the new worker before scaling it down. Do not
delete any service or data as rollback shorthand.

- [x] **Step 6: Journal deployment identity and matrix outcomes.**

The configuration commit from Step 2 precedes the manifest and deployment.
Record its hash, deployed identities, and bounded acceptance receipt paths;
do not make unrecorded runtime code changes during remote checks.

## Task 5: Verify Web replay and restart retention, then close M11

**Use:** `packages/capstone-app/src/threadProjectionStore.test.ts`,
`packages/capstone-app/src/ThreadLiveEntry.test.tsx`,
`packages/capstone-app/src/ThreadFixtureApp.test.tsx`.
**Create:** `docs/reviews/2026-10-05-capstone-m11-cloud-verification.md`.
**Update:** `docs/status/JOURNAL.md`, `docs/status/CURRENT-STATE.md`,
`docs/status/RESUME-NEXT-SESSION.md`.

- [x] **Step 1: Run existing replay/focus regressions and the App build.**

```sh
npm --prefix packages/capstone-app test -- src/threadProjectionStore.test.ts src/ThreadLiveEntry.test.tsx src/ThreadFixtureApp.test.tsx
npm --prefix packages/capstone-app run build
```

Require coverage of late topology events, revision mismatch, unknown focus
elements, historical pages, and snapshot/live-event reconciliation. Fix a
missing assertion with a failing regression before changing production code.
Repeat affected local gates and cloud rollout if runtime code changes.

- [ ] **Step 2: Inspect the actual cloud App with the completed Thread.**

Use the browser skill and existing private Thread authentication mechanism;
never place a token in a URL, screenshot, static variable, or receipt. Open
the remote receipt's Thread, confirm its PyPSA result card and matching current
diagram, refresh, and reconnect. Compare restored Attempt/context/revision
identity to the HTTP receipt. Verify a legitimate focus action if the returned
projection exposes one; absence of a focus target is not a successful positive
focus test. If needed, use an existing admitted element from the real diagram
through the existing UI focus contract, without inventing an Authority fact.

Use local regression fixtures for foreign-revision and unknown-element
negative tests; identify that evidence as local. Do not inject fabricated
events into the shared cloud ledger. Verify historical-page behavior in the
real Web history where available. Missing required acceptance remains pending.

- [ ] **Step 3: Verify committed history after worker restart.**

HTTP retention passed: the snapshot, 53 events, both legacy reports/results,
evidence and six network views match before/after restart. The Web refresh
portion remains pending with Step 2 because browser connection recovery failed.

Ensure test-owned Attempts are terminal and no unrelated active work would be
interrupted before restart. Restart the two validation workers using the same
tested revisions. Read the original Thread snapshot/event history and legacy
reports/evidence again, and refresh the Web page. Require unchanged committed
identities and content. Do not submit a turn on the old in-memory Context and
claim execution recovery. A new validation run starts with a new Thread.

- [x] **Step 4: Restore normal cloud runtime and recheck health.**

Remove the opt-in validation selection from API and both workers and redeploy the
same tested source. Wait for worker health, then refresh the API assembly if
needed for startup family health. Verify readiness, both catalog families,
App health, public scripted access, and public Provider denial. Submit no
Provider-backed Thread work during this step. Record final deployment IDs and
source/digest identity after restoration, not just validation-mode IDs.

- [x] **Step 5: Self-review evidence against every spec row.**

The verification record explicitly leaves the real Web acceptance row open.
HTTP retention passed, while its Web refresh portion also remains pending.
This review does not establish M11 completion.

The verification document contains one row per acceptance check, with result,
receipt path, execution mode, stage, and limit. Link the ignored receipt paths
as operator-local evidence and record stable non-secret IDs in the document.
Keep local negative tests, remote Thread execution, browser checks, and legacy
report checks distinct. Explicitly record Provider validation as not run.
No required failed/skipped row permits an M11-complete claim.

Check public scope persistence, idempotency isolation, no Provider fallback,
real prepared-context reuse, family leasing, and topology revision checks in
the final code review. Run `make doctor`, documentation link/symlink checks,
and `git diff --check`; all must pass before committing the record.

- [x] **Step 6: Commit the verification record and update the recovery baton.**

The record preserves the pending Web checks. This checkpoint commit does not
close M11; resume Step 2 and the Web portion of Step 3 after browser recovery.

Commit message: `docs: record M11 cloud federated Thread verification`.
Journal the commit and retain an active-session checkpoint. Leave promotion
to `capstone-demo` and any Provider validation as separate future actions.

## Plan review

- Public access and historical privacy: Task 1.
- Deterministic execution, real Authorities, admission, and M10 binding: Task 2.
- Switching/reopen, current-run refs, bounded deadlines/receipts: Task 3.
- PostgreSQL family isolation, local rebuild, revision identity, dual-worker
  rollout, and rollback: Task 4.
- Web focus/replay, restart retention, normal-mode restoration, and closeout:
  Task 5.
- No new Kernel semantic tool, arbitrary execution surface, Provider call, or
  user-trial mutation is required by any task.
