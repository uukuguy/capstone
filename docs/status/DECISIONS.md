# Architectural Decisions

## 2026-09-29 — Freeze grid-agent application growth under the unified Capstone application

- **Decision:** `capstone-agent` is the canonical application host for all new CLI/TUI, Thread, Run, current-model, Case-batch, API, Web, and Pi/DSH runtime-switching capabilities. `grid-agent` application-level behavior is frozen.
- **Compatibility:** `grid-agent` remains the pandapower compatibility adapter with its exact `run`, `analysis`, and `report` stdout contract and simulator/evidence boundary. Necessary security, dependency, correctness, and compatibility maintenance remains allowed; new application orchestration does not go there.
- **TUI consequence:** `capstone-tui` is a shorthand for the unified Capstone CLI's terminal UI mode, not a new agent application or package by definition. The existing `capstone-agent run` and line-oriented `chat` are reusable foundations; a rich TUI needs the public Thread/event client before UI implementation.
- **Rationale:** one application core prevents divergent Thread/Run/Turn, Authority admission, evidence, and runtime behavior across Web, CLI, and terminal UI while preserving the stable grid compatibility surface.
- **Discussion record:** `docs/superpowers/specs/2026-09-29-agent-interaction-discussion.md`.

## 2026-09-29 — Historical peer-agent names converge on one Capstone application

- **Decision:** the existing `capstone-agent`, `pandapower-agent`, and `pypsa-agent` names must not define three peer agent applications. The target is one Capstone application with model-compatible capability profiles, Domain Packs, and Authority adapters inside it.
- **Compatibility:** retain current package/entrypoint names temporarily where needed for migration and the frozen `grid-agent` compatibility surface. Do not introduce new features into historical peer application paths.
- **Rationale:** the names obscure the ownership direction and invite divergent orchestration, Thread/Run semantics, and evidence behavior. A unified Capstone application is the only public application boundary; domain names describe packs/adapters, not agent products.
- **Open:** choose the final single public executable/distribution name and migration aliases after the Thread/harness contracts stabilize.
- **Discussion record:** `docs/superpowers/specs/2026-09-29-agent-interaction-discussion.md`.

- **Package inventory:** there is no separate `pandapower-agent` distribution today; its historical application code is mainly in `grid-agent` alongside the correctly named `pandapower-domain-pack`. `pypsa-agent` is a real trusted application assembly package. Their migration must follow ownership boundaries rather than a symmetric rename.
- **Refactoring direction:** keep model-family capability assemblies inside Capstone or use separately installed profile distributions where pandapower/PyPSA environment isolation requires it. Exact package names remain open. Do not create new `*-agent` peer product names. Keep existing Domain Pack and Authority names.

- **Compatibility stance:** Capstone has no real external application consumers, so current internal package, registry, worker, session, and API shapes may be refactored. The historical `grid-agent` stdout contract remains a separately frozen repository boundary until deliberately retired; it does not constrain the new Capstone design.

## 2026-09-29 — Model Capability Profiles follow user-selected grid models

