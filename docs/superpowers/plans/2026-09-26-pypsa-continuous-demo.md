# PyPSA Continuous Demo Implementation Plan

> **For agentic workers:** Implement each checked step in order. The active session uses inline execution because the user asked to continue the current work.

**Goal:** Run each registered PyPSA demonstration as three ordered instructions in one Capstone application run with per-turn answers and current-run evidence.

**Architecture:** Keep the existing two PyPSA Domain Pack bindings and `ReferenceGrant`. The case catalog supplies ordered demonstration instructions and their bounded capability steps. The local scripted Provider executes those steps one turn at a time through `ApplicationRequest.questions`; it is an acceptance harness, not a substitute for later LLM validation. A unified App client can submit the same ordered list to the generic application interface when PyPSA registration and separate worker routing are added.

**Tech Stack:** Python 3.12+, PyPSA 1.3.0, capability-agent-kernel 0.1.0, pytest.

## Global Constraints

- Model revisions and numerical results must cross the registered PyPSA authority; no raw `Network` escapes.
- Keep pandapower CLI and its two-field compatibility output unchanged.
- Do not run a billable Provider validation without explicit authorization.
- Preserve the staged `.codex/config.toml` and existing status-file edits.

---

### Task 1: Three-turn scripted acceptance

**Files:** `validation/pypsa-cases/cases.json`, `validation/pypsa_cases.py`, `validation/test_pypsa_cases.py`.

**Interfaces:** `run_case(case_id: str, *, root: Path = RUN_ROOT, instructions: Sequence[str] | None = None) -> dict[str, Any]`; `presentation["turns"]` lists ordered instruction, answer, and admitted answer reference.

- [x] Write a failing test calling `run_case("regional-demand-stress", root=tmp_path, instructions=list(case["introduction"]["demo_instructions"]))`. Assert three completed questions and three answers; the second turn creates a distinct scenario revision and the third turn admits the variant dispatch result.
- [x] Run `uv run --project packages/pypsa-power-operations-domain-pack pytest validation/test_pypsa_cases.py -q`; confirmed failure because `run_case` had no `instructions` parameter.
- [x] Add `demo_workflow` capability lists to the three runnable catalog entries. Partition the existing workflow without changing its capability order. Update `CaseProvider` to retain the model reference across calls, execute only the current turn's segment, and return a bounded answer. Validate caller-supplied instructions against the registered list, then pass the tuple to `ApplicationRequest`.
- [x] Read the committed `turns/*/answer.json` artifacts through the Kernel's existing answer contract; build `presentation["turns"]` from those accepted answers and reject count/order mismatches. Preserve the existing final projection and case IDs.
- [x] Run the focused test again and confirm all three cases complete; inspect the per-turn answer and evidence references.
- [x] Commit the task-owned catalog, runner, and test paths together with the matching docs so the catalog and articles remain consistent.

### Task 2: App-facing contract and verification

**Files:** `Makefile`, `validation/pypsa-cases/introductions/*.md`, `docs/RUNBOOK.md`, `docs/superpowers/specs/2026-09-26-pypsa-model-library-and-business-cases-design.md`, `README.md`, `README.zh-CN.md`.

**Interfaces:** `make run-pypsa-case` remains the fixed-question regression path; the ordered demonstration path is a separate explicit input mode with current-run turn output.

- [x] Update all three introductions and bilingual operator docs to state exactly which scripted multi-turn path passed and which LLM path remains unverified. Keep the uniform client contract at the Kernel/Application Profile boundary and parallel Pack ownership.
- [x] Run `make doctor`, `make test`, `make test-e2e`, `make validate`, `git diff --check`, symlink check, and local Markdown link check. Inspect the saved regional, SciGRID-DE, and AC/DC presentations.
- [x] Commit only task-owned files. Append a one-line journal entry with the resulting commit hash and refresh the active recovery checkpoint.

## Review

- Confirm every result in the final answer and presentation has current-run admission.
- Confirm the script still cannot accept arbitrary free-text instructions or invoke arbitrary code.
- Confirm README English and Chinese state the same runtime boundary.
