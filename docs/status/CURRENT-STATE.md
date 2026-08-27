# Current State

## Project Snapshot

- Project: grid-static-analysis
- Current branch: feature/domain-kernel-seams
- Theme-level focus: general domain-agent framework upgrade by seam extraction
- Project route: direct
- Canonical design: `docs/superpowers/specs/2026-08-27-general-domain-agent-framework-upgrade-design.md`
- Active work package: Workstream A completed; kernel/domain seams are implemented inside the existing `grid-agent` distribution
- Deferred work packages: Workstreams B-E remain future work for physical package extraction, a non-grid reference domain, enterprise action governance, and multi-domain composition

## Current Architecture

- CLI: `grid-agent` writes exactly one JSON answer envelope to stdout; progress and diagnostics stay on stderr.
- Domain runtime profile seam: CLI selects `build_pandapower_profile(repo_root)`, then `prepare_domain_runtime(...)` materializes contracts, `environment.describe`, the tool catalog, guide index, current-run authority, executor, and projector registry.
- Built-in Profile: `packages/grid-agent/src/grid_agent/domains/pandapower.py` owns the pandapower compatibility `DomainRuntimeProfile`, manifest metadata, contract root, system policy path, guide root, `GridctlClient` executor adapter, `ContentReferenceVerifier` authority adapter, and existing projector registry adapter.
- Neutral domain runtime modules: `packages/grid-agent/src/grid_agent/domain/` defines `DomainManifest`, `CapabilityContractSource`, `CapabilityExecutor`, `DomainProjectorRegistry`, `ArtifactAuthority`, and `DomainRuntimeProfile`; these modules are packaged inside `grid-agent` and do not import simulator/grid implementation modules.
- Generic composer: `packages/grid-agent/src/grid_agent/application/composition.py` depends on the injected profile and protocols, and does not select a default Profile.
- Agent runtime: managed Pi exposes only project grid tools, guides, and bounded context/decision tools; the LLM boundary owns provider-specific formats, while `grid-agent` commits ordinary model final text with controller-bound current-turn result/evidence lineage.
- Canonical capture: Pi atomically persists provider-independent model inputs before provider I/O without waiting for observer acknowledgement.
- Native trajectory: a Python-owned typed event spine records model requests/responses, tools, decisions, claims, context revisions, results, and evidence as the authoritative chronology.
- Observation: polling skips already-seen request artifacts before parsing; projection, validation, and integrity diagnostics are deterministic consumers of recorded execution and cannot semantically replace simulator truth.
- Simulator: `gridctl` exclusively owns registered network access and deterministic pandapower 3.4.0 calculations through `grid-capability` protocol 1.0.
- Compatibility contracts: CLI command names, stdout envelope, stderr diagnostics, `grid_*` tool names, tool schemas, `grid-capability/1.0`, current-run evidence admission, and `runs/` artifact layouts remain unchanged.
- Analysis context: bounded model-facing views retain active model, sourced constraints, reusable calculations, scenarios, facts, lineage, and explicit omission metadata.
- Reporting: per-question reports render answer first, restore simulation environment context, summarize the observable agent trajectory with compact simulator results, and link persisted detailed trace/current-run evidence artifacts.
- Workbench: the loopback read-only trajectory API and Business/Agent/Context/Evidence workbench consume deterministic projections without mutating runs.
- Verification: unit, E2E, offline/scripted validation, and provider-backed continuous Analysis cover the stdout contract, capability boundary, trajectory replay, evidence, and reports.

## Open Problems (theme-level)

- No release-blocking capability gaps are known in the declared static-analysis scope.
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

- `packages/grid-agent/src/grid_agent/domain/` — neutral domain-runtime protocols and Profile value types
- `packages/grid-agent/src/grid_agent/domains/pandapower.py` — built-in pandapower compatibility Profile and adapters
- `packages/grid-agent/src/grid_agent/application/composition.py` — shared Profile-driven runtime materialization
- `packages/grid-agent/src/grid_agent/analysis/runner.py` — continuous Analysis orchestration
- `packages/grid-agent/src/grid_agent/trajectory/capture.py` — native Pi event/request observation
- `packages/grid-agent/src/grid_agent/analysis/projector.py` — simulator result projection into continuous context
- `packages/grid-agent/src/grid_agent/analysis/view.py` — bounded model-facing context view
- `packages/grid-agent/src/grid_agent/analysis/report.py` — native-event-backed report generation
- `packages/pi-grid-tools/src/model-request-capture.mjs` — canonical pre-provider request persistence
- `packages/pi-grid-tools/src/domain-tools.mjs` — bounded Pi grid/orchestration tools
- `packages/grid-simulator/src/grid_simulator/capabilities/` — deterministic simulator capabilities and contracts
- `configs/capabilities/pandapower-3.4.0-static-analysis.json` — executable product coverage source of truth
- `docs/status/climb/research-tree.md` — active autonomous implementation hypothesis state
- `packages/trajectory-workbench/` — read-only trajectory investigation UI
- `validation/questions/task.md.txt` — canonical provider-backed continuous Analysis suite
- `Makefile` — supported setup, execution, and verification commands