- **User-facing rule:** users choose a registered Grid Model. The catalog resolves its implementation family and Authority-owned revision. Capstone then presents eligible ModelCapabilityProfiles/Domain Packs and activates the user-selected set. The system does not claim to know semantic overlap in advance. Profiles and Domain Packs are internal capabilities, not separate user-facing applications.
- **Model switch:** one Thread and its v1 Run may switch between pandapower-backed and PyPSA-backed models. Each switch closes the previous Model Context and opens a new one, recording model/revision and resolved profile identities. Old tools and evidence do not automatically become current-model capabilities or facts.
- **Thread model timing:** Thread creation resolves the default IEEE-39 model to exact Authority-owned revision and implementation family, recording them in initial ModelContext metadata. Provider sessions, Profile handles, and tool catalog preparation are lazy before first execution. Failed revision resolution rejects creation; later preparation failure retains the pinned Thread/model identity for retry. Catalog updates never silently rebind an existing Thread.
- **Persistent data model:** Thread owns the ordered conversation/event stream and current Run/ModelContext pointers; the v1 Run owns multiple Turns and an ordered ModelContext sequence. Each ModelContext has a stable identity, model/revision/implementation family, and enabled package selection revisions. A model switch creates a new context; a package change retains the context identity and advances its selection revision at a Turn boundary. Tool calls, results, evidence, and replay bind to the effective context snapshot.
- **Run lifecycle:** Run uses durable logical states `created → open → closing → closed`, with `failed` reserved for unrecoverable Run-level persistence, integrity, or security errors. Close drains or cancels the active Turn and prevents new queued work. Ordinary tool/Provider/Turn failures, interruptions, and Worker retries leave Run open. Worker execution states remain separate and cannot close Run or change model/capability selection.
- **Turn retry model:** A Turn is one logical user request with one or more immutable Attempts. Each Attempt freezes the effective Model Context, capability selection revision, tool catalog, Provider/model, and Harness runtime snapshot. Retries create new Attempts under the same Turn; at most one Attempt commits answer/evidence. Failed or cancelled Attempt output remains diagnostic only, and idempotency keys return an existing committed result for duplicate submissions.
- **ModelContext controls:** Model switching and capability selection changes are first-class Run control operations in the ordered event stream. Active Attempts keep their snapshot; pending controls apply after the Turn reaches a terminal state. Model switching prepares the new Authority revision, implementation family, exact profile versions, and handles before retiring the old Context; failure preserves the old active Context. A successful switch creates a new Context identity, while package selection changes advance `selection_revision` on the existing Context. One v1 Run has one active Context.
- **Naming correction:** `Application Binding` and `capstone-binding-spi` are superseded design names. The accepted name is `ModelCapabilityProfile`; the intended independent package is `capstone-model-capability-spi`. Existing Kernel `DomainBinding` retains its historical meaning.
- **Four-concern baseline:** the neutral SPI owns descriptor, registry, factory, and exact selection contracts. It has no host, Kernel, Domain Pack, Authority, Pi, DSH, or current-tool imports. Model catalog, Case, network projection, Authority, and tool-catalog shapes are not mandatory SPI fields.
- **Two-layer rationale:** a neutral factory returns a lightweight `ModelCapabilityProfileHandle`; a trusted `CapstoneModelCapabilityAdapter` converts it into current Kernel or future Capstone assembly. This prevents the public SPI from inheriting today's `ApplicationProfile`/`DomainBinding` assumptions and keeps credentials, Authority admission, evidence, and runtime policy in the host and owning Domain Packs.
- **Adapter output:** `CapstoneModelCapabilityAdapter` returns a prepared profile-scoped capability contribution containing bounded tools, execution/admission bindings, and optional projections. The Harness composes contributions and owns public control/events; the new SPI does not expose Kernel `ApplicationProfile` as its output, and raw authority model objects never cross the boundary.
- **Trust/version:** descriptor fields are limited to `profile_id`, `profile_version`, and `spi_version`. Trust belongs to the Registry registration record. A trusted bootstrap registers approved factories and seals the Registry; runtime resolution is exact and read-only, with no implicit latest/range selection. Invalid or mismatched registration fails closed.
- **Lifetimes:** registration is process-scoped, a profile handle belongs to one active Model Context within a Prepared Run, Worker lease belongs to one task, and Thread/Run history is persistent. A Run may sequence different profile handles as models change. Persistent state stores exact model/revision/profile identities, not live handles.
- **Tool-choice correction:** users enable or disable packages at the ModelCapabilityProfile/Domain Pack boundary; all tools from enabled packages are available. Individual tool toggles are unnecessary. Overlap is permitted because semantic conflict may only be recognized by a professional user during tool descriptions, calls, or results. A model-specific default package set may be supplied for common models, and users may temporarily disable packages at a Turn boundary.
- **Tool provenance:** every tool-call and admitted-result projection must show stable tool identity, source profile/version, Domain Pack/version when available, implementation family, model context, and selection revision. This provenance is the primary troubleshooting surface for unexpected or conflicting behavior.
- **Public structure:** standardize these fields as `ToolSourceRef` and attach it to tool lifecycle events plus admitted result/evidence references. It is diagnostic provenance shared by CLI, TUI, SDK, API, and Web, with existing secret and evidence screening unchanged.
- **Harness protocol:** `HarnessPiClient` and `HarnessDSHClient` implement the replaceable low-level runtime client interface; `capstone-harness` owns the public Capstone event Envelope and control commands consumed by CLI, SDK, API, and Web. Native Pi/DSH events remain restricted diagnostics and never bypass Authority admission.
- **Pure runtime parity:** Pi/DSH reference paths share controls, normalized events, persistence, reconnect, and replay, but remain business-isolated with empty capability Contexts by default. They do not load Domain Packs or Authorities, and events carry explicit `runtime_mode` and `authority_mode` markers.
- **Reference context isolation:** `runtime_mode`/`authority_mode` are Attempt-snapshot fields. Reference output remains historical and visibly non-authoritative, excluded from Capstone business memory/evidence unless explicitly quoted as unverified user text. Returning to Capstone restores the previous ModelContext and selection.
- **Event persistence:** one append-only Thread-scoped Capstone event stream is the source for publication, reconnect, replay, and App projections. Normalized public text deltas, bounded tool progress, lifecycle/control, answer, result, and evidence events persist before publication; native Pi/DSH events remain optional diagnostics. Replay never reruns Provider/Authority work, and admitted result/evidence plus final answer persistence precedes committed-event publication.
- **App layout status:** the current three-column App layout is temporary until a scenario-driven interaction design is completed. The earlier conversation/model/context three-pane arrangement is only a candidate hypothesis and must not constrain the new UI design.
- **Replay cursor:** historical viewing uses a client-local read-only cursor. It changes displayed projections without modifying Thread/Run state, current ModelContext, or execution; rerun from history is a future explicit multi-Run operation.
- **Public read models:** all clients share typed `ThreadSnapshot` and `EventPage` semantics for initial load, current state, reconnect, live catch-up, and historical reads. Presentation adapters may differ, while business state interpretation stays shared and rebuildable from the event stream.
- **Control commands:** all public controls use a command envelope with command ID, idempotency key, expected event sequence/state version, bounded payload, and actor/source. Validation returns accepted/rejected; asynchronous terminal state is emitted on the canonical event stream. Duplicate and stale commands are deterministic and do not create duplicate work.
- **Approval and partial execution:** policy-gated tool calls emit bounded `approval_requested` events and accept idempotent, expiring approve/deny commands. Cancellation establishes an admission cutoff; later output is diagnostic. Earlier admitted results remain historical but do not commit a cancelled Attempt or auto-promote into later Attempts. Partial output is diagnostic unless a Domain Pack admits a typed partial result with completeness metadata.
- **Catalog ownership:** user-facing profile labels/descriptions, selectable profile references, implementation-family association, and default package selections belong to a Capstone Model Capability Catalog. Authorities retain model/revision truth; the neutral profile SPI remains presentation- and default-policy-independent.
- **Model-to-Profile resolution:** Authority/Grid Model Catalog resolves model identity, exact revision, implementation family, and model facts; Capstone Model Capability Catalog resolves eligible user-facing profiles, exact approved versions, and optional defaults; the neutral SPI registry plus trusted adapter prepares the selected handles and runtime assembly. Preparation is atomic, semantic overlap is not auto-detected, empty selection is valid for ordinary conversation, and failed preparation leaves the prior Context active.
- **Empty context:** an empty enabled profile set is valid. Capstone can support ordinary conversation, model/capability discovery, context switching, and UI state without domain tools; professional claims, tool calls, admitted results, and evidence require an applicable enabled package. Pure Pi/DSH can use the empty context as a no-domain-tool interaction/event baseline, with no authority or Capstone evidence semantics.
- **Selection control:** expose structured `enable_profile`, `disable_profile`, and `replace_selection` commands. A running Turn freezes its selection revision; changes become pending and apply after terminal completion/cancellation. An empty selection supports ordinary conversation, while professional analysis requires an applicable enabled package. Validation covers exact trusted model-compatible identities and leaves semantic overlap to the user.
- **Historical audit:** the existing `ApplicationRegistry` resolves complete Kernel `ApplicationProfile` objects, while Kernel `DomainRegistry` and `DomainBinding` encode current domain/tool details. The new SPI is independent and uses migration adapters rather than renaming these registries.
- **Discussion record:** `docs/superpowers/specs/2026-09-29-agent-interaction-discussion.md`.

