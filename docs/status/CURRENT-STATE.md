# Current State

## Project snapshot

Capstone provides evidence-backed enterprise agents over registered business
systems. The repository uses managed project control. The canonical delivery
worklist is [unified execution](../superpowers/plans/2026-10-16-enterprise-unified-execution.md).
The current themes are continuing conversations, instruction-scoped resources,
bounded diagnosis, source data access and large grid views.

The shared workspace keeps one conversation and composer. An instruction owns
its goal and resources; a session does not impose a permanent business goal.
Explicit targets win, related follow-ups can inherit, and unrelated requests
remain independent. Research node quality gaps support user judgement across
turns; scientific calculations retain objective Domain Pack/Authority checks.

## Architecture

Ownership follows Application → Domain Pack → Kernel → registered Authority.
Applications select bindings and public projections. Domain Packs own semantic
execution and policy. The Kernel owns neutral turns, context and trajectory.
Authorities own models, revisions, numerical results and evidence.

Native Pi runs general tasks in isolated workspaces. Its source observations do
not become simulator evidence. Published gateway tools use protected backend
configuration and fixed contracts. Browsers receive bounded projections and
never receive gateway or Provider credentials.

Grid source views retain raw equipment identity, source relationships, selection
rules, snapshots and gaps. Display partitions are not electrical equivalents.
Calculation views require exact registered model context and admitted layers.
Worker indexing and WebGL provide bounded large-view presentation. Automatic
view routing uses verified current-instruction execution; manual navigation wins.

## Development and recovery

Dev owns active worklists and project control; main holds release snapshots.
The [version register](VERSION-CONTROL.md) owns branch and deployment identities.
Local-dev serves development; local-demo follows its accepted demo source.
Cloud stages and their data remain separate. A merge is not deployment acceptance.
Use affected development gates; release checks belong to explicit releases.

The [journal](JOURNAL.md) records events. The [live baton](RESUME-NEXT-SESSION.md)
owns active tasks, failures, exact runtime identities and next actions. Historical
transcripts previously mixed into this snapshot are preserved byte-for-byte in
[the archived source](_archive/2026-10-26-pre-grid-source-state.txt).

## Open problems

- Source topology readiness does not prove a valid operating model. State,
  parameters, scenario, mapping, boundaries and electrical reduction need
  explicit Authority checks; missing construction capabilities remain visible.
- Real task delivery, interruption, continuation and refresh recovery require
  live verification beyond unit checks and synthetic rendering benchmarks.
- GB-scale resource storage, processing and model-context budgets remain separate
  obligations under the accepted enterprise design.
- Secondary core evolution research does not set the active delivery order.

## Key files

- [Repository contract](../../AGENTS.md), [architecture](../architecture/capstone-framework.md), [lifecycle](../architecture/capstone-development-lifecycle.md).
- [Enterprise design](../superpowers/specs/2026-10-15-enterprise-design-final.md), [UI contract](../superpowers/specs/2026-10-15-enterprise-task-ui-design.md), [grid view contract](../superpowers/specs/2026-10-25-grid-topology-view-requirements.md).
- `packages/capstone-agent/src/capstone_agent/thread_service.py` and `thread_work.py`: persistent instruction/Work state.
- `general_pi_server.py`, `delegated_runtime.py`: isolated execution, source admission and public events.
- `data_gateway_views.py`: connection-scoped bindings from admitted returned actions;
  typed presentation does not branch on gateway business tool names.
- `grid_source_topology.py`, `grid_source_http.py`: typed protected source projections.
- `packages/capstone-app/src/ThreadWorkAdapter.tsx`, `threadProjectionStore.ts`, `threadViewRouting.ts`: conversation state and instruction views.
- `GridSourceWorkspace.tsx`, `networkScene.worker.ts`, `networkSceneIndex.ts`: source navigation and bounded large diagrams.
- `packages/pandapower-domain-pack/`, `packages/pypsa-*-domain-pack/`, `packages/grid-simulator/`, `packages/pypsa-model-authority/`: professional semantics and registered Authorities.
- [Evolution notebook](../superpowers/specs/2026-10-07-capstone-core-evolution-discussion.md): secondary research, separate from delivery.
