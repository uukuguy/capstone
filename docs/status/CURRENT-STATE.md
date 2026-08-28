# Current State

## Project Snapshot

- Project: grid-static-analysis
- Theme-level focus: general domain-agent framework upgrade by seam and package extraction
- Project route: direct
- Canonical design: `docs/superpowers/specs/2026-08-27-general-domain-agent-framework-upgrade-design.md`
- Active work package: Workstream B package extraction is implemented, final-review findings are closed, and the pandapower application is locally release-ready at source revision `c146f5564220f622fedbbddd35b13696333d7534`
- Deferred work packages: Workstreams C-E remain future work for a non-grid reference domain, enterprise action governance, and multi-domain composition

## Current Architecture

- CLI: `grid-agent` writes exactly one JSON answer envelope to stdout; progress and diagnostics stay on stderr.
- Package assembly: `grid-agent` is assembled from four Python distributions (`capability-agent-kernel`, `grid-simulator`, `pandapower-domain-pack`, `grid-agent`) and two Pi npm packages (`@capability-agent/pi-tools`, `@grid-static-analysis/pi-grid-tools`).
- Domain runtime profile seam: CLI selects `pandapower_domain.build_pandapower_profile()`, then `capability_agent.prepare_domain_runtime(...)` materializes contracts, `environment.describe`, the tool catalog, guide index, current-run authority, executor, and projector registry.
- Agent Kernel: `capability-agent-kernel` owns neutral domain interfaces, runtime composition, tool catalog/guide materialization, trajectory primitives, artifacts, replay, and compatibility exports consumed by `grid-agent`.
- Pandapower Domain Pack: `pandapower-domain-pack` owns the pandapower compatibility `DomainRuntimeProfile`, manifest metadata, contract resources, system policy, guides, `GridctlClient` executor adapter, `ContentReferenceVerifier` authority adapter, and existing projector registry adapter.
- Simulator: `grid-simulator` owns `gridctl`, registered network access, deterministic pandapower 3.4.0 calculations, model revisions, result datasets, and evidence.
- Pi packages: `@capability-agent/pi-tools` owns generic descriptor-driven capability transport and model-request capture; `@grid-static-analysis/pi-grid-tools` preserves the current grid extension wrapper and `grid_*` tool compatibility.
- Agent runtime: managed Pi exposes only project grid tools, guides, and bounded context/decision tools; the LLM boundary owns provider-specific formats, while `grid-agent` commits ordinary model final text with controller-bound current-turn result/evidence lineage.
- Runtime descriptor: the fixed eight-field transport API is preserved while the production descriptor authoritatively binds catalog, guide, workspace, turn, context, trajectory, acknowledgement, and Pi runtime identity; descriptor mode does not supplement legacy runtime paths.
- Run isolation: an atomic cross-process lease prevents two active commands with the same `question_id` from sharing or overwriting current-run evidence.
- Canonical capture: Pi atomically persists provider-independent model inputs before provider I/O without waiting for observer acknowledgement.
- Native trajectory: the kernel event spine records model requests/responses, tools, decisions, claims, context revisions, results, and evidence as the authoritative chronology.
- Observation: polling skips already-seen request artifacts before parsing; projection, validation, and integrity diagnostics are deterministic consumers of recorded execution and cannot semantically replace simulator truth.
- Simulator boundary: `gridctl` exclusively owns registered network access and deterministic pandapower 3.4.0 calculations through `grid-capability` protocol 1.0.
- Compatibility contracts: CLI command names, stdout envelope, stderr diagnostics, `grid_*` tool names, tool schemas, `grid-capability/1.0`, current-run evidence admission, and `runs/` artifact layouts remain unchanged.
- Analysis context: bounded model-facing views retain active model, sourced constraints, reusable calculations, scenarios, facts, lineage, and explicit omission metadata.
- Reporting: per-question reports render answer first, restore simulation environment context, summarize the observable agent trajectory with compact simulator results, and link persisted detailed trace/current-run evidence artifacts.
- Workbench: the loopback read-only trajectory API and Business/Agent/Context/Evidence workbench consume deterministic projections without mutating runs.
- Verification: unit, package-boundary, install-mode package artifact, E2E, offline/scripted validation, and optional provider-backed continuous Analysis cover the stdout contract, capability boundary, trajectory replay, evidence, and reports.
- Release evidence: the final B-H005 run `runs/climb/20260828T092537Z-b-h005` scored 100/100 with no blockers. Its manifest binds five HMAC-attested non-focused receipts, focused `make validate`, and same-revision `make doctor`, `make test`, and `make test-e2e` prerequisite receipts to source revision `c146f5564220f622fedbbddd35b13696333d7534`.