## 2026-09-29 — Capstone is the public brand and default executable

- **Decision:** `Capstone` is the product brand and default command-line program name. `capstone-agent` is the canonical internal name for the single intelligent-agent application layer; it is not the public brand and not a peer application to a domain pack.
- **Naming guidance:** `capstone-harness` names the Capstone-aware execution layer; `capability-agent-kernel` remains the neutral Kernel package; `capstone-app` remains the Web presentation package; Domain Pack names carry domain semantics without an `-agent` product suffix.
- **Rejected:** `capstone-application` and `capstone-application-host` are longer and conflict conceptually with the existing `capstone-app` Web package. No `capstone-agent` rename is planned.
- **Discussion record:** `docs/superpowers/specs/2026-09-29-agent-interaction-discussion.md`.

## 2026-09-25 — Capability-named PyPSA packs and multi-binding composition

- **Decision:** an application may explicitly assemble multiple independently installable Domain Packs. PyPSA's Network modeling is its own pack; operations, capacity planning, and sector coupling are separately named packs. Each new distribution name includes `pypsa`, while the existing pandapower distribution remains compatible.
- **Reason:** PyPSA combines modeling, operating, planning and cross-carrier workflows. A shared, authority-owned immutable `model_ref` lets packs compose without exposing a Python `Network` or coupling their internal state. A single-binding runtime cannot serve the selected multi-pack application.
- **Sequence:** implement multi-binding preparation, Pi routing and per-binding evidence first; then the typed model-ref sharing protocol and Network modeling pack; then activate operations, planning and sector coupling one at a time. Unimplemented package shells expose no tools or binding.
- **Compatibility:** `grid-agent` retains its two-field stdout projection and simulator evidence boundary. Dynamic plugin discovery and enterprise write governance remain separate work.
- **Specification and plan:** `docs/superpowers/specs/2026-09-25-pypsa-multibinding-domain-packs-design.md` and `docs/superpowers/plans/2026-09-25-multi-binding-application-implementation.md` supersede the earlier deferral of Workstream E as the next approved work item; code remains feature-gated until implementation passes its acceptance.

