# General Pi Executor and Capstone Delegation Implementation Plan

> For agentic workers: use subagent-driven-development for bounded tasks, with task review and final review. Keep existing user changes. Execute without intermediate permission requests.

**Goal:** Deliver one native general Pi executor for delegated Capstone tasks and direct Pi requests, while preserving professional admission.

**Architecture:** Application-owned task contracts and execution selection sit outside Domain Packs. A separate general execution environment runs pinned Pi with native configuration and tools. Both entry points use the same executor identity and share bounded user-visible conversation; business state remains behind domain contracts.

**Tech Stack:** Python, pinned Pi RPC, local Compose, PostgreSQL Thread ledger, React/TypeScript App.

**Local delivery:** Tasks 1–5 are complete. Source and task reviews approve
`7f0f174`; final backend, App, native Pi, packaging, types, boundaries, integration,
and current-source rebuild checks pass. See the
[local verification receipt](../../reviews/2026-10-09-shared-pi-local-verification.md).
Real Provider answer quality and cloud release are not accepted by these checks.

## Global constraints

- Approved design: `docs/superpowers/specs/2026-10-09-capstone-pi-delegation-design.md`.
- No keyword classification or fallback; capability selection uses the semantic node.
- No generic tools in the business Pi launcher or authority environment.
- General outputs never produce simulator evidence. Business inputs require domain admission.
- Same configured executor for delegated and direct requests; no silent capability reduction.
- No Provider credentials in model-visible files, environments, output or logs.
- Preserve existing user files, local data and immutable retry inputs; no remote deployment.
- Paid Provider validation requires separate explicit authorization. Use offline/native loopback checks first.
- All commits stage only owned paths; append the commit hash to JOURNAL immediately.

## Task 1: Bounded executor contracts and client

**Files:** create `packages/capstone-agent/src/capstone_agent/pi_delegation.py` and `packages/capstone-agent/tests/test_pi_delegation.py`.

**Interface:** immutable `PiTaskRequest.from_document(document)`, `PiTaskResult.from_document(document, request)`, `.to_document()`; `GeneralPiExecutor` protocol with `capability`, `execute(request, control, on_event)`, `cancel(task_id)`. JSON-only input/output; host binds task/result identities.

- [x] Write request/result tests for defensive copies, finite bounded JSON, source and attempt binding, duplicate IDs, unknown fields, deadline and statuses.
- [x] Run `uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_pi_delegation.py -q`; verify missing implementation fails.
- [x] Define request schema `capstone-pi-task/1`: task_id, parent_attempt_id, entrypoint (`delegated` or `direct`), instruction, messages, dependency_results, executor_identity, timeout_seconds. History uses existing `ConversationContext` validation. No model internals or credentials.
- [x] Define result schema `capstone-pi-task-result/1`: task_id, parent_attempt_id, executor_identity, status, answer, sources, artifacts, usage. Statuses completed/needs_clarification/capability_unavailable/failed/cancelled; sources and artifacts have host-issued identity and bounded metadata; no Authority refs.
- [x] Implement a host-selected HTTP client: private origin supplied at construction, no caller endpoint, bounded JSON/event records, periodic control checkpoint, cancellation in finally, no secret logging. Fake local service tests verify delegated/direct identical identity and protocol, cancellation and timeout.
- [x] Run focused tests and commit owned paths; record commit and report for task review.

## Task 2: Native general executor with isolated execution

**Files:** create `packages/capstone-agent/src/capstone_agent/general_pi_executor.py`, `packages/capstone-agent/src/capstone_agent/general_pi_server.py`, matching tests, `configs/runtime/general-pi/settings.json`, general-only Docker build/Compose service and provider relay if required. Update `deploy/rebuild_local.sh` for readiness of the new service.

**Interface:** consume Task 1 contracts; publish actual native runtime/config/tool identity. Start/cancel/read tasks through trusted internal HTTP, bounded concurrency and TTL. Pi-native read/write/edit/bash are active in a private workspace.

