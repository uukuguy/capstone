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
- `make validate-thread-m5` runs the provider-free runner and writes the ignored JSON report path announced on stderr; it records a typed `skipped` check when `CAPSTONE_M5_API_ORIGIN` or `CAPSTONE_M5_OPERATOR_TOKEN` is absent and exits nonzero unless `CAPSTONE_M5_ALLOW_SKIP=1` is explicitly set for report-only work.

- [x] Write failing parser/serialization tests for result status, schema, bounded detail values, and secret redaction.
- [x] Implement the small typed envelope and redaction/bounds.
- [x] Add `make validate-thread-m5`; absent credentials produce a typed `skipped` report and a nonzero setup failure by default.
- [x] Run focused tests, pyright, and `git diff --check`.

### Task 2: Build real HTTP Thread acceptance helpers

**Files:**
- Create: `packages/capstone-agent/src/capstone_agent/thread_http.py`
- Modify: `validation/thread/http_runner.py`
- Test: `validation/test_m5_http_runner.py`
- Modify: `packages/capstone-agent/tests/test_thread_http_api.py` only if a missing API contract is exposed

**Interfaces:**
- Production `HttpThreadSession` uses `httpx.Client` with `Authorization: Bearer <token>` supplied by the caller from protected runtime state and exposes `create(model_id)`, `snapshot()`, `events(after)`, and `command(kind, payload)`; validation adds the catalog projection without making the runtime package depend on validation code.
- Every response is parsed through the existing Python Thread protocol constructors; raw JSON is never returned to checks.
- `wait_for_terminal(session, timeout_seconds)` polls typed snapshot/events and fails on timeout, missing terminal event, or non-contiguous cursor.

- [x] Write fake-transport tests for auth headers, catalog/snapshot parsing, command identity/idempotency, and resync responses.
- [x] Implement the production helper on top of the existing typed Thread protocol and layer the validation catalog extension over it.
- [x] Run focused tests and pyright.

### Task 3: Add pandapower and PyPSA matrix checks

**Files:**
- Create: `validation/thread/m5_matrix.py`
- Create: `validation/test_m5_matrix.py`
- Modify: `validation/thread/http_runner.py` if typed polling needs a bounded terminal predicate

**Interfaces:**
- `run_application_matrix(application_id: str, session: HttpThreadSession) -> tuple[M5CheckResult, ...]` runs only registered instructions and records bounded event/result/evidence references.
- Pandapower checks use instructions from `validation/application/pandapower-scripted-task.json` and require model catalog, automatic route, professional admission, tool source, duration, current-run result/evidence lineage, and replay equality.
- PyPSA checks use one case from `validation/pypsa-cases/cases.json`, require PyPSA family/Profile metadata, authority-backed terminal admission, and no pandapower-only labels.
- Ordinary informational check requires an answer and zero result/evidence references.
- The matrix marks an unavailable separately hosted application as `skipped` with a bounded reason; it never treats a fixture or guessed result as a pass.

- [x] Write matrix tests that reject missing route, tool source, result/evidence lineage, or admission; evidence-only topology and result-only derived queries remain valid when the Authority declares that shape.
- [x] Implement typed matrix checks using registered instruction/case files.
- [x] Run focused matrix tests and pyright.
- [x] Run the matrix against the validation-owned provider-free live HTTP host for both registered Authority families; each host reuses the production Thread worker, Harness admission, Domain Pack executor, and Authority boundary.

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

- [x] Add the TUI regression proving staged model changes do not freeze the current conversation.
- [x] Run App tests (135), build, Capstone Thread/TUI focused tests, and focused matrix tests.
- [x] Add provider-free lifecycle/recovery checks covering selection activation, failed Attempt retry lineage, and cursor-gap resync; Web/TUI continue to consume the same typed event page.

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

- [x] Run focused unit/App gates, `make doctor`, `git diff --check`, and `make capstone-local-rebuild` from current source (image `sha256:2b8d1ade8210b921b630fd62565a34c78e81aab94117868ae473e889e276d9a9`).
- [x] Run `make validate-thread-m5` without credentials; it produced an explicit ignored `skipped` report without echoing secrets.
- [x] Run both Authority families through provider-free live Thread APIs; App and TUI focused suites consume the same Thread projections (interactive browser/TUI capture remains an operator-stage check).
- [x] Dispatch independent code review; fix all Important/Critical findings.
- [x] Write the final verification report and recovery baton. Cloud/local Docker rebuild and the protected-path baseline remain explicit environment blockers outside the provider-free matrix.

## Self-review

- The plan validates each approved matrix row and preserves the separate pandapower/PyPSA environment boundary.
- The plan does not claim a composite cross-family process where the repository cannot safely co-install the simulators.
- All checks consume typed Thread projections and registered instruction/model sources; no test invents authority facts.