## 2026-09-05 — Delivery closes in the main application checkout

- **Correction:** branch/worktree acceptance is intermediate, not user delivery. Unless explicitly requested otherwise, integrate accepted commits into main and verify its actual application entry point and local runtime before claiming completion.
- **Action:** main fast-forwarded to1c32c0a; OP13 uncommitted changes remain excluded. Main recovery-baton edit is preserved in the named pre-integration stash; unrelated guide and ignored runtime/user data remain intact. Post-integration regression is required and tracked in the canonical plan.
- **Precedence:** supersedes the earlier branch-only closure wording. Does not authorize deleting deferred work, paid provider calls, remote publication or new-domain implementation.
- **Verification:** main import paths and public application factory confirmed; doctor/test/application2/2 passed. First E2E30/31 exposed an unpinned test model; two explicit test environment settings fixed it without changing production logic or user configuration. Focused1 and fullE2E31, business7/10/8 and coverage24/24 passed; continuation79559 exit0.

## 2026-09-05 — Framework-first optimization scope supersedes service scaling

- **Decision:** the user's product correction governs optimization v2: prioritize public Kernel SPI, independently installable business capability packs, common agent orchestration and current-run authority evidence. Enterprise service capacity is not the target.
- **Disposition:** OP08's arbitrary-JSON bounded parser and OP13's complex segmented writer/recovery are DEFERRED, not implemented or proven unnecessary. Keep the legacy default and isolate unaccepted changes. Existing prototypes and peripheral mechanisms are recorded for later cleanup, not deleted now.
- **Acceptance:** OP14 reconciles normal framework, package, compatibility and evidence gates. Inventory remains a cross-domain conformance proof; C.2 remains an unselected candidate with no automatic external research or paid validation.
- **Evidence:** canonical optimization plan v2 and `capstone-scope-cleanup-backlog.md`. This decision overrides the earlier conditional rule that OP12 scale measurements automatically require OP13 productionization.
- **Closure:** OP14 accepted against7e9b10c executable source: doctor/check-release exit0, real authority application validation2/2, business suites7/10/8 and capability24/24. Final document review conflicts corrected. Keep the feature branch and excluded OP13 work intact; no automatic merge, publication, new domain or cleanup.

## 2026-09-05 — Version report optionality in the owning domain contract

- **Decision:** OP-03 keeps `capability-agent-output/1.0` and the exact grid compatibility stdout unchanged, while revising the pandapower payload schema to `pandapower-static-analysis-output/1.1`.
- **Reason:** the existing domain `1.0` validator requires an admitted report reference. Silently permitting null under that identity would violate strict readers' legitimate expectations and keep presentation coupled to primary completion.
- **Contract:** retain the five payload fields and count/mode checks; an absent or explicit-null context report yields a null payload reference. A non-null report must still have the artifact reference format and current-run admission. No placeholder artifact, weakened authority check or rewritten historical output is permitted.
- **Failure semantics:** ordinary report/observer faults produce fixed run-scoped diagnostic artifacts and refs, or sanitized stderr if diagnostic storage also fails. Required answer/context transactions and BaseException cancellation remain fail closed/propagating. Safe report publication pins parent descriptors and verifies stage identity before and after publication.
- **Control:** exact file scope, tests, review and closure remain in the OP-03 section of the canonical optimization plan. Historical C.1 specs and synthetic compatibility `1.0` inputs remain historical evidence.