## Open Problems (theme-level)

- No release-blocking capability gaps are known in the declared static-analysis scope.
- The pinned Pi dependency tree still contains 2 High and 2 Moderate accepted findings. `configs/runtime/pi-security-risk-exception-v1.json` documents the bounded exception and expires on 2026-09-30; the deterministic gate rejects expiry, pin drift, lock drift, or a worsened risk baseline.
- Pandapower/pandas emit upstream deprecation warnings in state-estimation and legacy network construction paths; these do not change current results.
- Provider latency remains externally variable; future changes must preserve non-blocking trajectory observation.

## Key Files

### Loaded every agent session

- `AGENTS.md` — repository contract and simulator boundary

### State / handoff

- `docs/status/RESUME-NEXT-SESSION.md` — current session handoff
- `docs/status/JOURNAL.md` — append-only durable event log
- `docs/status/CURRENT-STATE.md` — this structural snapshot
- `docs/status/DECISIONS.md` — architectural decision ledger

### Implementation entry points

- `packages/capability-agent-kernel/src/capability_agent/domain/` — neutral domain-runtime protocols and Profile value types
- `packages/capability-agent-kernel/src/capability_agent/application/composition.py` — shared Profile-driven runtime materialization
- `packages/capability-agent-kernel/src/capability_agent/tools/` — neutral tool catalog and guide materialization
- `packages/capability-agent-kernel/src/capability_agent/trajectory/` — native event, artifact, recorder, replay, and reader primitives
- `packages/pandapower-domain-pack/src/pandapower_domain/` — pandapower compatibility Profile, resources, policy, guides, authority, executor, and projectors
- `packages/grid-agent/src/grid_agent/domain/` — compatibility imports for neutral kernel interfaces
- `packages/grid-agent/src/grid_agent/domains/pandapower.py` — compatibility import for the pandapower Profile
- `packages/grid-agent/src/grid_agent/application/composition.py` — compatibility import for shared Profile-driven runtime materialization
- `packages/grid-agent/src/grid_agent/analysis/runner.py` — continuous Analysis orchestration
- `packages/grid-agent/src/grid_agent/trajectory/capture.py` — native Pi event/request observation
- `packages/grid-agent/src/grid_agent/analysis/projector.py` — simulator result projection into continuous context
- `packages/grid-agent/src/grid_agent/analysis/view.py` — bounded model-facing context view
- `packages/grid-agent/src/grid_agent/analysis/report.py` — native-event-backed report generation
- `packages/pi-capability-tools/src/model-request-capture.mjs` — generic canonical pre-provider request persistence
- `packages/pi-capability-tools/src/domain-tools.mjs` — descriptor-driven bounded Pi capability tools
- `packages/pi-grid-tools/src/model-request-capture.mjs` — grid-compatible request-capture wrapper
- `packages/pi-grid-tools/src/domain-tools.mjs` — grid-compatible Pi extension wrapper
- `packages/grid-simulator/src/grid_simulator/capabilities/` — deterministic simulator capabilities and contracts
- `configs/capabilities/pandapower-3.4.0-static-analysis.json` — executable product coverage source of truth
- `configs/runtime/pi-security-risk-exception-v1.json` — versioned, expiring Pi vulnerability risk exception and upgrade trigger
- `docs/status/climb/research-tree.md` — generated Workstream B package extraction score state
- `packages/trajectory-workbench/` — read-only trajectory investigation UI
- `validation/questions/task.md.txt` — canonical provider-backed continuous Analysis suite
- `Makefile` — supported setup, execution, and verification commands
