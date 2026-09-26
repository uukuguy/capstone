# Capstone Durable Host Implementation Plan

> **For agentic workers:** Execute each checkbox in order with focused red/green tests and review each committed unit. Inline execution is selected by the user's approval and repository collaboration constraints.

**Goal:** Make the existing Capstone HTTP session contract work across API restarts and separately hosted worker processes.

**Architecture:** PostgreSQL owns session, command, event, and admitted-evidence metadata. An API process validates and records commands; a worker process claims a session, runs the existing `WorkerSession`, and persists each validated event before HTTP readers see it. A private artifact store holds bounded report bytes and evidence projections.

**Tech Stack:** Python 3.12, FastAPI, psycopg 3, PostgreSQL, existing Capstone worker protocol, S3 and GCS storage SDKs.

## Global constraints

- Preserve Application -> Domain Pack -> Kernel -> registered Authority; only `capstone-agent` host files own new HTTP and persistence behavior.
- Keep the existing `/api/v1` result and SSE event schemas and the CLI's single JSON stdout contract.
- Never accept arbitrary worker commands, paths, artifact keys, or evidence without current-run admission.
- Preserve the local loopback server for existing CLI users; hosted mode requires explicit Host and Origin allowlists.
- The user's staged `.codex/config.toml` is outside every task.
- Do not invoke billable Provider validation.

## File map

- `packages/capstone-agent/src/capstone_agent/ledger.py`: SQL schema and transactional session, command, event, lease, and evidence operations.
- `packages/capstone-agent/src/capstone_agent/artifacts.py`: bounded report/evidence object store interface and S3/GCS adapters.
- `packages/capstone-agent/src/capstone_agent/host_worker.py`: claim loop and one persistent `WorkerSession` per claimed session.
- `packages/capstone-agent/src/capstone_agent/host_api.py`: durable FastAPI adapter over the ledger.
- `packages/capstone-agent/src/capstone_agent/catalog.py`: fixed application/case presentation metadata from registered repository sources.
- `packages/capstone-agent/src/capstone_agent/session.py`: accept server-created session ID and persist events before publishing them.
- `packages/capstone-agent/src/capstone_agent/cli.py`: `serve-hosted` and `work-hosted` commands with explicit configuration.
- `packages/capstone-agent/pyproject.toml` and `uv.lock`: locked database and storage dependencies.
- `packages/capstone-agent/tests/test_host_*.py`: focused transaction, API, worker recovery, and catalog tests.

---

### Task 1: Ordered session ledger

**Interfaces:** `Ledger(dsn).initialize()`, `create_session(application_id, mode, case_id, provider, model) -> SessionRecord`, `get_session(id) -> SessionRecord | None`, `accept_turn(id, instruction, idempotency_key) -> CommandRecord`, `accept_close(id, idempotency_key) -> CommandRecord`, `events_after(id, sequence) -> list[EventRecord]`, `append_event(id, lease_token, frame) -> None`.

- [ ] Write `test_host_ledger.py` with a PostgreSQL fixture and assertions for opaque IDs, monotonic per-session ordinals/sequences, duplicate idempotency key returning the same command, simultaneous turn rejection, and cross-connection reads.
- [ ] Run `uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_host_ledger.py -q`; expect missing `capstone_agent.ledger`.
- [ ] Implement parameterized SQL tables `sessions`, `commands`, `events`, `evidence`, `artifacts`; use database transactions and row locks for command admission. A duplicate key must return its original command only if the request body hash matches; otherwise return conflict.
- [ ] Run the same focused test; expect pass, then commit only ledger, lockfile, and test paths.

### Task 2: Worker claim and event durability

**Interfaces:** `Ledger.claim_pending(worker_id, lease_seconds) -> SessionRecord | None`, `Ledger.renew_lease(id, lease_token) -> bool`, `Ledger.next_command(id, lease_token) -> CommandRecord | None`, `Ledger.mark_interrupted_stale(now) -> int`, `run_claimed_session(ledger, registry, artifacts, session) -> None`.

