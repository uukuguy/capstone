# LLM Answer Summary Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Have one LLM response provide both the complete formal answer and a faithful short process summary, without adding a second model request or changing the public CLI envelope.

**Architecture:** Add an opt-in `answer_bundle` response mode to the neutral Kernel request. The runner sends a response-format instruction only in that mode, parses a bounded `{answer, summary}` object, commits the formal answer as the existing `answer_output`, and persists the optional summary beside the turn metadata. Capstone workers select this mode; legacy grid-agent text mode remains unchanged.

**Tech Stack:** Python 3.14, dataclasses, JSON-lines worker protocol, pytest, existing Pi provider transport.

## Global Constraints

- The default CLI stdout envelope remains exactly `question_id` and `answer_output`.
- The formal answer remains the only text used by report generation and evidence admission.
- The summary may only compress the formal answer and must not add claims, values, evidence, or state.
- Invalid or legacy model responses must not block a valid formal answer; they use the deterministic fallback summary and emit a diagnostic.
- No second LLM request is introduced.

---

### Task 1: Define and test the bounded answer bundle parser

**Files:**
- Modify: `packages/capability-agent-kernel/src/capability_agent/application/answer_format.py`
- Test: `packages/capability-agent-kernel/tests/application/test_answer_format.py`

**Interfaces:**
- Produce `AnswerBundle(answer: str, summary: str | None, diagnostic_codes: tuple[str, ...])`.
- Produce `parse_answer_bundle(value: str) -> AnswerBundle`.

- [ ] **Step 1: Write failing parser tests** for valid JSON, fenced JSON, plain legacy text, missing answer, empty summary, and oversized summary.
- [ ] **Step 2: Run** `uv run --project packages/capability-agent-kernel pytest packages/capability-agent-kernel/tests/application/test_answer_format.py -q` and verify the new tests fail.
- [ ] **Step 3: Implement** strict JSON object parsing with only `answer` and `summary` accepted, trim both strings, cap summary at 140 CJK-oriented characters/220 code points, and return `summary=None` plus a diagnostic for malformed or unsafe summaries while preserving a valid answer.
- [ ] **Step 4: Run the focused test again** and require all parser tests to pass.
- [ ] **Step 5: Commit** with `git add packages/capability-agent-kernel/src/capability_agent/application/answer_format.py packages/capability-agent-kernel/tests/application/test_answer_format.py && git commit -m "feat: parse bounded formal answer summaries"`.

### Task 2: Add opt-in response mode and persist summary metadata

**Files:**
- Modify: `packages/capability-agent-kernel/src/capability_agent/application/runner.py`
- Modify: `packages/capability-agent-kernel/src/capability_agent/application/runtime_protocols.py`
- Modify: `packages/capability-agent-kernel/src/capability_agent/application/turns.py`
- Modify: `packages/capability-agent-kernel/src/capability_agent/trajectory/answers.py`
- Test: `packages/capability-agent-kernel/tests/application/test_runner.py`
- Test: `packages/capability-agent-kernel/tests/application/test_turns.py`

**Interfaces:**
- Extend `ApplicationRequest` with `response_mode: Literal["text", "answer_bundle"] = "text"`.
- Extend `FinalizedTurn` with `answer_summary: str | None = None`.
- Extend `TurnControllerSource.submit(..., answer_summary: str | None = None)`.
- Include `answer_summary` in `answer.json`, `answer.submitted`, `turn.completed`, and `application_turn_completed` only when present.

- [ ] **Step 1: Add failing runner tests** asserting `answer_bundle` wraps only the provider prompt, commits `answer` as `answer_output`, and persists/emits `summary`; add a legacy `text` test asserting the provider receives the original question unchanged.
- [ ] **Step 2: Run** `uv run --project packages/capability-agent-kernel pytest packages/capability-agent-kernel/tests/application/test_runner.py packages/capability-agent-kernel/tests/application/test_turns.py -q` and verify failure.
- [ ] **Step 3: Implement** request validation, the bounded response instruction, parser call in `_call_prompt`, optional summary threading through the controller, and backward-compatible persistence/replay handling.
- [ ] **Step 4: Run the focused tests** and require the existing runner/turn tests plus new cases to pass.
- [ ] **Step 5: Commit** with `git add packages/capability-agent-kernel/src/capability_agent/application/runner.py packages/capability-agent-kernel/src/capability_agent/application/runtime_protocols.py packages/capability-agent-kernel/src/capability_agent/application/turns.py packages/capability-agent-kernel/src/capability_agent/trajectory/answers.py packages/capability-agent-kernel/tests/application/test_runner.py packages/capability-agent-kernel/tests/application/test_turns.py && git commit -m "feat: persist answer summaries in turn records"`.

### Task 3: Select answer-bundle mode in Capstone and expose summary events

**Files:**
- Modify: `packages/capstone-agent/src/capstone_agent/worker.py`
- Modify: `packages/capstone-agent/src/capstone_agent/protocol.py`
- Modify: `packages/capstone-agent/src/capstone_agent/progress.py`
- Modify: `packages/capstone-agent/src/capstone_agent/cli.py`
- Test: `packages/capstone-agent/tests/test_worker.py`
- Test: `packages/capstone-agent/tests/test_protocol.py`
- Test: `packages/capstone-agent/tests/test_progress.py`

**Interfaces:**
- Capstone worker creates `ApplicationRequest(..., response_mode="answer_bundle")`.
- `answer_committed.answer_summary` carries the committed model summary when available.
- Existing worker frames without `answer_summary` remain valid for old sessions.

- [ ] **Step 1: Add failing worker tests** for summary propagation, fallback summary on plain provider text, and protocol acceptance of optional summary.
- [ ] **Step 2: Run** `uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_worker.py packages/capstone-agent/tests/test_protocol.py packages/capstone-agent/tests/test_progress.py -q` and verify failure.
- [ ] **Step 3: Implement** bundle-mode request construction, use the persisted summary before deterministic fallback, and keep CLI formal answer output unchanged.
- [ ] **Step 4: Run the focused tests** and require all to pass.
- [ ] **Step 5: Commit** with `git add packages/capstone-agent/src packages/capstone-agent/tests && git commit -m "feat: expose model answer summaries in Capstone runs"`.

### Task 4: Verify both domain packs with real and compatibility paths

**Files:**
- Test: `packages/capability-agent-kernel/tests/application/test_runner.py`
- Test: `packages/capstone-agent/tests/test_hosting.py`
- Test: existing PyPSA and pandapower integration tests

- [ ] **Step 1: Run focused Python gates**:
  `uv run --project packages/capability-agent-kernel pytest packages/capability-agent-kernel/tests/application/test_answer_format.py packages/capability-agent-kernel/tests/application/test_runner.py packages/capability-agent-kernel/tests/application/test_turns.py -q`
  and
  `uv run --project packages/capstone-agent pytest packages/capstone-agent/tests -q`.
- [ ] **Step 2: Run the five local case commands** and verify each report still contains the complete formal answer while process events contain a distinct summary.
- [ ] **Step 3: Run** `make doctor` and `git diff --check`.
- [ ] **Step 4: Commit any test-only adjustments** with a focused message.

