# Agent Interaction and Grid Workspace — Discussion Record

> Date: 2026-09-29. Status: active discussion record, **not an approved implementation specification**. This file preserves the conversation so design work can continue without relying on chat history. Items marked **Decided** reflect explicit user agreement; items marked **Proposed** remain subject to review.

## Goal and product position

**Decided.** Capstone will add full agent interaction to its App in milestones. `capstone-agent` is the independent application-level agent core, intended to serve CLI, SDK, API, and Web. Cases and open-ended dialogue must use the same Capstone business capabilities. `pandapower-agent` and `pypsa-agent` are internal implementations/adapters of `capstone-agent`, rather than separate product cores. Having to adapt both independently today is historical compromise and may be refactored when the new interaction path makes that work appropriate.

Preserve the repository's ownership direction: `Application -> Domain Pack -> Kernel -> registered Authority`. An application may select model capability profiles and public contracts; Domain Packs own semantic tools and result/evidence admission; the Kernel owns neutral turns, trajectories, artifacts, and replay; registered Authorities own model revisions and facts. A new `capstone-harness` must fit this architecture rather than becoming a fifth domain ownership layer. See [Capstone framework](../../architecture/capstone-framework.md) and [repository agent contract](../../../AGENTS.md).

## Vocabulary and boundaries

| Term | Intended responsibility | Status |
| --- | --- | --- |
| `capstone-agent` | Canonical internal name for the single Capstone intelligent-agent application host: CLI/SDK/API/Web entry points, selection, auth, ledger, worker, deployment, and public projections. It is not a peer product application to a domain pack and not the lower-level harness runtime. | Decided. |
| `grid-agent` | Frozen pandapower compatibility adapter. It keeps existing compatibility commands and contracts and receives only necessary maintenance; it is not the target for new Thread, TUI, model, Case, or runtime-switching features. | Decided. |
| `capstone-tui` | Conversation shorthand for the TUI form of the unified Capstone CLI. It is not a new package, a second agent core, or a third application. | Decided terminology. |
| `pandapower-agent` / `pypsa-agent` | Historical names for domain/application implementations. They must not remain as peer product applications; future refactoring moves their behavior behind the unified Capstone application and selected Domain Pack/adapters. | Decided direction; migration/name plan pending. |
| `capstone-harness` | Reusable Capstone-aware agent execution service: run/turn control, bounded runtime event normalization, policy coordination, domain-tool orchestration, current-run context, and application-facing events. It consumes Domain Pack admission results; it does not independently declare authority facts. | Decided responsibility; interface and placement pending. |
| Pi / DSH | Replaceable **pure harness runtimes** beneath Capstone's business harness. Their native interaction can also be exposed as reference/comparison modes. | Decided. |
| Domain Pack | Publishes bounded semantic tools, policy, guides, projections, and authority-backed admission. | Existing architectural invariant. |
| Registered Authority | Owns grid models, revisions, calculations, result datasets, and evidence. | Existing architectural invariant. |
| Grid Model | User-facing registered model and Authority-owned revision selected as the current model of a Thread. | Decided relationship; catalog contract pending. |
| Model Implementation Family | The underlying model/runtime family, such as pandapower or PyPSA, that determines which semantic capabilities can operate on a model. | Decided relationship; exact identity contract pending. |
| ModelCapabilityProfile | A model-implementation-compatible capability composition that may contain Domain Packs, Authority adapters, policies, tools, and projections. It is not a user-facing application. | Decided terminology and direction; SPI details pending. |
| Model Capability Selection | The explicit, versioned set of enabled ModelCapabilityProfiles/Domain Packs for the current Model Context. It lets a user choose capability packages without changing the registered model. | Decided v1 direction; selection contract pending. |
| Thread | User's continuing dialogue/workspace context with one current grid model in v1. | Decided concept; persistence contract pending. |
| Run | One agent execution instance within a Thread. | Decided concept; terminal/lifecycle details pending. |
| Turn | One instruction and its agent processing/committed response. A Case batch contains multiple Turns. | Decided concept; event contract pending. |
| Case | A reusable ordered instruction sequence, executed as a multi-turn batch. It is an application capability, not a Thread prerequisite or parent. | Decided. |

The worker, ledger, and API are hosting/control-plane parts of `capstone-agent`. They are not Pi and not themselves the business harness. Existing `AgentApplication.run_stream` and the narrow `ProviderSession.start/prompt_and_wait/stop` provide a starting point, but the intended full interaction requires richer control and events.

