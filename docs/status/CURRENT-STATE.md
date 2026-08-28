# Current State

## Project Snapshot

- Project: grid-static-analysis
- Theme-level focus: general domain-agent framework upgrade by seam and package extraction
- Project route: direct
- Canonical design: `docs/superpowers/specs/2026-08-27-general-domain-agent-framework-upgrade-design.md`
- Active work package: Workstream B package extraction is integrated on `main` at `448c407`; all three final-review rounds are closed, and the pandapower application is locally release-ready at source revision `e41783558afb57eb04ad04562c7d9b0fe6e6bf0b`
- Deferred work packages: Workstreams C-E remain future work for a non-grid reference domain, enterprise action governance, and multi-domain composition

## Current Architecture

- CLI: `grid-agent` writes exactly one JSON answer envelope to stdout, including validation failures for unsafe externally supplied question IDs; progress, validation detail, and diagnostics stay on stderr without a raw traceback.
- Package assembly: `grid-agent` is assembled from four Python distributions (`capability-agent-kernel`, `grid-simulator`, `pandapower-domain-pack`, `grid-agent`) and two Pi npm packages (`@capability-agent/pi-tools`, `@grid-static-analysis/pi-grid-tools`).
- Domain runtime profile seam: CLI selects `pandapower_domain.build_pandapower_profile()`, then `capability_agent.prepare_domain_runtime(...)` materializes contracts, `environment.describe`, the tool catalog, guide index, current-run authority, executor, and projector registry.
- Agent Kernel: `capability-agent-kernel` owns neutral domain interfaces, runtime composition, tool catalog/guide materialization, trajectory primitives, artifacts, replay, and compatibility exports consumed by `grid-agent`.
- Pandapower Domain Pack: `pandapower-domain-pack` owns the pandapower compatibility `DomainRuntimeProfile`, manifest metadata, contract resources, system policy, guides, `GridctlClient` executor adapter, `ContentReferenceVerifier` authority adapter, and existing projector registry adapter.
- Simulator: `grid-simulator` owns `gridctl`, registered network access, deterministic pandapower 3.4.0 calculations, model revisions, result datasets, and evidence.
- Pi packages: `@capability-agent/pi-tools` owns generic descriptor-driven capability transport and model-request capture; `@grid-static-analysis/pi-grid-tools` preserves the current grid extension wrapper and `grid_*` tool compatibility. Source setup uses the committed frozen local-file locks and installs exact `pi-ai@0.80.6`; published tarballs retain their exact installable dependency.
- Agent runtime: managed Pi exposes only project grid tools, guides, and bounded context/decision tools; the LLM boundary owns provider-specific formats, while `grid-agent` commits ordinary model final text with controller-bound current-turn result/evidence lineage.
- Runtime descriptor: the fixed eight-field transport API is preserved while the production descriptor authoritatively binds catalog, guide, workspace, turn, context, trajectory, acknowledgement, and Pi runtime identity; descriptor mode does not supplement legacy runtime paths.
- Guide authority: the descriptor binds the guide root and index digest; startup and execution use no-follow same-fd read/fstat/digest/named binding and validate protocol, version, root, and resource mapping before any resource read.
- Run isolation: `question_id` is a bounded portable basename, and no-follow exclusive invocation roots plus the cross-process lease reject active or sequential same-ID reuse rather than sharing, escaping, or inheriting stale evidence. Lease state is created from the trusted project root via component-wise dirfd `O_NOFOLLOW` opens and same-fd named bindings for `.grid-agent/run-leases`.
- Canonical capture: Pi atomically persists provider-independent model inputs before provider I/O without waiting for observer acknowledgement.
- Native trajectory: the kernel event spine records model requests/responses, tools, decisions, claims, context revisions, results, and evidence as the authoritative chronology.
- Observation: polling skips already-seen request artifacts before parsing; projection, validation, and integrity diagnostics are deterministic consumers of recorded execution and cannot semantically replace simulator truth.
- Simulator boundary: `gridctl` exclusively owns registered network access and deterministic pandapower 3.4.0 calculations through `grid-capability` protocol 1.0.
- Compatibility contracts: CLI command names, stdout envelope, stderr diagnostics, `grid_*` tool names, tool schemas, `grid-capability/1.0`, current-run evidence admission, and `runs/` artifact layouts remain unchanged. Runtime grid trajectory readers reject hash-valid foreign schema/producer identities while the kernel remains neutral and policy-injectable.
- Analysis context: bounded model-facing views retain active model, sourced constraints, reusable calculations, scenarios, facts, lineage, and explicit omission metadata.
- Reporting: per-question reports render answer first, restore simulation environment context, summarize the observable agent trajectory with compact simulator results, and link persisted detailed trace/current-run evidence artifacts.
- Workbench: the loopback read-only trajectory API and Business/Agent/Context/Evidence workbench consume deterministic projections without mutating runs.
- Verification: unit, package-boundary, install-mode package artifact, E2E, offline/scripted validation, and optional provider-backed continuous Analysis cover the stdout contract, capability boundary, trajectory replay, evidence, and reports.
- Release evidence: the final B-H005 run `runs/climb/20260828T111922Z-b-h005` scored 100/100 with no blockers. Under policy digest `efe8fc8e...`, its live closure reran the fixed kernel/domain/Pi/app/dist/doctor/test/test-e2e/product command allowlist at source revision `e41783558afb57eb04ad04562c7d9b0fe6e6bf0b` and tree digest `9ff57149...`; all nine outputs are `closure-passed` and linked by closure digest `5049c057...`. Same-user HMAC receipts remain integrity snapshots, not the release trust root.
- Mainline integration: `main` was fast-forwarded to `448c407`, then reverified with package boundaries and installed-artifact smoke, 688 grid-agent tests, 165 simulator tests, 43 grid Pi tests, 17 E2E tests, and the 24/24 validation matrix. The temporary Workstream B worktree and feature branch were removed.

## Open Problems (theme-level)

- No release-blocking capability gaps are known in the declared static-analysis scope.
- The pinned Pi dependency tree still contains 2 High and 2 Moderate accepted findings. `configs/runtime/pi-security-risk-exception-v1.json` documents the bounded exception and expires on 2026-09-30; the deterministic gate rejects expiry, pin/lock/installed-graph drift, or a worsened declared baseline. It does not discover a future advisory against unchanged versions.
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
