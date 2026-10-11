# Task Understanding and Formal Answer Closure Implementation Plan

Acceptance correction, 2026-10-11: real local-dev2473e48 user samples failed.
The English clarification prefix and malformed overview request are reproduced.
Follow [deployment answer acceptance repair](2026-10-11-deployment-answer-acceptance.md)
before human handoff or Research Model R1. Prior technical checks remain valid
within their recorded scope; they did not prove real Provider business acceptance.

**Goal:** Bind each requested conclusion to its actual model, scenario and verified coverage, then write a direct formal answer.

**Architecture:** Application owns bounded semantic recognition and immutable task identity. Domain Packs resolve objects, operations, coverage and supported conclusions. Authorities remain the only source of model facts. Kernel remains domain neutral.

**Tech Stack:** Python 3.12, existing Pi RPC, Thread ledger, registered Domain Packs and pytest.

Related feedback: GitHub Issues #2 and #3, both `ai:working` since 2026-10-11. They share this approved package; initial independent review requires fixes before full local-dev acceptance or a PR. Issue #4 is a separate diagnosis, not a reason to change this package's scope.

## Constraints

- User approved the shared design on 2026-10-11. One main-based enhancement branch; no experimental Pi import.
- No keyword fallback, guessed model references or model-certified completion.
- Preserve legacy records, current-run admission, stdout contracts and fatal required persistence failures.
- No paid Provider calls or cloud deployment. Local-demo stays at its accepted source.

## Execution

### 1. Bounded task contract

- [x] Add `capstone_agent/task_understanding.py`: frozen request identity, semantic goal proposals, answer policy, strict document decoding and host-bound targets.
- [x] Test malformed decisions, foreign context, duplicate goals, unknown fields, depth/size limits and immutable round trips in `tests/test_task_understanding.py`.
- [x] Run `uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_task_understanding.py -q` before and after implementation. Eighteen tests pass on Python3.12; independent slice review approves checkpoint `45946db`.

### 2. Semantic recognition and durable replay

- [x] Add a tool-free recognition session using existing managed Pi transport; input is instruction, selected context and bounded history. Persist a distinct task decision before execution.
- [x] Freeze accepted decisions for retries; legacy retries remain explicitly uncertified. Recognition failure stops before execution with a safe retryable code.
- [x] Pass the task contract into professional execution and ordinary response policy without changing Authority permissions.
- [x] Test recognition failure, cancellation, decision replay and required ledger failures through Harness and worker tests. Checkpoint `491b23b`: independent V3 review approves; 159 focused tests including PostgreSQL pass; actual managed Pi loopback verifies one request and zero tools.

### 3. Pack-owned relevance and conclusion records

- [x] Add typed Pack-owned requirements and coverage records; resolve subject identifiers through published authority contracts.
- [x] Match verified results by context, revision, scenario, operation and requested coverage. Baseline cannot satisfy changed load or outage; subset cannot certify full ranking.
- [x] Verify the requested object and measure, not an unrelated generic summary. Preserve existing published operations outside the typed coverage adapter through explicitly uncertified compatibility, with unchanged permissions and admission.
- [x] Reuse reviewed optional-query and result-preservation guards from archived source after focused comparison.
- [x] Test real registered baseline, branch contingency, modified-load and incomplete-ranking results; expose unsupported generator contingency before unrelated execution.

### 4. Formal answer and product acceptance

- [x] Apply the user's run-process UI adjustment: running switches between one latest-action preview and full history; completed switches between collapsed and full history. Bound both window heights and scroll full history; shrink the disclosure label and use half-font-size row gaps. Source4223a6d independently reviewed; local-dev UI-only candidate22acf1b rebuilt and checked on 2026-10-11; human acceptance pending.
- [x] Compose from admitted conclusion records with language/scale policy. Trusted fallback renders these same conclusions and specific unresolved obligations.
- [x] Separate process messages from the final assistant message at the neutral transport boundary; verify ordinary, mixed and compatibility paths, not only trusted Pack conclusions. English process prefaces must not enter the public Chinese final answer.
- [x] Preserve unsupported gen/ext_grid intent and explain the registered capability boundary. Do not implement or claim new numerical outage support in this package. An unspecified scope must not certify full coverage.
- [x] Apply the second UI density adjustment: 9px descriptive rows, 8px metadata, 23px summary and 32px preview cap; keep 160px scrollable full history, running attention and settled secondary weight. Source checks pass; actual local-dev acceptance is pending.
- [x] Verify mixed goals, recovered optional errors, non-convergence, tampering, required persistence failure and legacy replay.
- [ ] Run focused tests, scope-required integration gates and canonical local-dev rebuild; inspect actual desktop/mobile entry points.
- [ ] Update canonical worklist, version register, graph and recovery files; independently review a single PR. Merge only after exact-source acceptance.

## Completion rule

Contract unit tests alone do not complete this package. Semantic recognition, Pack coverage, formal response and actual local-dev acceptance are all required.

## Missing-input repair checkpoint

The760ac0a overall8-case/10-turn receipt passes independent business review,
but a real Provider review of the previously failed proposal retains the extra
power-component question. Input-gap专项 is not accepted from the overall pass.
The Pack now defines proportional whole-load scaling, normalizes empty component
selection to explicit p/q fields, and freezes the resolved patches. Explicit
component requests and true unresolved choices remain distinct.52 Pack tests and
source review pass. Verify the captured proposal, true unresolved component choice,
and the deployed load-change Thread before any baseline or human handoff claim.

## Source acceptance checkpoint

Whole-source independent review approved; full test, E2E, validate and source/validation type gates passed. Fresh precommit checks:38 passed, including actual Authority coverage and formal-message separation. local-dev rebuild, actual App/API acceptance, exact remote CI and integration remain required. The next baseline must precede Research Model implementation; preserve the existing research experiment as a reference.
