# Capstone Framework Guide Implementation Plan

> Historical plan: Tasks 1–3 were completed in `6024b65`, `e42ec23`, and `5a38c5b`. The active optimization record is `2026-09-05-capstone-optimization.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the framework guide, README, and agent contract explain Capstone before its first grid application.

**Architecture:** Expand the architecture guide around four ownership layers and three protocols, then make both READMEs summarize that guide before presenting grid as the verified application. AGENTS records the same dependency direction and references the guide as the authority.

**Tech Stack:** Markdown and repository documentation gates.

## Global Constraints

- Preserve every Python/npm name, CLI command, protocol, environment variable, artifact path, stdout envelope, and grid evidence contract.
- Do not present inventory, C.2, multi-domain routing, or write governance as implemented.
- Keep English and Chinese README product facts, headings, commands, and links aligned.
- Keep Kernel, Domain Pack, Application, and registered Authority ownership distinct.

---

### Task 1: Expand the framework guide

**Files:**
- Modify: `docs/architecture/capstone-framework.md`

- [x] Replace the short overview with sections for purpose/non-goals, four-layer dependency direction, runtime/tool protocol, composite output protocol, current-run evidence protocol, new-application integration sequence, verified grid application, conformance/deferred scope, and domain design rules.
- [x] Include this ownership diagram:

  ```text
  Application -> Domain Pack -> Kernel -> registered Authority
  ```

  State that dependencies only flow rightward, while result/evidence references
  return through explicit contracts.
- [x] State the exact generic result shape:

  ```json
  {"schema":"capability-agent-output/1.0","core":{},"domains":{"<binding_id>":{}}}
  ```

  Explain that a vertical compatibility adapter, not Kernel, owns the grid
  two-field projection.
- [x] Run `git diff --check` and commit with `docs: expand Capstone framework guide`.

### Task 2: Reframe the bilingual READMEs

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`

- [x] Move the framework purpose, four-layer summary, application-addition path,
  and framework guarantees ahead of the first-application section.
- [x] Retain grid static-analysis features, commands, package table, and
  compatibility details beneath a clearly labeled first-application section.
- [x] Add the framework-guide link as the primary architecture reference in both
  READMEs.
- [x] Run `rg -n 'Capstone|grid-agent|gridctl|grid-capability/1\\.0|question_id|answer_output' README.md README.zh-CN.md`, `git diff --check`, and `make doctor`; commit with `docs: lead README with Capstone framework`.

### Task 3: Align the agent contract and verify documentation

**Files:**
- Modify: `AGENTS.md`
- Verify: `CLAUDE.md`

- [x] Add the four-layer dependency direction and explicit new-domain integration
  rule to `AGENTS.md`; retain all grid-specific simulator constraints under the
  first-application contract.
- [x] Keep `docs/architecture/capstone-framework.md` in the authoritative
  references table.
- [x] Run `test -L CLAUDE.md`, `git diff --check`, and `make doctor`; commit
  with `docs: clarify Capstone agent contract`.
