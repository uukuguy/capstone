# Capstone M5 Unified Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven development for every code change and request an independent code review before declaring M5 complete.

**Goal:** Create a repeatable provider-free validation matrix proving real Capstone Thread behavior across registered pandapower/PyPSA assemblies, Web/TUI clients, controls, evidence admission, and recovery.

**Architecture:** M5 adds a validation-only adapter around the existing typed Thread protocol. It does not create a second state machine or import Authority objects into Web/TUI. The runner talks to a selected real application process through `/api/v1`; pandapower and PyPSA remain separate environments, while the same `CapstoneThreadClient` and command/event contracts are exercised for both.

**Tech Stack:** Python 3.12/uv, pytest, FastAPI TestClient/httpx, TypeScript/Vitest, Textual, local Compose, existing `make capstone-local-rebuild`.

## Global Constraints

- `capstone-agent` owns the Thread/Harness contract; `grid-agent` and `pypsa-agent` remain migration adapters.
- No provider credentials, operator tokens, raw Authority objects, raw DataFrames, Pi/DSH native events, or mutable run data may enter versioned tests or artifacts.
- Professional answers require current-run authority admission; ordinary informational answers create no simulator evidence.
- Recovery is fail-closed: a cursor gap replaces the snapshot and catches up before commands are enabled.
- Pandapower and PyPSA pinned environments are validated as separate application processes; do not import both simulators into one runtime.
- M5 does not add multi-run Threads or new UI features.

---

### Task 1: Define the M5 validation document and typed result envelope

**Files:**
- Create: `validation/thread/__init__.py`
- Create: `validation/thread/m5_contract.py`
- Test: `validation/test_m5_contract.py`
- Modify: `Makefile`

**Interfaces:**
- `M5CheckResult(name: str, status: Literal["passed", "skipped", "failed"], details: dict[str, object])` serializes to bounded JSON.
- `M5RunSummary(application_id: str, api_origin: str, checks: tuple[M5CheckResult, ...])` serializes to `capstone-m5-validation/1` and rejects secrets or unbounded text.
- `make validate-thread-m5` runs the provider-free runner and writes the ignored JSON report path announced on stderr; it skips live checks when `CAPSTONE_M5_API_ORIGIN` or `CAPSTONE_M5_OPERATOR_TOKEN` is absent instead of inventing a pass.

- [ ] Write failing parser/serialization tests for result status, schema, bounded detail values, and secret redaction.
- [ ] Run `uv run --project packages/capstone-agent pytest validation/test_m5_contract.py -q`; confirm the missing module fails.
- [ ] Implement the small typed envelope and redaction/bounds.
- [ ] Add the Make target with explicit environment requirements and no secret echo.
- [ ] Run the focused tests and `git diff --check`.
- [ ] Commit: `test: add m5 validation result contract`.

### Task 2: Build real HTTP Thread acceptance helpers

**Files:**
- Create: `validation/thread/http_runner.py`
- Test: `validation/test_m5_http_runner.py`
- Modify: `packages/capstone-agent/tests/test_thread_http_api.py` only if a missing API contract is exposed

**Interfaces:**
- `HttpThreadSession` uses `httpx.Client` with `Authorization: Bearer <token>` supplied only from the environment and exposes `create(model_id)`, `snapshot()`, `catalog()`, `events(after)`, and `command(kind, payload)`.
- Every response is parsed through the existing Python Thread protocol constructors; raw JSON is never returned to checks.
- `wait_for_terminal(session, timeout_seconds)` polls typed snapshot/events and fails on timeout, missing terminal event, or non-contiguous cursor.

- [ ] Write failing tests using a fake transport for auth headers, catalog/snapshot parsing, command identity/idempotency, and terminal polling.
- [ ] Run focused tests and verify the expected missing-helper failures.
- [ ] Implement the helper on top of existing `ThreadCommandFactory`, `ThreadSnapshot`, `EventPage`, and `CommandReceipt`.
- [ ] Run focused tests and the existing HTTP API suite.
- [ ] Commit: `test: add typed live thread acceptance helper`.

### Task 3: Add pandapower and PyPSA matrix checks