## 2026-09-05 — Close framework assurance and verification before C.2

- **Status:** optimization direction accepted; current implementation status belongs to the canonical plan.
- **Decision:** execute OP-01–OP-14 from `docs/superpowers/plans/2026-09-05-capstone-optimization.md`; retain direct project routing and use that document as the sole optimization execution ledger.
- **Rationale:** review found zero-reference answer admission and legacy run submission gaps, report failures blocking accepted answers, incomplete default gates, and scaling costs; these undermine the guarantees a second production domain would inherit.
- **Assurance boundary:** current-run lineage is not proof of freeform prose semantics. Domain-owned admission must distinguish deterministic information, authority-backed lineage and limitations; no grid keyword heuristics in Kernel and no model-owned answer submission.
- **Failure boundary:** mandatory evidence/answer persistence fails closed; report, preview, cache and progress failures are diagnostic and cannot revoke an accepted primary answer.
- **Scope:** preserve public grid compatibility, single binding, existing runs and C.1 historical evidence. Inventory remains conformance infrastructure. Segmented storage is conditional on measured OP-12 budgets; Pi risk expiry remains a release gate.
- **Precedence:** replaces the prior immediate next action of C.2 selection; does not select GitHub as the second domain or authorize online provider runs.
- **Evidence:** `docs/status/2026-09-05-capstone-design-code-review.md`.

## 2026-08-29 — A read-only inventory authority is the cross-domain conformance proof

- **Decision:** instantiate a second, independently packaged domain with `inventory-reference-service` and `inventory-domain-pack`, using only the public Kernel Domain Pack SPI and unchanged generic Pi transport.
- **Reason:** a non-grid authority with its own protocol, resources, projectors, and current-run evidence proves reuse more strongly than another in-memory fixture while avoiding premature write-governance and multi-domain routing concerns.
- **Boundary:** inventory capabilities are read-only and remain a conformance/reference product, not a runtime-selectable `grid-agent` mode. Dynamic discovery and multi-domain composition remain Workstream E; governed mutations remain Workstream D.
- **Protection:** `capability-agent-kernel`, `pi-capability-tools`, and `trajectory-workbench` are digest-pinned protected paths. Package and release gates reject changes, reverse dependencies, and source-layout coupling.
- **Specification:** `docs/superpowers/specs/2026-08-29-workstream-c-inventory-reference-domain-design.md`
- **Plan:** `docs/superpowers/plans/2026-08-29-workstream-c-inventory-reference-domain.md`

## 2026-08-19 — Answer submission is controller-owned

- **Decision:** Pi/LLM may use only project-defined grid tools and `grid_guide_open`; after tool use it returns ordinary reader-facing final text. `grid-agent` deterministically commits that text and binds the current turn's consumed and produced result/evidence lineage.
- **Rationale:** provider and model tool-call behavior must not decide whether a valid analysis answer is persisted. Moving submission into the controller makes online `run` and continuous `analysis` provider-independent while preserving the simulator boundary.
- **Superseded report consequence:** reports were initially documented as evidence-first projections with recorded simulator/tool results before model prose. The 2026-08-19 readable trajectory decision below supersedes only that presentation order; failed-turn evidence preservation and diagnostic boundaries remain.
- **Specification:** `docs/superpowers/specs/2026-08-18-controller-owned-answer-submission-and-evidence-first-report-design.md`
- **Plan:** `docs/superpowers/plans/2026-08-19-controller-owned-answer-submission-and-evidence-first-report.md`

## 2026-08-19 — Reports are answer-first with a bounded observable trajectory

- **Decision:** Each question renders answer, simulation context, compact observable agent trajectory, then execution status/evidence. Simulator results appear inside the step that produced them; raw JSON remains in the linked detailed trace.
- **Rationale:** A result-first JSON dump obscured answers, removed useful context, and weakened causal diagnosis. Generic capability labels were too repetitive to explain inputs, results, recovery, or reuse.
- **Boundary:** The renderer uses recorded actions, arguments, results, lineage, failures, and optional declared decisions. It does not expose or invent private chain-of-thought and does not require a model narration tool.
- **Density:** Target six milestones and 20–25 trajectory lines per question; failures and distinct safety-relevant findings are never dropped to meet the target.
- **Supersedes:** The report-order consequence in the 2026-08-19 controller-owned submission decision; controller-owned submission itself is unchanged.
- **Specification:** `docs/superpowers/specs/2026-08-19-readable-agent-analysis-trajectory-report-design.md`
- **Plan:** `docs/superpowers/plans/2026-08-19-readable-agent-analysis-trajectory-report.md`