- [ ] Add `test_host_worker.py` using the existing fixture worker protocol; assert one worker executes accepted turns in order, event rows are visible from a new ledger connection, a second worker cannot claim the same live session, and expired leases become `interrupted` while committed answers remain readable.
- [ ] Run only `test_host_worker.py`; expect imports/methods missing.
- [ ] Add a fixed host-side session ID to `WorkerSession`; call the ledger append callback before in-memory event publication. On persistence failure, stop the session and mark it failed rather than dropping a frame. The worker loop claims only registered applications and dispatches only the closed `turn`/`close` command kinds.
- [ ] Run `test_host_worker.py` and existing `test_session.py`; expect pass, then commit only owned paths.

### Task 3: Portable report and evidence artifacts

**Interfaces:** `ArtifactStore.put(run_id, kind, content, mime) -> ArtifactRecord`, `get(artifact_record) -> bytes`; `Ledger.admit_evidence(session_id, ref, projection)`; `Ledger.get_evidence(session_id, ref)`.

- [ ] Add tests for bounded artifact writes, server-created object keys, SHA-256 verification on read, foreign-run rejection, missing report, and evidence refs not committed in the current session.
- [ ] Run the focused tests; expect missing artifact module.
- [ ] Implement S3-compatible and GCS adapters behind one interface. After an `answer_committed` frame, the host worker asks the selected existing worker for each admitted evidence ref and stores only a bounded verified projection. After `completed`, read only the generated report path beneath the run directory, cap bytes, store it and expose artifact metadata without a local path.
- [ ] Run artifact, worker, and protocol tests; expect pass, then commit owned paths.

### Task 4: Durable HTTP and catalog

**Interfaces:** `create_host_app(ledger, registry, artifacts, operator_token, allowed_hosts, allowed_origins) -> FastAPI`; `build_catalog(registry, repo_root) -> dict`.

- [ ] Add `test_host_api.py` for create, idempotent turn, close, cross-app-instance status/result/turn/SSE cursor, report, evidence, bearer auth, Host/Origin checks, interrupted state, and readiness. Add `test_catalog.py` to assert only registered runnable cases and exact three ordered instructions.
- [ ] Run those two files; expect missing API/catalog imports.
- [ ] Implement catalog from `validation/client/*.json` and registered PyPSA case metadata; never expose arbitrary filesystem paths. Implement SSE by polling durable sequence rows with 15-second comments; return on terminal status. Add bounded JSON responses and explicit CORS headers for allowed origins.
- [ ] Run the focused tests plus existing `test_server.py`; expect pass, then commit owned paths.

### Task 5: Host entry points and local acceptance

**Interfaces:** `capstone-agent serve-hosted`, `capstone-agent work-hosted`; configuration through `DATABASE_URL`, artifact backend variables, `CAPSTONE_OPERATOR_TOKEN`, `CAPSTONE_ALLOWED_HOSTS`, `CAPSTONE_ALLOWED_ORIGINS`, and `PORT`.

- [ ] Add CLI tests for missing secrets and malformed allowlists, and a two-process PostgreSQL fixture exercising a full scripted three-turn run without invoking Provider mode.
- [ ] Run the new CLI/integration tests; expect new commands missing.
- [ ] Add entry points and a server-side readiness probe; never log token values, DSN passwords, instructions, or evidence. Document env vars and local commands in `docs/RUNBOOK.md`.
- [ ] Run focused Capstone tests, `make doctor`, `git diff --check`, and the real local pandapower/PyPSA scripted entrypoints once. Commit only task-owned paths.

## Review gate

Check the spec's lifecycle, restart, evidence, authentication, and same API contract against tests and actual routes. Confirm the main checkout is the delivery location and `.codex/config.toml` remains staged and untouched.
