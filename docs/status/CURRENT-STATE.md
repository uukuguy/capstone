# Current State

## Project snapshot

Tool composition covers independent requests and dependent cursor chains with
bounded session scheduling. Deployment and validation state belong to the session
baton and [validation](../reports/2026-11-05-batch-regression.md).

Capstone provides evidence-backed enterprise agents over registered business
systems. The repository uses managed project control. The canonical delivery
worklist is [unified execution](../superpowers/plans/2026-10-16-enterprise-unified-execution.md).
The current themes are continuing conversations, instruction-scoped resources,
bounded diagnosis, source data access and large grid views.

Shared tool execution retains host-observed actions and source references instead
of requiring copied business identifiers. Public error summaries are extracted
before truncation; explicit response intent is separate from answer text and
thinking. The owning [invocation design](../superpowers/specs/2026-10-31-deterministic-tool-invocation-design.md)
keeps business names and availability rules in the connected gateway contract.

Continuing instructions carry immutable historical file references instead of
copying every prior product into a new sandbox. A task-local host port admits
only frozen resource identities. An explicit reference read uses the existing
chunked transport and verifies ownership, version and digest before exposing
bounded text or a protected read-only input. Historical files never become
current Authority evidence merely by being referenced.

The shared workspace keeps one conversation and composer. An instruction owns
its goal and resources; a session does not impose a permanent business goal.
New default native conversations send frozen context and admitted capabilities
directly to execution, without a separate recognition model call. The execution
model answers or selects authorized skills and tools. Existing frozen intent
decisions retain their recovery path; explicit professional entries retain their
contracts. Model selection remains frozen and reasoning follows recorded controls.
三区正在试验独立Thinking临时推送与异步批量写入。临时片段不推进
持久化游标；重连恢复、工具、产品和终态仍依赖正式事件。试验默认关闭，
单API进程范围与验证见[回执](../reports/2026-11-05-direct-thinking-preview.md)。
显示缓冲与数据库缓冲分开；执行调用边界和Thinking使用同一host任务ID，
使前端能够准确归属临时片段。修正记录见[显示节奏](../reports/2026-11-05-smooth-thinking.md)。
Explicit targets win, related follow-ups can inherit, and unrelated requests
remain independent. Research node quality gaps support user judgement across
turns; scientific calculations retain objective Domain Pack/Authority checks.

## Architecture

Ownership follows Application → Domain Pack → Kernel → registered Authority.
Applications select bindings and public projections. Domain Packs own semantic
execution and policy. The Kernel owns neutral turns, context and trajectory.
Authorities own models, revisions, numerical results and evidence.

Connected gateway publications build task-admitted capability snapshots. The
existing discovery index searches names, descriptions and published metadata; exact
contracts stay provider-owned and are read on demand. The execution model uses
these capabilities to decompose complex questions into professional actions, with
bounded exploratory queries for gaps. This adds no fixed business inventory,
mandatory first action or separate planning model. Published summary fingerprints
and contract revisions remain distinct.

Native Pi runs general tasks in isolated workspaces. Its source observations do
not become simulator evidence. Published gateway tools use protected backend
configuration and published contracts. Gateway entry points are adapter-owned;
business calls use current discovery and returned actions. Browsers receive bounded
projections and never receive gateway or Provider credentials.

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
Native Thread workers use bounded process-local attempt slots over the existing
PostgreSQL leases. Waiting unleased tasks cancel immediately; running cancellation
retains cleanup and fencing. Capacity is backend configuration, not model input.

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
- `stream_progress.py`: bounded progress coalescing shared by understanding and native execution; durable event failures remain fatal.
- `thread_worker_capacity.py`: bounded slot dispatch; `thread_service.py`: durable claims, waiting cancellation and ownership fences.
- `data_gateway_views.py`: connection-scoped bindings from admitted returned actions;
  typed presentation does not branch on gateway business tool names.
- `grid_source_topology.py`, `grid_source_http.py`: typed protected source projections.
- `packages/capstone-app/src/ThreadWorkAdapter.tsx`, `threadProjectionStore.ts`, `threadViewRouting.ts`: conversation state and instruction views.
- `GridSourceWorkspace.tsx`, `networkScene.worker.ts`, `networkSceneIndex.ts`: source navigation and bounded large diagrams.
- `packages/pandapower-domain-pack/`, `packages/pypsa-*-domain-pack/`, `packages/grid-simulator/`, `packages/pypsa-model-authority/`: professional semantics and registered Authorities.
- [Evolution notebook](../superpowers/specs/2026-10-07-capstone-core-evolution-discussion.md): secondary research, separate from delivery.
## Tool composition boundary

The native composition tool accepts structured independent calls or an isolated
processing program. Host preflight, grants and observation refs remain authoritative.
Programs use tools.map for bounded independent cursor chains; each mapper awaits
its actual dependencies. Calls, reuse and skipped outcomes expose host-owned tool
identity. Context helpers share global and tools namespace implementations; datasets
remain source-referenced arrays. tools.help publishes helper contracts.

The scheduler is shared within one composition session, not across processes.
Published read-only operations may overlap; unknown/mutating operations execute
exclusively. Models still choose semantic dependencies; the host does not rewrite
arbitrary JavaScript or infer business scope from names.
See [design](../superpowers/specs/2026-11-05-structured-tool-batches-design.md)
and the session baton for deployment, verification and pending gateway assistance.