**Files:**
- Create: `validation/thread/m5_matrix.py`
- Create: `validation/test_m5_matrix.py`
- Modify: `validation/thread/http_runner.py` if typed polling needs a bounded terminal predicate

**Interfaces:**
- `run_application_matrix(application_id: str, session: HttpThreadSession) -> tuple[M5CheckResult, ...]` runs only registered instructions and records bounded event/result/evidence references.
- Pandapower checks use instructions from `validation/application/pandapower-scripted-task.json` and require model catalog, automatic route, professional admission, tool source, duration, current-run result/evidence, and replay equality.
- PyPSA checks use one case from `validation/pypsa-cases/cases.json`, require PyPSA family/Profile metadata, authority-backed terminal admission, and no pandapower-only labels.
- Ordinary informational check requires an answer and zero result/evidence references.
- The matrix marks an unavailable separately hosted application as `skipped` with a bounded reason; it never treats a fixture or guessed result as a pass.

- [ ] Write failing matrix tests against a deterministic fake `HttpThreadSession` that omit one required event/reference at a time.
- [ ] Run focused tests and confirm failures identify the missing admission/provenance condition.
- [ ] Implement matrix checks using only typed snapshots/events and registered instruction files.
- [ ] Run focused matrix tests plus existing pandapower/PyPSA validation tests.
- [ ] Commit: `test: validate registered application thread matrix`.

### Task 4: Verify controls, lifecycle, and recovery against the same protocol

**Files:**
- Modify: `validation/thread/m5_matrix.py`
- Create: `validation/test_m5_lifecycle.py`
- Modify: `packages/capstone-app/src/threadProjectionStore.test.ts`
- Modify: `packages/capstone-agent/tests/test_thread_tui.py`

**Interfaces:**
- Lifecycle checks submit `replace_selection`, `switch_model`, `cancel_live_attempt`, and `retry_new_attempt`; they assert pending/activation events, exact original Attempt identity, and unchanged predecessor events.
- Recovery checks exercise transient SSE reconnect and `resync_required`; command submission remains frozen until a verified snapshot/event page is contiguous.
- Web projection and TUI tests consume the same event page and assert matching active model, pending state, cursor, and receipt status.

- [ ] Write failing lifecycle/parity tests for pending activation, predecessor immutability, SSE gap freeze, and TUI command envelopes.
- [ ] Run focused tests and confirm each failure is attributable to the missing assertion/helper.
- [ ] Implement the checks and only any minimal protocol fix required by an observed failure.
- [ ] Run all App tests, Capstone Thread/TUI tests, and focused matrix tests.
- [ ] Commit: `test: cover m5 lifecycle and client parity`.

### Task 5: Run the real local matrix and publish verification evidence

**Files:**
- Create: `docs/status/2026-10-01-capstone-m5-verification.md`
- Modify: `docs/status/CURRENT-STATE.md`
- Modify: `docs/status/RESUME-NEXT-SESSION.md`
- Modify: `docs/status/JOURNAL.md`
- Modify: `docs/superpowers/plans/2026-10-01-capstone-m5-unified-validation-plan.md`

**Interfaces:**
- Verification report records exact source revision, API/worker image digest, selected application origins, command lines, pass/skip/fail counts, and artifact paths without token values.
- M5 is complete only when provider-free checks, App tests/build, Capstone tests, boundary checks, `make doctor`, `git diff --check`, and `make capstone-local-rebuild` pass; missing PyPSA live deployment remains an explicit skipped capability with a successor item.

- [ ] Run unit and integration checks, then rebuild local API/worker from current source.
- [ ] Run `make validate-thread-m5` with the local private API when the ignored token/origin are available; otherwise record the typed skip and run the injected real-assembly matrix.
- [ ] Run the Web build and Textual tests against the same protocol fixtures and capture bounded evidence.
- [ ] Dispatch independent code review; fix all Important/Critical findings.
- [ ] Write the verification report and recovery baton, mark the plan complete, and commit `docs: record M5 unified validation`.

## Self-review

- The plan validates each approved matrix row and preserves the separate pandapower/PyPSA environment boundary.
- The plan does not claim a composite cross-family process where the repository cannot safely co-install the simulators.
- All checks consume typed Thread projections and registered instruction/model sources; no test invents authority facts.