**Decided freeze boundary.** New application-level capabilities go directly into the unified Capstone application and its shared `capstone-harness`. The current `capstone-agent` package is the implementation foundation during migration, not evidence of a second product alongside `pandapower-agent` and `pypsa-agent`. `grid-agent` keeps its stable pandapower compatibility entry points, exact stdout behavior, and simulator/evidence boundary. It may receive security, dependency, correctness, and compatibility fixes, but it is not extended with the new Thread/TUI/application orchestration model. The `capstone-tui` shorthand describes the unified CLI's terminal UI and must consume the public Capstone client/harness contract rather than import historical agent application internals.

**Naming target.** The product presents one Capstone agent application with internal model capability profiles and adapters. `pandapower-agent` and `pypsa-agent` are not peer applications in the target architecture. The public brand and default executable are `capstone`; `capstone-agent` is the canonical internal application-layer name. Naming must not turn domain packs into peer agent products.

**Current package inventory.** The repository does not currently contain a separate `packages/pandapower-agent` distribution. Its historical application-level behavior is split between the frozen `grid-agent` compatibility/application package and the already correctly named `pandapower-domain-pack`. `packages/pypsa-agent` does exist and currently contains a trusted PyPSA application profile/registry, report shell, case preview, network view/story projection, and worker assembly; its domain packs and `pypsa-model-authority` are separate packages. These boundaries are asymmetric and must be refactored by ownership rather than mechanically renamed.

**Proposed target names.** Move generic application assembly and orchestration into `capstone-agent`/`capstone-harness`; represent model-family capability profiles and projections as Capstone-owned modules or separately installed profile distributions where incompatible pandapower and PyPSA environments require isolation. Keep `pandapower-domain-pack`, the capability-named `pypsa-*-domain-pack` packages, and `pypsa-model-authority` as domain/authority names. A future `capstone-grid-compat` name could clarify the frozen legacy adapter, with `grid-agent` retained as a compatibility alias. These are proposals, not approved package renames.

**Decided public and internal names.** `Capstone` is the product brand and default command-line program name. `capstone-agent` is the canonical internal name for the intelligent-agent application layer. `capstone-harness` names the Capstone-aware business execution layer, and `capstone-app` names the Web presentation client. `capstone-application` and `capstone-application-host` are rejected as longer names that conflict conceptually with `capstone-app`; no rename of `capstone-agent` is planned.

## Runtime paths and comparison

**Decided.** Thread interaction must be able to switch between a Capstone business path and pure Pi/DSH reference paths. Preserve three named clients:

```text
Thread UI / other application projections
    -> capstone-agent gateway (auth, secrets, ledger, public API)
       ├── CapstoneThreadClient -> capstone-harness -> Pi/DSH runtime adapter
       │                           -> Kernel + selected Domain Pack -> Authority
       ├── HarnessPiClient      -> pure Pi runtime reference path
       └── HarnessDSHClient     -> pure DSH runtime reference path (empty shell initially)
```

This diagram expresses comparison modes, not permission for the browser to contact privileged runtime endpoints directly. Browser requests continue through a bounded, authenticated `capstone-agent` gateway. The production Capstone path must keep existing allowlisted tool, Authority, evidence, and secret boundaries. Pure runtime output is useful for comparing interaction and tool behavior; it cannot become a Capstone current-run authoritative result merely by being displayed. Whether reference modes receive any Capstone domain tools, and what comparison parity means, remain open.

**Proposed.** Define one Capstone-owned UI-facing `ThreadRuntimeClient` capability interface for the three clients. `HarnessPiClient` must be implemented locally; assistant-ui supplies Pi client/runtime primitives, but no Capstone-specific class by that name. The native Capstone Thread API and Pi's native client contract are distinct wire protocols, even if adapters expose comparable UI capabilities. `HarnessDSHClient` should compile as a deliberately unavailable shell without DSH-specific types leaking into public Capstone contracts. DSH support is a future milestone; the official DSH repository currently labels itself a developer preview with breaking changes possible.

**Research considered.** The initial candidate was assistant-ui + `@assistant-ui/react-pi` + a custom `HarnessPiClient`. assistant-ui's Pi package provides a JSON-safe `PiClient`, event projection, HTTP/Node transports, message snapshots, streaming, tool events, and control operations. Its custom runtime/transport path is a candidate for the Capstone business mode. AG-UI offers a broader event vocabulary and assistant-ui integration but is not yet selected as Capstone's canonical contract. Capstone's authority admission, model context, evidence, and grid projections make a Capstone-owned public contract the current recommendation. Sources: [assistant-ui react-pi](https://github.com/assistant-ui/assistant-ui/blob/main/packages/react-pi/README.md), [assistant-ui custom runtimes](https://www.assistant-ui.com/docs/runtimes/custom/overview), [AssistantTransport](https://www.assistant-ui.com/docs/runtimes/custom/assistant-transport), [AG-UI events](https://github.com/ag-ui-protocol/ag-ui/blob/main/docs/concepts/events.mdx), [DSH repository](https://github.com/deepseek-ai/deepseek-harness).

