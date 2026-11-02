# Enterprise Analysis Implementation Plan

> Status: implementation sequencing proposal. No implementation or acceptance is claimed. Detailed code plans follow each bounded phase after its owning interfaces are inspected.

**Goal:** Support question-led, multi-turn enterprise analysis from an initial intent to reusable findings and revised reports.

Accepted discussion: [enterprise data research analysis](../specs/2026-10-30-enterprise-data-research-analysis.md).

**Architecture:** Extend the existing task state, event ledger and artifact references. The enterprise capability owns research semantics; the application owns navigation and interaction. The lightweight loop advances research without an additional mandatory planning or review model call.

**Tech Stack:** Existing Python backend, Pi execution runtime, React/TypeScript App and registered MCP authorities.

## Global constraints

- A research goal belongs to a concrete research task, not the whole conversation.
- Questions, execution status and artifacts have separate identities and states.
- Research result acceptance requires explicit user confirmation. AI may submit a result for acceptance but must not accept it on the user's behalf. Execution completion, file generation, preview, download, silence and continued discussion are not acceptance.
- Acceptance binds the exact submitted result revision and scope. Later changes require confirmation of the revised result; preserve the previously accepted revision and its confirmation record. Individual question findings need not each block on approval unless the user requests it.
- Missing evidence does not establish that a question's premise is false.
- Intermediate products remain available when a question is unresolved or withdrawn.
- Preserve source, version, time window, units and evidence boundaries.
- Reuse the unified conversation UI and existing ledger. No second scheduler.
- Local exploration must not silently alter the main research scope.
- Do not require DR, additional model review or whole-report regeneration for ordinary progress.

## Sequence and acceptance

### 1. Question state and the first visible vertical slice

- [ ] Inspect current research state mutation, persistence and projection before selecting extension points. Read the architecture and enterprise baseline.
- [ ] Add stable question references, parent/related-question relations, scope, revision, short finding, evidence references and artifact references to the owning research contract.
- [ ] Keep execution states separate from outcomes: answered, partially answered, evidence insufficient and premise invalid. Premise invalid requires explicit supporting evidence; pending and withdrawn are not analytical conclusions.
- [ ] Extend existing turn events and restoration so updates are idempotent and old revisions cannot overwrite current conclusions.
- [ ] Record submission and user acceptance separately from execution and analytical outcomes. Provide an explicit confirmation action and support unambiguous user acceptance in conversation; bind both to the presented result revision. Keep unaccepted artifacts available for use and revision.
- [ ] Add a compact question navigation view through `packages/capstone-app/src/ThreadWorkAdapter.tsx`; reuse `ThreadProductsWorkspace.tsx` for associated products. Keep execution traces separate.
- [ ] Verify: create a research question, attach a finding and CSV, refresh, continue the question, then inspect the earlier revision. Verify insufficient evidence never renders as a disproved premise.
- [ ] Verify that AI completion cannot accept research results; preview and download cannot accept them; explicit user confirmation accepts only the submitted revision; revised results require a new confirmation, and refresh preserves the acceptance record.

Deliverable: a real conversation with a persistent question map and accessible intermediate products.

### 2. AI guidance and purposeful stopping points

- [ ] Extend the selected enterprise research policy with question-led iteration: identify the main question, inspect available evidence, deliver a useful bounded finding, and recommend the next action.
- [ ] Generate guidance during existing model turns, not a separate mandatory host/reviewer chain. Show only the current purpose, key finding or limitation and recommended next step.
- [ ] Ask only questions that change direction or scope. Continue independent useful work while optional user input is pending.
- [ ] Distinguish a completed stage from completed research. Do not stop merely because the request pool is empty.
- [ ] When a proposed research result is ready, present a concise conclusion and limitations with actions to accept or continue revision. Pending acceptance must not trigger model polling, automatic retries or additional unsolicited work.
- [ ] Verify an initially vague summer-analysis request produces a useful first stage and a navigable research direction without waiting for a complete deck.

Deliverable: AI actively maintains research direction and exposes meaningful decision points.

### 3. User steering and local exploration

- [ ] Let the user select a question to continue, add a question, revise scope or launch a local exploration with explicit inherited resource versions.
- [ ] Record whether a new instruction supplements, replaces or branches from current work; resolve ambiguous high-impact changes with the user.
- [ ] Label active work by its input revision. Preserve outdated results as historical; do not silently apply them to revised conclusions.
- [ ] Let useful local findings be incorporated into the main research by explicit reference, without rerunning their source queries.
- [ ] Verify a province-specific side exploration, return to the original question, and change the comparison window while work is running.

Deliverable: user autonomy without loss of the main research direction.

### 4. Reusable findings and targeted report revision

- [ ] Associate report sections with question findings and exact artifact versions.
- [ ] Distinguish draft products, selected report material and exported reports without discarding process files.
- [ ] On evidence or scope change, mark affected findings and sections for update; retain unaffected sections and source results.
- [ ] Verify a revised comparison window updates the affected chart and report section, while unrelated sections remain unchanged.

Deliverable: reports are maintainable outputs of research rather than repeatedly regenerated end products.

### 5. Real multi-turn acceptance and measured optimization

- [ ] Use one new conversation in the existing Vivaldi Capstone tab: vague intent → initial findings → local exploration → user correction → synthesis → report → local revision → refresh and restore.
- [ ] Finish acceptance with explicit user confirmation of the revised report. Verify that rejecting or requesting changes preserves the products and returns the task to revision rather than recording acceptance.
- [ ] Measure time to first useful finding, first usable artifact, per-turn latency, model/tool counts, duplicate calls and report revision cost. Compare like-for-like tasks and instrumentation.
- [ ] Reuse discovered contracts and evidence within their scope/version constraints; use parallel requests only for genuinely independent questions.
- [ ] Check another enterprise analysis subject to reject summer-specific hardcoding.
- [ ] Run focused regression checks, canonical local rebuild and real App acceptance before claiming runtime completion. Record actual source/image identities and integration state.

## First delivery boundary

Complete phases 1 and 2 together as the first user-visible milestone. It must support one real question-led research session across at least three user turns, a restored navigation graph and usable intermediate products. Full report revision and concurrent user steering remain later explicit milestones.

## Existing mechanisms to retain

- `ThreadWorkAdapter.tsx`: existing conversation/work integration.
- `ThreadProductsWorkspace.tsx`: product selection and preview.
- `ResearchProgressSummary.tsx`: inspect reuse for concise progress; do not conflate it with a question graph.
- Existing actual LLM request pool: opt-in experimental scheduling, disabled by default; not a prerequisite for this mode or research semantics.
- Existing professional authorities: source and numerical truth; research conclusions cannot fabricate authority evidence.

## Known baseline

The latest summer run took about 512 seconds, with 81 main model requests, no independent analysis calls and 23 tool errors. It produced a 14-slide PPTX and CSV. This shows functioning delivery but does not demonstrate a performance improvement. The new acceptance target measures useful staged delivery and multi-turn correction as well as total execution cost.
