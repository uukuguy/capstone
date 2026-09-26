# Capstone Agent Multimode Host Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver one evidence-backed Capstone session lifecycle through headless CLI, interactive CLI, and local HTTP/SSE for registered pandapower and PyPSA applications.

**Architecture:** Refactor the tested Kernel runner to accept instructions lazily while preserving its fixed-list API. Extract `grid-agent` generic composition and Pi location code into a neutral host package; app-specific persistent workers use a bounded JSON-lines protocol and separate environments. CLI and HTTP adapters share the same host session interface.

**Tech Stack:** Python 3.12, Kernel application API, existing Pi RPC and domain adapters, FastAPI/Starlette, Uvicorn, pytest, uv.

## Global Constraints

- Keep `grid-agent` compatibility stdout exactly one `question_id` / `answer_output` JSON object.
- Progress and diagnostics go to stderr; no arbitrary command, path, or authority selection from callers or models.
- Pandapower and PyPSA remain in separate Python environments; the neutral host imports neither Domain Pack.
- Current-run result and evidence references must pass selected authority admission before answer publication.
- Provider credentials remain in environment or ignored operator state; do not invoke billable Provider checks without authorization.
- Preserve staged `.codex/config.toml`, user runtime assets, and unrelated changes; align English and Chinese README changes.
- Use `apply_patch` for text edits and test a focused failing case before each behavior change.

---

### Task 1: Incremental Kernel turn source

**Files:** Modify `packages/capability-agent-kernel/src/capability_agent/application/runner.py`, `context_reducer.py`; test `packages/capability-agent-kernel/tests/application/test_runner.py` and `test_context_store.py`.

**Interfaces:** `AgentApplication.run_stream(request: ApplicationRequest, instructions: Iterable[str]) -> ApplicationOutcome`; existing `run(request)` delegates to the same private turn loop. `ApplicationRequest.questions` is empty at stream creation and records accepted instructions by completion. Existing `semantic_event_observer` emits each committed turn.

- [ ] Write a fake-provider test with a blocking generator: after its first yield, assert answer one is committed, the provider started once, and the second instruction can then be supplied; after source close, assert two answers and one provider stop.
- [ ] Run `uv run --project packages/capability-agent-kernel pytest packages/capability-agent-kernel/tests/application/test_runner.py -q` and observe the missing `run_stream` failure.
- [ ] Refactor the current `run` body into a shared private method fed by either the fixed tuple or a validated lazy iterable. Keep one preflight/start/cleanup sequence and `FinalizedTurn` submission; build the current request with `dataclasses.replace(request, questions=tuple(accepted))` after each accepted instruction.
- [ ] Add a Kernel context input transition so a streamed instruction is durably appended before its `turn.started` event; reject duplicate or out-of-order instruction ordinal. Test replay and terminal-state rejection.
- [ ] Run the focused tests, then the Kernel suite; commit only Task 1 files.

### Task 2: Neutral composition and process protocol

**Files:** Create `packages/capstone-agent/pyproject.toml`, `src/capstone_agent/application.py`, `src/capstone_agent/runtime.py`, `src/capstone_agent/protocol.py`, `src/capstone_agent/session.py`; modify `packages/grid-agent/src/grid_agent/application/composition.py` and the existing runtime locator forwarding modules; test under `packages/capstone-agent/tests/` and the existing `test_generic_entrypoint.py`.

**Interfaces:** `build_application(application_id, *, registry, runtime_host, ...) -> AgentApplication`; `WorkerSession.open(...)`, `submit(instruction)`, `close()`, `evidence(ref)`; line frames have schema, session ID, sequence, kind, bounded JSON payload. Registry maps exact application IDs to fixed worker commands.