## Thread, Run, Turn, Case, and model

**Decided.** v1 has one Run per Thread. A Run has multiple Turns. The persistent identities and API should leave room for a later one-Thread/many-Run version supporting reruns, branches, and comparisons. Do not make a Case mandatory to create or use a Thread. A Case can be recognized or selected and executed as a batch of ordered Turns; its steps remain individually observable and attributable to one `batch_id`.

**Decided Thread → Run → ModelContext data model.** A Thread persists the dialogue workspace, ordered event stream, active Run identity, and current ModelContext identity. Its single v1 Run persists the multi-Turn execution history and an ordered sequence of ModelContexts. Each ModelContext has a stable `model_context_id`, registered `model_id`, Authority-owned `model_revision`, `implementation_family`, and enabled ModelCapabilityProfile/Domain Pack identities with a selection-revision history. A model switch closes the old context and opens a new one within the same Run; a package enable/disable operation keeps the context identity and advances its selection revision at the next Turn boundary. The empty enabled set is a valid ModelContext state. Tool calls, results, evidence, and replay bind to the effective `thread_id`, `run_id`, `model_context_id`, model/revision, and selection revision; tool activity additionally carries `ToolSourceRef`. This keeps the current model pane and historical evidence on the same event chronology and leaves room for later multiple Runs per Thread.

**Run lifecycle accepted.** Run has a durable logical lifecycle independent from Worker execution leases:

```text
created -> open -> closing -> closed
                         \-> failed
```

`open` accepts Turns, model switches, and capability selection changes. A user close request enters `closing`, lets the active Turn finish or be explicitly cancelled, prevents new queued work, and commits `run_closed`. `failed` is reserved for unrecoverable Run-level persistence, integrity, or security errors. Ordinary tool errors, Provider failures, Turn failures, interruptions, and Worker retries leave the Run usable. Worker execution keeps its own transient states (`idle`, `queued`, `running`, `waiting`, `suspended`, `interrupted`) and cannot close the Run, change the current model, or change capability selection. A closed Run remains replayable and read-only; future multi-Run support may create another Run without changing this v1 state meaning.

**Turn retry model accepted.** A Turn is the durable logical user request; each execution is an immutable Attempt under that Turn. An Attempt captures the effective Model Context, model revision, enabled profile/package identities, selection revision, tool catalog hash, Provider/model identity, and Harness runtime version. The Attempt lifecycle is `created → accepted → running → waiting → committing → committed`, with terminal `failed`, `cancelled`, or `interrupted` states. Retry creates a new Attempt under the same Turn and never overwrites the earlier event trail. At most one Attempt may commit the Turn's answer and admitted evidence. Tool and Provider events from failed or cancelled Attempts remain diagnostics and do not become current-run answer/evidence references. Duplicate client submissions use an idempotency key to return the existing committed result.

**ModelContext control operations accepted.** Model switching and capability selection changes are first-class Run control operations recorded in the same ordered event stream as Turns. A running Attempt keeps its immutable context snapshot. A control request received while an Attempt is active becomes pending and applies only after the Turn reaches a terminal state. Model switching prepares the new Authority model revision, implementation family, exact Profile/Domain Pack versions, and profile handles before retiring the old Context; preparation failure leaves the old Context active. A successful switch creates a new `model_context_id` and makes the old Context read-only. A capability selection change keeps the Context identity and creates a new `selection_revision`. UI controls and natural-language requests normalize to the same validated control command. In v1, one Run has one active ModelContext at a time.

**Decided.** A Thread has one **current grid model** at a time in v1. It supports ordinary conversation and professional conversation about that model. The user can switch the current model within the conversation, including between pandapower-backed and PyPSA-backed models. Each switch closes the previous Model Context and opens a new one inside the same Run. A later version may keep multiple model contexts concurrently in one Thread, but cross-model comparison and handoff need explicit contracts and are outside v1.

**Decided model-to-capability relationship.** The user selects a registered Grid Model, never an individual tool. The model catalog resolves the selected model to an implementation family and Authority-owned revision. Capstone then resolves the model's eligible ModelCapabilityProfiles/Domain Packs and activates a user-selected subset. A model implementation may offer multiple packages with overlapping or unknown semantic coverage; Capstone does not claim it can determine those conflicts at registration time. A profile may compose multiple Domain Packs; `capstone-agent` remains the single user-facing application.

