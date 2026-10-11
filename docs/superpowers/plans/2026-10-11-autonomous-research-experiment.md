# Autonomous research experiment implementation plan

> For agentic workers: use subagent-driven-development for bounded implementation,
> independent task review and final whole-branch review.

**Goal:** Execute and replay the first real Authority-backed falsifiable study.

**Architecture:** Application strategy and journal compose a Domain Pack study.
The Pack uses the existing GridctlExecutor and artifact verifier. No Kernel
domain semantics or hosted application behavior changes.

**Tech Stack:** Python 3.12, current pandapower Domain Pack, grid-capability/1.0,
pytest and content-addressed Authority artifacts.

## Global constraints

User requested an isolated experimental branch. Preserve main, local-dev,
local-demo and the separate answer-closure branch. No paid Provider calls.
No new tools that encode a single fixture or precomputed answer. Study-specific
policy is an experimental consumer of existing reusable semantic actions.

## Task 1: Executable research slice

Files:
- Create application module under
  packages/capstone-agent/src/capstone_agent/research_experiment.py.
- Create Pack module under
  packages/pandapower-domain-pack/src/pandapower_domain/research_experiment.py.
- Create experimental CLI at experiments/autonomous_research/run.py.
- Create tests in the owning packages for each module.

Interfaces: strategy receives persisted public observations and proposes a next
bounded experiment or termination. Pack executes the typed static-grid study and
admits observations; Pack replay reconstructs observations from Authority artifacts.
Application journal stores proposals and observations without interpreting grid data.

- [x] Write and run failing tests for evidence tampering, false completion at
  budget exhaustion and branching based on differing observations.
- [x] Implement bounded proposal/strategy protocol, append-only events and receipt.
- [x] Represent research nodes with ids, goals, dependencies, completion criteria
  and grouped tool calls; record evidence-dependent successors and node verdicts.
- [x] Materialize a versioned Pack knowledge descriptor with sources, assumptions
  and criterion, a typed workflow with step dependencies, and an independent
  conclusion validator. These three base components are part of this branch.
- [x] Implement Pack adapter using existing registered gridctl executor and verifier.
- [x] Run focused tests and resolve failures without weakening evidence checks.
- [x] Execute the user-provided IEEE39 corpus in experiments/autonomous_research/cases.json;
  report each goal separately, preserve bus identity ambiguity and generator balance
  limits, then replay in a fresh process without a solver; save ignored receipts.
- [x] Run independent review; fix important findings; commit only owned files.

## Task 2: Experimental evidence and control alignment

- [ ] Write a concise tracked report with actual commands, results and limitations.
- [ ] Update canonical version register, notebook, worklist and recovery checkpoint.
- [ ] Regenerate the existing project overview and verify source edges, spacing
  and mobile layout in a browser.
- [ ] Keep experimental delivery on this branch, as explicitly requested.

## Verification commands

Run setup, install-pi and doctor before managed tool tests. Use Python3.12 focused
pytest in the owning packages, then the new CLI's real-run and replay commands.
Run repository boundary checks relevant to added imports and git diff --check.
Exact experiment command and receipt identity must be included in the report.

## Next evolution

R0 code bf678f2 passed actual IEEE39 execution, replay and independent review. The next authoritative plan is [Research Model evolution](2026-10-11-research-model-evolution.md). Current controlled execution does not implement the full Research Model or establish autonomous reasoning.
