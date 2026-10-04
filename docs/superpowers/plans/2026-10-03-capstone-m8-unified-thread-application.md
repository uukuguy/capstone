# Capstone M8 Unified Thread Application Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven-development for each behavior and complete an independent code review before closing M8.

**Goal:** Make one Capstone Thread application expose registered pandapower and PyPSA model families through one neutral catalog and shared durable Thread ledger, while keeping Authority execution in separate pinned worker environments.

**Architecture:** The API/control plane uses a bounded federated catalog containing only public model/profile descriptors. Pandapower and PyPSA workers continue to run in their own environments and share the Thread PostgreSQL ledger; each worker claims only Attempts for its registered implementation family. The public Thread protocol remains unchanged, and no Domain Pack or Authority object crosses into `capstone-agent`.

**Tech Stack:** Python 3.12, FastAPI, PostgreSQL, existing `ThreadApplicationAssembly`, `CompositeThreadModelCatalog`, Textual/Web public Thread protocol, Docker Compose.

## Global Constraints

- `capstone-agent` remains the application/control-plane owner; `grid-agent` and `pypsa-agent` remain transition adapters only.
- Pandapower and PyPSA Authority dependencies stay in separate Python environments.
- The public Thread API exposes bounded descriptors, events, commands, results and evidence references only.
- API and all family workers use the same PostgreSQL ledger and exact backend image revision.
- Same model/revision in one Thread reuses the active context; an explicit fresh-open control creates a new context identity.
- Every implementation change starts with a failing focused test and ends with focused verification plus an independent review.

### Task 1: Family-filtered Attempt leasing

**Files:**
- Modify: `packages/capstone-agent/src/capstone_agent/thread_service.py`
- Modify: `packages/capstone-agent/src/capstone_agent/thread_worker.py`
- Test: `packages/capstone-agent/tests/test_thread_worker.py`
- Test: `packages/capstone-agent/tests/test_thread_postgres.py`

Add an optional `implementation_family` filter to `claim_attempt` and the worker loop. `None` preserves existing behavior; a family worker claims only matching active model contexts. The filter must be applied inside the SQL row selection and the in-memory loop before leasing.

### Task 2: Federated catalog and profile metadata

**Files:**
- Create: `packages/capstone-agent/src/capstone_agent/federated_catalog.py`
- Modify: `packages/capstone-agent/src/capstone_agent/thread_catalog.py`
- Test: `packages/capstone-agent/tests/test_federated_catalog.py`

Add a neutral bounded catalog loader for model/profile descriptor documents. It validates revisions, families, defaults and duplicate IDs, and produces `CompositeThreadModelCatalog` plus a lightweight capability catalog that validates family-compatible profile selections without importing Domain Packs.

### Task 3: Authority-owned catalog export

**Files:**
- Create: `packages/grid-agent/src/grid_agent/thread_catalog_export.py`
- Create: `packages/pypsa-agent/src/pypsa_agent/thread_catalog_export.py`
- Test: `packages/grid-agent/tests/application/test_thread_catalog_export.py`
- Test: `packages/pypsa-agent/tests/test_thread_catalog_export.py`

Each adapter exports bounded JSON descriptors and profile metadata using its own Authority environment. No raw network, dataframe, tool object, or credential is exported.

### Task 4: Federated hosted composition

**Files:**
- Create: `packages/capstone-agent/src/capstone_agent/federated_hosted.py`
- Modify: `packages/capstone-agent/src/capstone_agent/cli.py`
- Modify: `packages/capstone-agent/src/capstone_agent/hosted.py`
- Test: `packages/capstone-agent/tests/test_federated_hosted.py`

Add an opt-in `CAPSTONE_HOSTED_APPLICATION=capstone` API composition that loads the two adapter manifests through fixed subprocess commands, builds the neutral catalog, and runs the existing hosted API. Add a family-worker mode that builds the existing selected adapter and passes its family filter to the shared Thread worker.

### Task 5: Local Compose dual-worker lane

**Files:**
- Modify: `deploy/entrypoint.sh`
- Modify: `compose.yaml`
- Modify: `deploy/rebuild_local.sh`
- Modify: `deploy/local.env.example`
- Test: `tools/tests/test_local_rebuild_contract.py`

Add API plus `worker-pandapower` and `worker-pypsa` services for federated mode, while preserving the single-family compatibility mode. Health, image-digest and readiness checks must cover both workers.

### Task 6: Context reuse and explicit fresh-open control

**Files:**
- Modify: `packages/capstone-agent/src/capstone_agent/thread_service.py`
- Modify: `packages/capstone-agent/src/capstone_agent/thread_commands.py`
- Modify: `packages/capstone-app/src/CapstoneAssistantThread.tsx`
- Test: `packages/capstone-agent/tests/test_thread_attempts.py`
- Test: `packages/capstone-agent/tests/test_thread_commands.py`
- Test: `packages/capstone-app/src/CapstoneAssistantThread.test.tsx`

Add a typed `reopen_model_context` command requiring an explicit model ID and a fresh context reason. Ordinary same-model selection is rejected as already active; the explicit command creates a new context ID, keeps the prior context in history, and emits `model_context_reopened`.

### Task 7: Web model-family presentation and verification

**Files:**
- Modify: `packages/capstone-app/src/ThreadModelPane.tsx`
- Modify: `packages/capstone-app/src/threadProtocol.ts`
- Modify: `packages/capstone-app/src/styles-light.css`
- Test: `packages/capstone-app/src/ThreadModelPane.test.tsx`

Display family and profile provenance in the existing compact model selector, show unavailable family workers explicitly, and keep PyPSA model IDs readable. Do not add a second protocol or direct Authority calls.

### Task 8: M8 verification and independent review

Run focused Python/Web tests, `make doctor`, `make test-e2e`, current-source local rebuild, and the dual-family provider-free matrix. Record evidence in `docs/status/JOURNAL.md`, update `CURRENT-STATE.md` and `RESUME-NEXT-SESSION.md`, then perform an independent code review before declaring M8 complete.