**Decided tool-choice requirement.** Users choose enabled packages at the ModelCapabilityProfile/Domain Pack boundary, and all tools published by an enabled package become available. Individual tool toggles are unnecessary for v1. The system permits overlapping packages because semantic duplication may only become visible through actual tool descriptions, calls, and results; users can disable a package at a later Turn when their professional judgment identifies a conflict.

**Proposed active capability selection.** Add a Capstone-owned, versioned Model Capability Selection set inside each Model Context:

```text
Model Context
  ├── Grid Model + revision
  ├── implementation family
  └── ModelCapabilitySelection             # enabled profile / Domain Pack set
```

The UI presents user-facing package descriptions and Domain Pack-level enable/disable controls, not individual tool switches or raw internal names. A selection change creates a durable revision and applies at a Turn boundary. Each tool call and admitted result records the effective selection revision. A model-specific default selection may be supplied by the catalog for common models; users can adjust it during the Thread. The neutral Model Capability SPI remains tool-shape agnostic and does not attempt semantic conflict detection.

**Model Capability Catalog accepted.** User-facing package labels, descriptions, implementation-family association, selectable profile references, and model/implementation default selections belong to a Capstone-owned Model Capability Catalog. Registered Authorities remain responsible for model identity and revision truth. The neutral Model Capability SPI keeps identity and registration contracts independent of presentation metadata and default-selection policy.

**Empty capability context accepted.** A current Grid Model with an empty enabled profile set is a valid first-class context. In the Capstone business path it supports ordinary conversation, model/context explanation, capability discovery and selection, model switching, clarification, and UI workspace state. Professional model claims, simulator-backed calculations, tool calls, admitted results, and run evidence require an enabled applicable package; the assistant must state the capability boundary rather than infer model facts. In pure Pi/DSH reference paths it provides a useful no-domain-tool baseline for streaming, cancellation, event normalization, replay, and interaction comparison without domain-tool contamination. Pure runtime output remains non-authoritative and cannot create Capstone evidence merely because a model context is visible.

**Capability selection control accepted.** Expose structured Capstone commands for `enable_profile`, `disable_profile`, and `replace_selection`. UI controls and natural-language requests may both target these commands, but the harness validates and commits one canonical selection event. A running Turn freezes its `selection_revision`; changes become pending and take effect after the Turn completes, fails, or is cancelled. The next Turn receives a refreshed tool catalog. Selection validation checks model-family compatibility, exact registered version, trust, and duplicate identity; it does not diagnose semantic overlap. An empty enabled set remains valid for ordinary conversation, while a professional analysis Turn must request an applicable enabled capability and return a bounded prompt if none is active. Every committed selection receives a durable revision, and prior Turns retain their original selection and `ToolSourceRef` lineage.

**Decided.** A new Thread defaults to the **registered IEEE-39** model. The application chooses this default; the registered Authority/catalog resolves the actual model reference and revision. The default must not be hardcoded as a Kernel concept. Model switches must be explicit and replayable. Results, network overlays, and evidence retain the model identity and revision applicable when they were produced. Prior model facts must not silently appear as current-model facts after a switch.

**Proposed.** Ordinary informational turns may answer without a simulator call and should create no run evidence. Professional turns use the current Model Context's enabled profile/package tools and Authority. Explicit Case launch should use the Thread's current model unless the Case declares an incompatible model requirement; exact compatibility behavior is open. Model switch should validate model availability, implementation family, eligible packages, and revision; emit a durable event containing those identities; clear temporary visual focus; and use the new context for subsequent professional turns. A package selection change applies at a Turn boundary and must not silently reinterpret prior tools or evidence.

**Open.** The earlier proposal that a Thread could begin without a model is superseded by the IEEE-39 default. It remains to define whether Thread creation eagerly resolves a concrete revision or defers that resolution until first execution, how user-facing package labels and model defaults are declared, and how active profile handles are replaced or sequenced when the user changes package selection or model within one Run.

## Events and application projections

**Decided direction.** `capstone-harness` consumes rich Pi/DSH events, performs Capstone-specific processing, and exposes a common Capstone run/event stream to CLI, SDK, API, and Web. Thread is one projection of that shared stream. Native runtime events must not be mistaken for admitted business facts or a stable Capstone public API. Diagnostic native events may be retained server-side subject to security and storage policy.

**Capstone event/control protocol accepted.** `HarnessPiClient` and `HarnessDSHClient` implement a replaceable low-level runtime client interface for session start, prompt submission, cancellation/interruption, close, state, and native event delivery. `capstone-harness` owns the public Capstone protocol above those clients. CLI, SDK, API, and Web consume a Capstone event Envelope carrying `event_id`, monotonic `event_seq`, `event_type`, applicable Thread/Run/Turn/Attempt identifiers, Model Context and selection snapshot fields, timestamp, and bounded payload. Public controls normalize to Capstone commands such as `submit_turn`, `retry_attempt`, `cancel_attempt`, `switch_model`, profile selection changes, and `close_run`. Pi/DSH native events may be retained as restricted runtime diagnostics, but cannot become public business facts or bypass Authority admission.

