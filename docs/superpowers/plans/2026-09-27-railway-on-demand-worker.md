# Railway On-Demand Worker Implementation Plan

> **For agentic workers:** Implement each checked step with focused tests before the repository gates.

**Goal:** Let the Railway demonstration worker sleep when no session is active and wake through a private API request.

**Architecture:** The ledger remains durable. A private wake endpoint signals the existing worker loop, while the API retries transient cold starts without changing public responses. Local Compose uses this mode; Cloud Run retains polling mode.

**Tech Stack:** Python, FastAPI, PostgreSQL, Docker Compose, Railway.

## Global Constraints

- Keep API, worker, and simulator authority boundaries unchanged.
- Never expose operator or wake credentials to the App or logs.
- Preserve the current-run result and evidence contracts.
- Stage only task-owned paths and preserve the user's existing changes.

---

### Task 1: Wake-aware worker loop

**Files:** `packages/capstone-agent/src/capstone_agent/host_worker.py`, focused host-worker tests.

- [ ] Write a failing test that asserts idle wake mode performs no repeated ledger query and wakes after a signal.
- [ ] Run that test, implement an optional event-driven idle wait, and rerun it.
- [ ] Keep active-session lease and command handling intact.

### Task 2: Private wake endpoint and API notifier

**Files:** `packages/capstone-agent/src/capstone_agent/host_worker.py`, `host_api.py`, `hosting.py`, `cli.py`, focused API tests.

- [ ] Test rejected wake credentials, creation wakeup, cold-start retry, and pending-status retry.
- [ ] Implement private HTTP wake listener and bounded API wake client with a derived token.
- [ ] Run focused tests for the API and worker.

### Task 3: Portable deployment wiring

**Files:** `compose.yaml`, `deploy/railway/README.md`, `docs/RUNBOOK.md`, focused integration checks.

- [ ] Configure local Compose and Railway to use the same private worker wake URL.
- [ ] Build the backend image and run a scripted case through local Compose.
- [ ] Run `make doctor`, `make test`, `make test-e2e`, and `make validate` once after behavior stabilizes.
- [ ] Commit only accepted source and documentation changes; deploy the same revision to Railway.
