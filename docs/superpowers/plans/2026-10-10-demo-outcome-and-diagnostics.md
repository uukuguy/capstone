# Demo task outcomes and diagnostics implementation plan

> Execute inline, task by task, using test-driven-development and verification-before-completion. Preserve unrelated work. Written design approved on 2026-10-10.

**Goal:** Repair derived-model work and retain truthful, actionable partial outcomes on the demo baseline and local main.

**Architecture:** Authority owns scope and lineage verification. Neutral runtime receipts preserve tool outcomes. Application-owned terminal outcomes separate task coverage from execution lifecycle; the App presents admitted work and confirmed blockers.

**Tech stack:** Python, grid-capability/1.0, Pi RPC, TypeScript/React, pytest and Vitest.

## Global constraints

- Design: `docs/superpowers/specs/2026-10-10-demo-outcome-and-diagnostics-design.md`.
- Keep the existing stdout envelope, current-run evidence gates and stage isolation.
- Do not publish rejected answer text or silently accept missing calculation results.
- Keep existing Attempt phases. Optional terminal outcome data must survive replay.
- Demo baseline `ed2524f`; local baseline `8c674ab`. Do not promote unrelated local features.
- Release-lane redesign is deferred. Remote deployment and Provider checks have separate authorization.

## Task 1: Authority-verified derived contexts

Files: `packages/pandapower-domain-pack/src/pandapower_domain/authority.py`,
`packages/grid-simulator/src/grid_simulator/{cli,models,operations}.py`,
`packages/pandapower-domain-pack/src/pandapower_domain/{execution,provisioning}.py`,
`packages/grid-agent/src/grid_agent/{hosted,thread_binding}.py`,
`packages/capstone-agent/src/capstone_agent/{kernel_capability_preparation,kernel_pi_session}.py`.

Interfaces: Authority `verify_context_descendant(reference, *, base_ref, model_id, revision_ref)`
returns a strict boolean; application binding `accepts_context_identity(context_ref, revision_ref)`
uses the exact base or that verifier. gridctl accepts an operator-owned optional
`--bound-context` and rejects context arguments outside its verified descendant chain.

- [x] Write real artifact tests with a base, child and grandchild, plus foreign root, wrong revision and missing/tampered lineage.
- [x] Run `uv run --project packages/grid-agent pytest packages/pandapower-domain-pack/tests/test_authority.py -q`; observe new-test failures.
- [x] Add bounded current-run lineage verification. Authority installs a fixed private Thread scope in the run workspace; gridctl enforces it for both native and host invocations. Remove the static context enum only when that scope exists. Keep Kernel endpoint metadata immutable.
- [x] Test admission with both event identities and result/evidence identities; keep PyPSA behavior unchanged. Verify child projections never overlay the base implicitly.
- [x] Run grid Thread binding/model-sequence tests and Capstone bound-admission tests. Commit only task paths.

Regression example:
```python
assert authority.verify_context_descendant(child, base_ref=base, model_id='ieee39', revision_ref=child_revision)
assert not authority.verify_context_descendant(child, base_ref=foreign, model_id='ieee39', revision_ref=child_revision)
```

## Task 2: Complete, safe tool diagnostics

Files: `packages/capability-agent-kernel/src/capability_agent/runtime/rpc.py`,
`packages/capstone-agent/src/capstone_agent/harness.py`, and their runtime/Harness tests.

Interfaces: semantic receipts retain `tool_call_id`, `tool_name`, strict `ok`,
optional declared capability, and stable safe error code. Unstructured tool ends
receive a neutral terminal receipt with no invented Authority references.

- [x] Write a Pi loopback regression with tool start and an SDK validation failure lacking capability details.
- [x] Run the regression and confirm the terminal receipt is currently missing.
- [x] Preserve the paired terminal receipt; normalize allowlisted error codes and stages without raw messages or secrets.
- [x] Verify normal Authority tool errors preserve their typed cause. Unknown codes use an unknown category.
- [x] Run Kernel RPC and Harness suites, including legacy event fixtures. Commit task paths.

Regression example:
```python
assert receipt['tool_call_id'] == 'call-1'
assert receipt['ok'] is False
assert not receipt.get('result_refs')
```

## Task 3: Outcome contract, persistence and App

Files: new `packages/capstone-agent/src/capstone_agent/task_outcome.py`,
`harness.py`, `kernel_pi_session.py`, `thread_service.py`,
and `packages/capstone-app/src/{threadProtocol,CapstoneAssistantThread}.ts*`.

Interfaces: bounded `capstone-task-outcome/1`, with complete/partial/unavailable
status, confirmed and blocked work, admitted references, diagnostics, and optional
Domain Pack coverage. Both storage implementations validate it before persisting.

- [x] Write tests for unknown tool outcomes, valid independent results plus a failed call, rejected answer text, and required persistence failure.
- [x] Run and observe failures for the missing contract and presentation.
- [x] Generate outcome only from host receipts and separately admitted Authority work. Retain earliest blockers and later admission failures. Missing ends remain unknown.
- [x] Retain available result projections independently; never treat a failed exhaustive study as a full ranking. Domain coverage comes from verified calculation artifacts.
- [x] Extend strict terminal validation and history restoration; add desktop/mobile tests and legacy fallback.
- [x] Run focused Python and App suites and type checks. Commit task paths.

Regression example:
```python
assert outcome['status'] == 'partial'
assert outcome['diagnostics'][0]['confirmation'] == 'unknown'
assert 'rejected model answer' not in terminal['answer']
```

## Task 4: Local and demo-baseline verification

- [x] Run `make doctor`, `make test`, `make test-e2e`, `make validate`, types and release gates required for integration.
- [x] Run `make capstone-local-rebuild` and verify actual API/worker identity and App behavior.
- [x] Build a minimal incident patch on `ed2524f`; repeat focused and integration verification there without copying ignored authentication state.
- [ ] Request any still-required remote authorization only with the tested patch and concrete release scope available.
- [ ] Validate cloud and demo exact identities, health, replay and scenario behavior; tag only after their required checks pass.
- [x] Record measured limits. Do not declare the demo fixed from local tests.