**Event persistence accepted.** One append-only canonical Capstone event stream is the source for real-time delivery, reconnect, replay, and all App projections. The ordering scope is Thread, with each event carrying `run_id` for current and future multi-Run filtering. A normalized public event is durably appended and safety-filtered before publication; clients resume with `after_seq` and deduplicate by `event_id`/`event_seq`. Public text deltas, bounded tool progress, lifecycle, control, final answer, admitted result, and evidence events are persisted in v1. Pi/DSH native events remain optional restricted diagnostics. Replay reads the saved event and context snapshots without rerunning Provider or Authority work. Result/evidence admission and final answer persistence complete before their committed events are published. Materialized Thread/model/evidence projections are rebuildable views, not separate business truth.

**Proposed event groups** (names and schema are not approved):

- Lifecycle/control: `run_started`, `turn_started`, `turn_committed`, `run_completed`, `run_failed`, `run_cancelled`, model switch, cancellation, reconnect/replay.
- Streaming interaction: `text_delta`, bounded reasoning/status indicator, tool-call start/progress/completion, user approval request/decision where applicable, capability-policy change.
- Business admission: Authority result admitted, evidence admitted, artifact/report available, bounded network projection updated.
- Batch execution: Case batch started, step started/completed, batch completed/failed.

**Proposed event identity.** A public event envelope should carry a monotonic cursor and appropriate `thread_id`, `run_id`, `turn_id`, optional `batch_id`, source, visibility, and model/revision/profile context. The exact event taxonomy, visibility levels, snapshot format, recovery behavior, and whether a separate harness protocol version is warranted are open. Do not expose hidden chain-of-thought, raw Authority objects, credentials, or unadmitted claims.

**Decided tool provenance requirement.** Every tool-call start, progress, completion, failure, and admitted result must expose bounded provenance sufficient for a professional user to diagnose package overlap or an unexpected result. The public projection should include the stable tool identity and display name, the source ModelCapabilityProfile and version, the Domain Pack and version when available, the implementation family, the active model context, the selection revision, and result/evidence references. The UI should show this source beside the tool activity and allow the user to disable the responsible profile/package for later Turns. Arguments and results remain subject to existing secret, raw-object, and evidence-boundary rules.

**ToolSourceRef accepted.** Standardize the bounded source projection as `ToolSourceRef` and attach it to every tool-call lifecycle event and every admitted result/evidence reference:

```text
ToolSourceRef
  tool_id
  tool_display_name
  model_capability_profile_id/version
  domain_pack_id/version (when available)
  implementation_family
  model_context_id
  selection_revision
```

`ToolSourceRef` is a provenance projection, not a permission grant. It gives CLI, TUI, SDK, API, and Web a common diagnostic surface while preserving secret screening, raw-object boundaries, and current-run evidence admission.

**Proposed projections.** CLI maps durable output to its existing compatibility envelope while progress stays on stderr; SDK exposes event iteration and snapshots; API exposes authenticated commands, snapshots, SSE replay; Web maps the same events to assistant-ui messages/tools and the grid/context panes. The grid compatibility `run`, `analysis`, and `report` commands must keep exactly one stdout JSON object with `question_id` and `answer_output`. The generic output remains its separate `core` plus `domains.<binding_id>` envelope.

## App redesign: whole workspace, not a chat widget

**Decided.** Redesign all three columns. Current App structure is Case library / Case run plus network story / details. The new conceptual structure is:

```text
Thread conversation | Current grid model workspace | Context and evidence
```

The Case library becomes an auxiliary batch launcher instead of a persistent primary column. The center model area is a peer projection of the Thread, not a Case-owned widget. Chat, model projections, result references, and replay use one ordered event source. Existing bounded network contracts and rendering code can be reused selectively, but the workspace state root changes from `caseCard + session` to `thread + current_model + run`.

**Proposed left pane.** Thread messages, text streaming, tool progress and result cards, ordinary and professional turns, composer, cancellation/retry, and Case batch launch. A message can link to the model element or replay point it describes.

**Proposed center pane.** Model identity and revision, model switch, an authoritative topology canvas, focus and result overlays, follow-analysis control, concise current analysis context, and access to replay. The default IEEE-39 topology should be visible when its bounded projection is available. The canvas must label partial/omitted network data and never infer topology or numerical values from assistant prose.