## 2026-08-18 — Model-facing contracts must publish exact composition syntax

- **Decision:** dynamic creator contracts publish the exact `{"element_ref":"<earlier_local_id>"}` encoding and transaction ordering rule; guide tools enumerate only the resource IDs present in the generated guide index.
- **Reason:** a boolean “accepts reference” marker and unconstrained guide string forced the LLM to guess encodings and resource names even though the execution capability already existed.
- **Boundary:** this is contract discovery, not a question-specific shortcut; creator execution remains allowlisted and all network construction remains inside `gridctl`.
- **Validation:** the standard seven-question provider analysis passes, and a focused provider regression performs first-attempt local-reference model creation without audit findings.

## 2026-08-18 — Full pandapower static-analysis capability is current scope

- **Decision:** all pandapower 3.4.0 capabilities relevant to static power-system analysis are current release scope, not future WP-B work. Test questions probe the capability surface and never define it.
- **Architecture:** publish a contract-driven model/revision/dataset/analysis/result substrate and bind complete static-analysis families behind `gridctl`; Pi tools are generated from the same contracts.
- **Boundary:** raw Python, DataFrames, pandapowerNet objects, arbitrary file/database I/O, plotting, time-series/control simulation and unpinned optional external solver runtimes remain intentionally excluded.
- **Release:** every `in_scope` row in `configs/capabilities/pandapower-3.4.0-static-analysis.json` must reach 100% deterministic release coverage.
- **Specification:** `docs/superpowers/specs/2026-08-18-pandapower-static-analysis-full-capability-design.md`
- **Plan:** `docs/superpowers/plans/2026-08-18-pandapower-static-analysis-full-capability.md`

## 2026-08-17 — Unified LLM runtime boundary

- **Decision:** Provider-specific request and response fields remain exclusively
  inside `pi-ai` adapters. Pi exposes the final provider-independent invocation
  before network I/O, and trajectory records the exact canonical request rather
  than the raw provider payload.
- **Reason:** Raw `before_provider_request` capture made valid provider evolution
  capable of terminating the core `make analysis` flow. The repository already
  depends on a multi-provider normalization layer; the framework must consume its
  stable contract instead of duplicating provider logic.
- **Replay:** A request is durably committed before provider I/O with its canonical
  context, tools, public options, correlations, runtime/adapter versions, and hash.
  Wire-level diagnostics remain adapter-owned and non-authoritative.
- **Specification:**
  `docs/superpowers/specs/2026-08-17-unified-llm-runtime-boundary-design.md`

## 2026-08-14 — Unified trajectory event spine and workbench

- **Status:** approved design; implementation not started
- **Decision:** make a typed, append-only, hash-chained native run event spine the authoritative chronology, with independent Agent, Business, Context, and Artifact projections.
- **Rationale:** the `v0.2` artifacts already prove execution and evidence but are split across related timelines. One durable chronology supports replay, exact model-input reconstruction, event-level context time travel, and a polished business-first workbench without weakening simulator or evidence authority.
- **Constraints:** DeepSeek Harness is prior art only; hidden chain-of-thought is excluded; historical runs remain immutable; the UI and API are read-only; numerical and network claims remain under `gridctl` and current-run evidence contracts.
- **Specification:** `docs/superpowers/specs/2026-08-14-unified-trajectory-workbench-design.md`

## 2026-08-14 — Dependency-ordered trajectory delivery

- **Status:** approved plan; implementation not started
- **Decision:** deliver the platform through five gated plans in order: event spine, native capture, projections plus immutable `v0.2` import, loopback read-only API, then React Workbench.
- **Rationale:** each layer establishes a typed interface and focused regression gate before a consumer depends on it; the UI cannot become an alternate source of truth or force historical artifacts to be rewritten.
- **Technology boundary:** Python/Pydantic own chronology and replay; FastAPI/uvicorn expose fixed read-only loopback routes; React/TypeScript/Vite/TanStack Virtual implement the operator workbench; Vitest and Playwright cover interaction, accessibility, and visual states.
- **Roadmap:** `docs/superpowers/plans/2026-08-14-unified-trajectory-implementation-roadmap.md`
