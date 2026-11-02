# Three-line development coordination

Status: application branches created for preparation; shared foundation is not yet
ready for dependent application implementation. dev is the active implementation line.

## Sequence and visible delivery

Three branches do not mean three simultaneous implementation streams. A1/B1 may
inventory assets, prepare external acceptance inputs and review frontend interaction.
Do not build temporary application runtimes or duplicate missing foundation services.
Enable dependent slices when their specific shared capabilities become usable, not
when the entire foundation is finished.

The first shared milestone is a runnable frontend-to-backend vertical slice:
start a task from the existing application, observe progress, receive an actual
saved result and inspect its source, then refresh/reconnect without losing state.
Use available registered resources and ordinary output; this milestone does not
require the full report workspace or a new scientific solver. Preserve the current
conversation entry and verify its affected behavior in the same iteration.

Each functional milestone supplies a reproducible human-observation entry:
URL, application/Profile selection, tested source identity, sample input and
resource prerequisites, visible expected behavior, known gaps and feedback record.
Use the existing local-dev App/API and canonical rebuild after runtime changes.
Do not start competing application deployments on its ports. A future parallel
preview must explicitly isolate ports, data and source identity before use.
Screenshots and static prototypes help review appearance but do not replace the
running application. Human feedback is recorded separately from automated checks;
missing optional feedback does not halt unrelated work. Required release acceptance
still follows the development lifecycle.

## Branches and ownership

Both application branches start at accepted dev `6c0b0ae74b523763b8d47bb1cd2f686afdeb12f0`.
Its design PR #34 passed Linux/macOS CI38875364352. This is a branch baseline,
not a new runtime acceptance or deployment. Initial control updates are shared
before implementation; they do not count as application functionality.

| Line | Owner scope | First stage |
| --- | --- | --- |
| dev | Shared agent foundation, protocol, storage/recovery, shared frontend state/components, integration; also serves conversation maintenance | Unified execution Tasks 1–4 and shared parts of Task 5; first deliver Task 1 baseline and bridge checks |
| feat/business-analysis | Enterprise research (`enterprise-research`) application composition and views; external-resource acceptance | A1 baseline and input contracts; A2 resource-to-chart/report vertical slice; A3 revision/recovery acceptance |
| feat/model-decision | Grid analysis/decision (`grid-analysis`) application composition and views; professional integration acceptance | B1 existing professional baseline; B2 shared-loop and existing topology/result slice; B3 candidate/revision/recovery acceptance |

The [unified implementation plan](2026-10-16-enterprise-unified-execution.md)
owns shared APIs and task dependencies. Do not duplicate its Task 1–6 checklists
as independent implementations. The two application lines use those deliveries.
Demo1/Demo2 are external evaluation examples, not production tool names or workflows.

## First-stage deliverables

### A1 — Baseline and input contract

- Inspect existing `general_pi_executor.py`, `artifacts.py`, Thread entry and
  the resource/artifact contracts in the unified plan. Record what runs now and
  what needs shared Tasks 2–4; do not call the current delegated executor unified.
- Define replaceable external resource fixtures and outcome checks for analysis,
  chart data, report sources and missing inputs. Business definitions remain in
  supplied resources. Do not add Capstone indicator APIs or fixed tool sequences.
- Deliver `docs/reviews/business-analysis-baseline.md` with frontend/backend/input
  readiness separately. This baseline can proceed before shared-loop completion.

### A2/A3 — Analysis/report slice and recovery

- After the relevant shared contracts land in dev, compose the application and
  artifact views through the common registry. Shared `TaskArtifacts.tsx`,
  `threadProtocol.ts` and projection-store changes go through dev first.
- Deliver a usable resource → analysis → professional chart/report → source-view
  slice. Check real rendered/exported chart readability and numeric data matching;
  a static prototype is not end-to-end acceptance.
- Verify revised inputs invalidate dependent results, saved versions remain
  accessible, and interruption/reconnect preserves progress. Independent work
  continues when an optional source or export fails.

### B1 — Existing professional baseline

- Inspect registered professional execution and existing
  `packages/capstone-app/src/NetworkView.tsx`, `ResultExplorer.tsx` and
  `ResearchEvidence.tsx`; use current registered cases and admitted results.
- Deliver `docs/reviews/model-decision-baseline.md` covering real execution,
  topology/result identity, source revisions and recovery. Preserve existing assets.
- Separate a missing external solver/model capability from a framework defect.
  Do not implement the example's optimizer or claim new scientific capability.

### B2/B3 — Shared-loop slice and decision views

- Consume accepted shared TaskContext and execution interfaces from dev; retain
  Domain Pack semantics and Authority facts. Do not create a second planner.
- Link scenario, candidate, result and validation views to admitted identities;
  reuse the existing electrical topology. Shared component changes return to dev.
- Verify revisions invalidate affected candidates, partial validation is presented
  accurately, and a resumed task retains evidence. Use only capabilities provided
  by the selected application bindings; unavailable actions do not block unrelated work.

## Integration and acceptance control

Each slice records owner, affected files, dependencies, frontend/backend scope,
external input readiness, checks, PR and release status. Before code work, expand
the next slice into exact files and focused checks against the current checkout.
Do not add speculative modules just to reserve ownership.

- Shared fixes use short branches targeting dev, then both application branches
  synchronize dev through normal merges. Never copy shared fixes independently.
- Application slices target dev as reviewed PRs. Unfinished application features
  remain controlled by application configuration, not forced into conversation UX.
- Cross-line dependencies flow through dev; application branches do not merge
  each other. Concurrent edits to shared files require one designated dev slice.
- Check affected behavior at both conversation and autonomous entry points for
  shared changes. Check the owning application slice end to end. Run broader gates
  when integration scope requires them, not as a universal blocker for every edit.
- After A/B slices, perform one mixed task acceptance using shared research,
  authorization, recovery and artifacts. Do not introduce a third execution loop.
- Provider calls and deployment follow existing authorization and lifecycle rules.
  Local verification, main acceptance and user updates remain separate.
- Close each application branch at its accepted stage boundary, retaining data and
  recovery references. A continuing application direction can start a new stage branch.

The repository root stays on dev. Branch creation does not require new worktrees
or running services. When implementation needs an isolated worktree, initialize
its managed runtimes with setup/install-pi/doctor before testing.

2026-10-17 naming: `enterprise-research` (企业研究与分析) and `grid-analysis` (电网分析与决策). Existing preparation branch names remain stable. The research Profile defaults to intranet resources; public-web retrieval requires an explicitly enabled, configured enhancement. These are accepted design targets, not registered-runtime claims.