**Proposed right pane.** Context inspector for selected model element, admitted findings, evidence and artifacts, plus Case batch status and step replay. Full narrative answers stay in the Thread. Existing post-run `NetworkStory` is a candidate replay projection; live in-run topology updates require a separate design and cannot be claimed as current behavior.

**Proposed bidirectional interaction.** Thread events may focus/highlight validated model elements and show admitted overlays. Pan, zoom, hover, and ordinary selection stay local. Explicit actions such as “ask about this element”, “analyze this element”, and model switch create structured commands. Selecting a historical step moves a replay cursor without rerunning calculations. Agent-driven focus should respect manual exploration; a follow-analysis control can resume it.

**Proposed responsive direction.** Desktop uses three panes with the model canvas as the main visual surface. At narrower widths, the inspector becomes a drawer; on phone, model, Thread, and inspector need a clear single-surface navigation pattern. Exact sizing, pane priorities, accessibility behavior, and visual language require a dedicated UI design pass. The prior illustrative `320px / flex / 340px` widths are not approved measurements.

## Existing implementation and expected migration

- `packages/capstone-agent/src/capstone_agent/host_api.py`, `ledger.py`, `session.py`, `worker.py`, `protocol.py`, `application.py`, and `runtime.py` provide the current API/worker/session/Pi assembly. Today session creation and App usage are oriented toward registered cases and the worker emits coarse progress, committed answer, network, and terminal events.
- `packages/capstone-agent/src/capstone_agent/cli.py` already provides a reusable headless `run`, line-oriented interactive `chat`, local `serve`, hosted service, worker, and test seams. It is a foundation for the new client surface, not a finished TUI: it currently waits for completed answers, has no Thread/model-switch/snapshot client, and is coupled to `WorkerSession` rather than a public rich event/control client.
- **TUI recommendation.** Keep the unified Capstone CLI's headless `run` and line-oriented `chat` modes as protocol clients, then add the `capstone-tui` terminal UI mode on top of the same public client/event contract. It is a presentation mode, not a separate package or agent application by definition. It must not import Kernel, Domain Packs, `WorkerSession` internals, or historical `*-agent` application internals. The final command name, package layout, and toolkit remain open.
- `packages/capability-agent-kernel/` provides `AgentApplication.run_stream` and a narrow `ProviderSession` boundary. The richer harness control/events should evolve from these contracts while preserving Kernel neutrality.
- `packages/capstone-app/src/App.tsx` currently renders `CatalogPanel`, `CaseWorkspace`, `RunPanel`, `NetworkView`, and `DetailPanel`. Case selection and instructions drive the center run and its network story. `api.ts` and `types.ts` consume `/api/v1` sessions and SSE. The App currently has React/ReactDOM, not assistant-ui, as dependencies.
- Existing `capstone-network-view/2.0`, `capstone-network-diagram/1.0`, `capstone-network-layer/1.0`, and `capstone-network-story/1.0` are bounded projections worth assessing for reuse. The present story is assembled after completion; a real-time model workspace needs additional event/state design.

This is a substantive API, runtime, persistence, and UI change. Capstone has no real external application consumers yet, so internal package, registry, worker, session, and API shapes may be refactored rather than preserved for compatibility. The historical `grid-agent` compatibility stdout boundary is a separate repository contract and remains frozen unless a deliberate retirement decision changes it; it must not constrain the new Capstone application design. Duplicating every change separately in pandapower and PyPSA paths should not become the target architecture.

## Historical framework audit and refactoring stance

**Decided.** Before implementing the new interaction feature, inspect and map the historical framework rather than trusting package names. Refactor where ownership or dependency direction is wrong. Do not treat current `capstone-agent`, `grid-agent`, or `pypsa-agent` package APIs as stable public contracts; Capstone has no actual external application adoption that would justify preserving those accidental boundaries.

The audit currently finds:

- `capstone-agent` owns the current host API, ledger, worker, CLI, application registry, catalog and worker registry, but its generic composition still originates from historical extraction work.
- `grid-agent` owns a frozen pandapower compatibility entry point plus generic application composition, runtime helpers, trajectory and historical analysis modules. The generic pieces are candidates to move into `capstone-agent`/`capstone-harness`; the compatibility surface is a separate frozen concern.
- `pypsa-agent` owns a PyPSA application profile/registry, worker assembly, report shell, case preview, and network projections while depending on `capstone-agent`, Kernel, and PyPSA Domain Packs. It is not a second desired application; its domain-specific pieces should become a PyPSA model capability profile and/or pack-owned projection.
- Existing Domain Packs and Authorities are already closer to the desired names and ownership; they should not be rewrapped as agents.