- [ ] Write failing tests proving the neutral package imports no pandapower or PyPSA module, registry rejects unknown IDs, and worker protocol rejects unknown fields, oversized frames, and sequence gaps.
- [ ] Run the focused tests and confirm expected failures.
- [ ] Move the body of verified generic composition and Pi locator/lock functions into neutral modules, preserving signatures and behavior. Make `grid-agent` entry points forward to them and run existing compatibility tests.
- [ ] Implement one-worker-per-session JSON-lines transport with fixed command declarations, bounded input/output, safe crash handling, and a single in-flight turn. Use an injected fake process in tests; do not execute caller-provided commands.
- [ ] Run focused neutral and grid generic tests; commit only Task 2 files.

### Task 3: Registered application workers

**Files:** Create pandapower and PyPSA worker entry points in their owning application packages; promote the assembly from `validation/pypsa_cases.py` into a PyPSA application module; modify `tools/capstone_client.py` to delegate to the neutral headless host; update package dependencies and locks. Test with scripted providers and fake Pi.

**Interfaces:** Both worker entries implement `open`, `turn`, `close`, `evidence` using `AgentApplication.run_stream`; the PyPSA profile resolves `pypsa-business-cases` version `1.0` and binds `source` and `operations` with the existing reference grant. Scripted demos enforce their registered instruction sequence.

- [ ] Write failing tests for two real pandapower turns and each of the three PyPSA demo sequences through the worker protocol, checking run ID, committed answer refs, and current-run evidence refs.
- [ ] Write a fake-Pi test proving the PyPSA two-binding profile publishes only its semantic tools and uses the generic transport; run it and observe failure before the profile promotion.
- [ ] Reuse the proven profile, grant, authority setup, and scripted provider from `validation/pypsa_cases.py` in the trusted worker. Keep the validation script as a wrapper/regression entry.
- [ ] Wire the pandapower worker to its existing Profile and `gridctl`; preserve all `grid-agent` compatibility commands. Run focused worker, generic, and compatibility tests; commit Task 3 files.

### Task 4: Headless, interactive, and HTTP/SSE adapters

**Files:** Create `packages/capstone-agent/src/capstone_agent/cli.py`, `server.py`, `events.py`; test `packages/capstone-agent/tests/test_cli.py` and `test_server.py`; update `Makefile`, `docs/RUNBOOK.md`, `README.md`, `README.zh-CN.md`.

**Interfaces:** `capstone-agent run --request FILE`, `capstone-agent chat --application ID`, `capstone-agent serve --host 127.0.0.1 --port PORT`; `/api/v1/sessions` and its turn, close, event, result, and evidence routes follow the approved design document.

- [ ] Write a failing CLI test that supplies two interactive lines one at a time and sees answer one before line two; test headless stdout remains exactly one JSON object.
- [ ] Write failing HTTP tests for create/turn/SSE replay/close/result/evidence, concurrent-turn 409, bad reference rejection, token/host/origin rejection, and worker crash sanitization.
- [ ] Implement CLI adapters over `WorkerSession`, and FastAPI routes over a bounded in-memory session manager. Reuse existing trajectory server security patterns; store the operator token in ignored state with mode 0600.
- [ ] Document all modes and the HTTP event contract in both READMEs and the runbook; run focused tests and commit Task 4 files.

### Task 5: Integration and verification

**Files:** Update architecture/status docs and any verification scripts that enumerate packages; add only integration tests that exercise a real authority path.

**Interfaces:** The main checkout exposes all three `capstone-agent` modes; `grid-agent` remains compatible; PyPSA and pandapower worker environments stay separate.

- [ ] Run pandapower and the three PyPSA scripted demos through the new neutral headless CLI and inspect each current-run answer/evidence chain.
- [ ] Run `make doctor`, `make test`, `make test-e2e`, `make validate`, package/type checks affected by the new distribution, `git diff --check`, local doc-link checks, and `CLAUDE.md -> AGENTS.md` check.
- [ ] Test the main checkout's actual `grid-agent run --offline` envelope and a local HTTP/SSE session with fake Provider; document that live Provider is unverified without billing authorization.
- [ ] Commit only task-owned files, append one concise journal line per commit, and update the active recovery checkpoint when the new entry point is verified.
