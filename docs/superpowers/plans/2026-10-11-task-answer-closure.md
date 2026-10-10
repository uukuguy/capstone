# Task Understanding and Formal Answer Closure Implementation Plan

**Goal:** Bind each requested conclusion to its actual model, scenario and verified coverage, then write a direct formal answer.

**Architecture:** Application owns bounded semantic recognition and immutable task identity. Domain Packs resolve objects, operations, coverage and supported conclusions. Authorities remain the only source of model facts. Kernel remains domain neutral.

**Tech Stack:** Python 3.12, existing Pi RPC, Thread ledger, registered Domain Packs and pytest.

## Constraints

- User approved the shared design on 2026-10-11. One main-based enhancement branch; no experimental Pi import.
- No keyword fallback, guessed model references or model-certified completion.
- Preserve legacy records, current-run admission, stdout contracts and fatal required persistence failures.
- No paid Provider calls or cloud deployment. Local-demo stays at its accepted source.

## Execution

### 1. Bounded task contract

- [ ] Add `capstone_agent/task_understanding.py`: frozen request identity, semantic goal proposals, answer policy, strict document decoding and host-bound targets.
- [ ] Test malformed decisions, foreign context, duplicate goals, unknown fields, depth/size limits and immutable round trips in `tests/test_task_understanding.py`.
- [ ] Run `uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_task_understanding.py -q` before and after implementation.

### 2. Semantic recognition and durable replay

- [ ] Add a tool-free recognition session using existing managed Pi transport; input is instruction, selected context and bounded history. Persist a distinct task decision before execution.
- [ ] Freeze accepted decisions for retries; legacy retries remain explicitly uncertified. Recognition failure stops before execution with a safe retryable code.
- [ ] Pass the task contract into professional execution and ordinary response policy without changing Authority permissions.
- [ ] Test recognition failure, cancellation, decision replay and required ledger failures through Harness and worker tests.

### 3. Pack-owned relevance and conclusion records

- [ ] Add typed Pack-owned requirements and coverage records; resolve subject identifiers through published authority contracts.
- [ ] Match verified results by context, revision, scenario, operation and requested coverage. Baseline cannot satisfy changed load or outage; subset cannot certify full ranking.
- [ ] Reuse reviewed optional-query and result-preservation guards from archived source after focused comparison.
- [ ] Test real registered baseline, branch contingency, modified-load and incomplete-ranking results; expose unsupported generator contingency before unrelated execution.

### 4. Formal answer and product acceptance

- [ ] Compose from admitted conclusion records with language/scale policy. Trusted fallback renders these same conclusions and specific unresolved obligations.
- [ ] Verify mixed goals, recovered optional errors, non-convergence, tampering, required persistence failure and legacy replay.
- [ ] Run focused tests, scope-required integration gates and canonical local-dev rebuild; inspect actual desktop/mobile entry points.
- [ ] Update canonical worklist, version register, graph and recovery files; independently review a single PR. Merge only after exact-source acceptance.

## Completion rule

Contract unit tests alone do not complete this package. Semantic recognition, Pack coverage, formal response and actual local-dev acceptance are all required.