The audit should produce an ownership/dependency map before plans are written. It should identify code that can move without compatibility shims, code that is explicitly protected by the `grid-agent` legacy contract, and code that should be deleted after its replacement is verified. No historical name is evidence of a required architecture.

## Public Model Capability Profile SPI

**Decided terminology.** `Application Binding` was a misleading proposed name and is superseded by `ModelCapabilityProfile`. A profile is a capability composition compatible with one grid-model implementation family, such as pandapower or PyPSA. It may compose one or more Domain Packs and Authority adapters. It is not a user-facing application, a specific model, or Kernel `DomainBinding`. The user chooses a registered Grid Model; Capstone resolves its implementation family and then presents the eligible profile/package choices. One Model Context v1 activates the user-selected profile set.

**Decided four-concern baseline.** The independent `packages/capstone-model-capability-spi` package owns only descriptor, registry, factory, and exact profile selection contracts. It uses standard-library facilities and has no imports from `capstone-agent`, the Kernel, Domain Packs, Authorities, Pi, DSH, or current tool packages. The core descriptor carries only `profile_id`, `profile_version`, and `spi_version`; it does not claim trust or encode model catalogs, tools, cases, projections, or Authority shapes. The exact spelling of these types and fields remains subject to final specification review.

```text
capstone-model-capability-spi
  ModelCapabilityRegistry
  ModelCapabilityDescriptor
  ModelCapabilityFactory -> ModelCapabilityProfileHandle
  ModelCapabilitySelection(enabled_profiles=((profile_id, profile_version), ...))

capstone-agent
  registered Grid Model -> implementation family + Authority revision
  implementation family -> eligible exact ModelCapabilitySelection(s), user-selected active set in v1
  CapstoneModelCapabilityAdapter(handle) -> current Kernel / future Capstone assembly

capstone-harness
  executes the active Model Context and exposes common Thread/Run/Turn events
```

**Two-layer rationale.** The neutral factory returns a lightweight, closeable profile handle with a descriptor and implementation-private state. A named, trusted `CapstoneModelCapabilityAdapter` in `capstone-agent` converts it to a Capstone application assembly. This separation keeps the public SPI independent of current Kernel `ApplicationProfile`, `DomainBinding`, and `DomainRuntimeProfile`; lets future model families compose different capability shapes; and leaves credentials, Authority admission, evidence, runtime policy, and public projections with the Capstone host and owning Domain Packs. The neutral handle is not itself an executable Kernel profile.

**Trust, version, and Registry lifecycle accepted.** A trusted bootstrap registers source/deployment-approved factories and their trust records, then explicitly seals the Registry. Descriptors do not self-declare trust. After sealing, runtime may resolve and inspect but may not register, replace, or remove profiles. Resolution is exact by `(profile_id, profile_version)`; duplicate registration, descriptor mismatch, unsupported SPI version, or invalid factory fails closed. There is no implicit latest version or version-range selection. Test/development code may create isolated unsealed registries. A future plugin loader remains subject to the trusted deployment manifest.

**Lifetime correction.** Registry entries live from bootstrap to process exit. Each enabled profile handle belongs to one active Model Context within a Prepared Run; a context may hold several handles for the user-selected package set, and a Run may replace or sequence them as the user changes packages or models. A Worker lease belongs to one execution task. Thread and Run identities and events are persistent; they store model/revision and enabled profile identities, never live handles. The Capstone adapter prepares and closes context-scoped resources. A model or package switch must not implicitly carry old tools or evidence into the new effective selection.

**Host selection contract.** The Capstone application configuration records exact approved profiles per model implementation family. The user-facing selector stops at the profile/Domain Pack level; individual tools are implementation details. The catalog owns model identity, implementation family, Authority revision, and optional default package selection for common models; it does not load arbitrary code. Capstone records the enabled profile set in Model Context events. When several profiles are eligible, the application may expose their business labels and let the user enable or disable packages; the model or user text cannot select an arbitrary profile by internal ID.

**Model-to-Profile resolution accepted.** Resolution is deliberately three-layered: the Authority or Grid Model Catalog establishes the registered `model_id`, concrete Authority-owned `model_revision`, implementation family, and model facts; the Capstone Model Capability Catalog supplies user-facing profile metadata, eligibility, exact approved versions, and optional defaults; the neutral SPI registry and trusted adapter prepare the selected profile handles and runtime assembly. Resolution validates exact trusted versions and implementation-family compatibility, then prepares the complete selected set and tool catalog before activation. Profile overlap is not rejected by the resolver. An empty selection may activate an ordinary-conversation Context; a professional Turn without an applicable enabled capability returns a bounded structured prompt. If any selected profile cannot prepare, the new Context is not activated and the previous active Context remains usable.