- [x] Test native launch flags and context projection: no professional system prompt, domain artifacts, business credentials or authority handles; native discovery loads managed project config.
- [x] Test isolation with a real built-in tool call through loopback Provider. A separate process alone fails acceptance; sandbox must exclude private business files, service credential environment and control interfaces.
- [x] Implement native RPC execution using existing PiRpcClient, task workspace and application-owned context extension. Host supplies Provider relay configuration; provider credential stays outside the model tool environment. Bind version, model, configuration and permitted tools to executor identity.
- [x] Host-issued sources/artifacts record actual observations and files; preserve native usage and tool events as diagnostics, not domain semantic events. Persist task receipts with restrictive permissions and finite retention.
- [x] Test success, failure, child termination on cancellation/deadline, no zombie tools, oversized response and concurrency admission. Commit only after isolation and focused checks pass.

## Task 3: Per-goal delegation and mixed execution

**Files:** update `intent_runtime.py`, `request_intent.py` as needed, native intent contract/config, hosted adapter; create `delegated_runtime.py` and focused tests.

**Interface:** executor capability joins the frozen intent catalog. A validated goal chooses business or general execution by operation and registered executor capability. Existing domain preparation consumes only business goals.

- [x] Reproduce external lookup incorrectly blocked by domain-only catalog with a failing worker test.
- [x] Add general executor availability/config identity to frozen resources and semantic input. Reject unknown references and unavailable executors; never convert business_execute into general shell execution.
- [x] Delegate ordinary goals using bounded shared history. Record parent/child start and terminal receipts in the Thread ledger. Reuse native executor events as diagnostics without admitting them as authority facts.
- [x] Schedule dependencies in order; independent goals survive sibling failure. Pass external observations only as explicitly typed supplemental input, never as result/evidence refs or automatic model mutation.
- [x] Aggregate completed goal answers while preserving professional admitted refs. Plain ordinary output can use delegate text directly. Test no extra rewrite call for one general task, mixed dependency order, professional admission and historical references.
- [x] Test cancellation, timeout and immutable retry configuration. Commit and review task scope.

## Task 4: Direct Pi entry point and public controls

**Files:** update Thread protocol/service/storage, worker entrypoint, App Thread settings/protocol and tests.

**Interface:** persisted `runtime_mode` capstone/pi_reference; switch accepted only with no queued/running Attempt or active Case. Attempt retains accepted mode on retries. Direct entry bypasses intent and domain preparation and uses Task 2 executor.

- [x] Add failing memory/PostgreSQL/API tests for switching, conflicting active work, replay and retry after switch.
- [x] Add additive storage fields with capstone legacy default and strict public projection; keep shared visible history and current model selection.
- [x] Route direct tasks through the same executor and config snapshot used by delegation. No Domain Pack preparation, no authority admission, no simulator references.
- [x] Add App control, label and sending projection; test switching, pending state, failure recovery and retained draft/model.
- [x] Compare delegated/direct runtime identity, tool availability, source capture, cancellation and history continuity in native loopback tests. Commit and review.

## Task 5: Integration, operational checks and acceptance receipt

**Files:** architecture, runbook, aligned README files, canonical conversation worklist, status checkpoint and review receipt.

- [x] Update normative ownership rules to distinguish a professional semantic-tool session from an isolated general executor. Preserve authority model/evidence rules.
- [x] Run focused suites, type/boundary checks, full Capstone/App gates required for changed scope, packaging and doctor.
- [x] Run `make capstone-local-rebuild`; verify API/workers share tested backend identity, general executor readiness and actual native tool task through offline test Provider.
- [x] Run final code review and fix material findings. Record implementation evidence separately from actual billed model quality.
- [x] Record remaining real Provider acceptance explicitly; do not claim ordinary/general support accepted from fixture checks alone. No remote deploy or push.