**Adapter scope.** Each approved profile has a trusted `CapstoneModelCapabilityAdapter` entry point. It validates compatibility and assembles the active model capability context from host-supplied preparation inputs. It does not own Thread persistence, Run/Turn state machines, Worker scheduling, Pi/DSH event normalization, public output, or user instruction parsing.

**Historical audit findings (2026-09-29).** The current tree confirms that the new SPI must not be implemented as a rename of an existing registry:

- `capstone-agent.application_registry.ApplicationRegistry` resolves an `application_id/version` pair directly to a complete Kernel `ApplicationProfile`.
- Kernel `DomainRegistry` resolves `domain_id/version` to a `DomainRuntimeProfile`; Kernel `DomainBinding` already carries tool namespace, credentials, sharing policy, and a complete domain profile. Reusing it as the public Model Capability Profile would lock the new SPI to today's domain composition.
- `capstone_agent.application.build_application` creates a per-profile `DomainRegistry` during preparation. The PyPSA worker and the historical grid application repeat similar profile-to-registry assembly locally.
- `grid-agent` still combines the frozen pandapower compatibility entry point with generic composition and runtime helpers. `pypsa-agent` is a real two-binding application assembly with its own worker and projections. These are migration sources, not target public application boundaries.

The migration implication is to introduce a lightweight binding contract, then provide adapters that turn current complete profiles into bindings. The generic preparation path can be moved behind those adapters after the new contract is tested. It should not promote `DomainBinding` or the existing complete-application registry into the public SPI.

The remaining SPI question is the exact minimum behavior of the returned handle and the host adapter, including lifecycle, version compatibility, and trusted selection. This should be resolved before creating the package skeleton.

## Milestone sketch (proposed, not committed scope)

1. Audit historical packages and dependency/ownership paths; classify movable code, frozen legacy compatibility, and deletable duplication.
2. Define the public Model Capability Profile SPI and the trusted model-to-profile composition model.
3. Define shared Thread/Run/Turn/model and harness event/control contracts, including snapshots and security boundaries.
4. Evolve the Capstone harness facade around existing Kernel/Domain Pack/Authority flow; refactor internal package boundaries without treating current Capstone APIs as stable.
5. Add a Pi runtime adapter and `HarnessPiClient` reference path; keep a `HarnessDSHClient` unavailable shell.
6. Add Capstone Thread API/client, streaming interaction, model switch, Case batch, and event replay.
7. Redesign the App's three-pane workspace and connect conversation, topology, inspector, and evidence to one event stream.
8. Add the Capstone TUI mode on the public client/event contract, unify CLI/SDK/API/Web projections, and verify behavioral parity; later add DSH adapter and multi-Run/multi-model capabilities.

This order will be refined into smaller independently reviewable specs and plans. No code or deployment is authorized by this discussion record alone.

## Questions to resolve next

1. What exactly is the v1 Run lifecycle when a Thread has ongoing dialogue and model switching? Does a Run close only when the Thread is explicitly ended, or can it become terminal earlier?
2. How does the model catalog resolve an implementation family and eligible ModelCapabilityProfile(s)? What exact context transition and evidence isolation apply when switching between models backed by different Authorities within one Run?
3. How much runtime parity should pure Pi/DSH reference modes provide: conversation only, the same bounded tool catalog, or full business comparison with separately admitted results?
4. Which Pi/DSH events need durable replay, which are transient progress, and how are snapshots rebuilt after reconnect?
5. Where do user approvals, cancellation, interruption, and partial tool execution appear in the public control protocol?
6. How should the new App present Thread navigation, Case launch, model switching, and responsive pane transitions? The three-pane concept is decided; exact interaction and visual specification are not.
7. How should the single `capstone` executable expose headless, line-interactive, and TUI modes while keeping `capstone-agent` as the internal application package? `capstone-tui` remains a mode term rather than a package decision.
8. What exact public Model Capability Profile SPI and trust/dependency model should be approved before moving the historical PyPSA and pandapower assemblies?

## Design guardrails

- Keep `Application -> Domain Pack -> Kernel -> registered Authority` ownership intact. Domain Packs admit semantic results; Authorities own numerical truth.
- Expose only published, allowlisted semantic tools. No shell, arbitrary execution, raw models, arbitrary endpoints, or credentials in browser/model-visible state.
- Offline informational answers create no run evidence. Simulator-backed claims cite only current-run admitted results and evidence, bound to the correct model revision.
- Preserve existing CLI compatibility stdout and the generic application output shape.
- Keep App as a presentation client for bounded `/api/v1` projections; preserve local/cloud stage and credential isolation.
