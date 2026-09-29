# Live Session Checkpoint

> Updated: 2026-09-30 00:49 CST. **Session remains active — not a final handoff.** The prior session's baton was recovered from the journal.

## TL;DR

- The local, cloud-development, and user-trial release lanes are documented in `docs/architecture/capstone-development-lifecycle.md` and enforced in `AGENTS.md`.
- Railway `capstone-cloud-dev` API, worker, PostgreSQL, private bucket, and App were deployed and health-checked on one source revision; the user-trial environment remains isolated.
- `main` contains the persisted discussion commits and is four commits ahead of `origin/main`; the worktree is clean. No cloud Provider validation has been claimed because cloud-dev still lacks its independent protected Provider key.
- Active design discussion: `capstone-agent` is the unified agent core for CLI, SDK, API, and Web. Cases and dialogue must share its session, turn, authority, and evidence path; pandapower and PyPSA adapters belong inside it.
- Dialogue v1 uses one run per thread. The design must preserve a later one-thread/many-run upgrade for comparison, reruns, and branches.
- The Thread → Run → ModelContext data model is accepted: Thread keeps the ordered workspace events and current pointers; its v1 Run contains multiple Turns and sequential ModelContexts. Model switch creates a context, while package selection changes only its revision at a Turn boundary. Tool/evidence/replay records bind to the effective context snapshot and `ToolSourceRef` where applicable.
- Run lifecycle is accepted: `created → open → closing → closed`, with `failed` only for unrecoverable Run-level persistence/integrity/security errors. Ordinary Turn/tool/Provider failures leave Run usable; Worker execution states remain separate and cannot close Run or change model/capability selection.
- Turn retry model is accepted: one logical Turn contains immutable Attempts; retry creates a new Attempt, preserves the prior trail, and allows only one Attempt to commit answer/evidence. Each Attempt freezes the Model Context, selection revision, tool catalog, Provider/model, and Harness runtime snapshot.
- ModelContext control operations are accepted: model switches and capability selection changes are first-class ordered Run events, pending during an active Turn, validated before activation, and isolated by Context identity or selection revision.
- Model-to-Profile resolution is accepted as three layers: Authority/Grid Model Catalog owns model facts and revision, Capstone Model Capability Catalog owns eligibility/defaults and user labels, and neutral SPI plus trusted adapter prepares exact selected handles atomically.
- Capstone event/control protocol is accepted: low-level Pi/DSH clients are replaceable runtime adapters, while `capstone-harness` owns the public event Envelope and control commands for CLI/SDK/API/Web; native events remain restricted diagnostics.
- Event persistence is accepted: one Thread-scoped append-only Capstone stream is persisted before publication and drives reconnect, replay, and all App projections; normalized deltas/progress are retained in v1, while native runtime events remain diagnostics.
- Pure Pi/DSH parity is accepted as interaction-only: shared gateway/control/events/replay, empty capability Context by default, no Domain Pack/Authority business facts, and explicit `runtime_mode`/`authority_mode` markers.
- Reference context isolation is accepted: mode markers are immutable per Attempt; Pi/DSH output stays non-authoritative history and is excluded from Capstone memory/evidence unless explicitly quoted as unverified text; returning to Capstone restores the prior ModelContext.
- Pi and DSH are replaceable pure harness runtimes from Thread's perspective; `HarnessPiClient` and an empty `HarnessDSHClient` remain comparison paths. `capstone-harness` may consume their events, normalize and enrich them, then serve CLI/SDK/API/Web projections; Thread is only one consumer.
- A case is a reusable multi-turn instruction batch, not Thread state. A Thread is centered on a current grid model, supports ordinary and model-focused professional dialogue, and can switch that model; v1 has one current model at a time, with multi-model context deferred.
- Thread v1 defaults to the registered IEEE-39 grid model. The Authority/catalog resolves and pins the concrete model revision at Thread creation and binds it to subsequent result/evidence events.
- Thread creation now resolves and pins the exact IEEE-39 model revision and implementation family; Profile handles, Provider sessions, and tool catalog are prepared lazily before first execution. Failed revision resolution rejects creation; later preparation failure preserves the Thread for retry.
- Users select registered Grid Models, not internal capability profiles. The model catalog resolves implementation family plus Authority revision, then Capstone resolves a compatible `ModelCapabilityProfile`. One Thread/Run may switch between pandapower-backed and PyPSA-backed models; each switch starts a new Model Context with isolated tools and evidence.
- A model implementation may expose multiple candidate `ModelCapabilityProfile` entries. Users enable or disable packages at the Profile/Domain Pack boundary, and a Model Context may hold several selected packages. Individual tool switches are unnecessary; semantic overlap is diagnosed by professionals during use. Model defaults may provide a common package set, and selection revisions apply at Turn boundaries.
- Tool provenance is mandatory in public activity/evidence projections: tool identity/name, source profile/version, Domain Pack/version when available, implementation family, model context, and selection revision must be visible for troubleshooting.
- The common provenance structure is named `ToolSourceRef` and is attached to every tool lifecycle event and admitted result/evidence reference.
- User-facing labels, descriptions, eligible profiles, and default package combinations belong to the Capstone Model Capability Catalog; Authorities retain model/revision truth.
- Empty capability context is a valid baseline: Capstone supports ordinary conversation and capability discovery without tools, while professional claims/evidence require an enabled package; pure Pi/DSH uses it for no-domain-tool runtime/event comparison.
- Capability selection controls are accepted: structured enable/disable/replace commands, pending changes during an active Turn, next-Turn effect, durable selection revisions, empty selection allowed for ordinary conversation, and bounded rejection of professional analysis without an enabled applicable package.
- The existing App middle column is a redesign target: replace the case-result panel with a Thread-driven current-grid workspace. Chat, model projection, case batches, and evidence replay must consume one event source; the model area is a peer projection of the Thread, not a case-owned widget.
- The existing three-column App layout is temporary until a scenario-driven UI design is completed. The earlier left Thread / center model / right context arrangement is only a candidate hypothesis and does not constrain the new design.
- Historical replay uses a client-local read-only cursor; it changes displayed projections without changing Thread/Run state or rerunning work.
- Public read models are unified: typed `ThreadSnapshot` and `EventPage` serve SDK, API, Web, CLI, and TUI; clients only transform presentation.
- Control commands are unified: command ID, idempotency key, expected sequence/state version, accepted/rejected receipt, and asynchronous terminal events apply consistently to submit, retry, cancel, context changes, and Run close.
- Approval/cancellation/partial-output semantics are accepted: approval IDs are bounded and expiring; cancellation sets an admission cutoff; pre-cutoff admitted results remain historical; partial output is diagnostic unless a Domain Pack explicitly admits a typed partial result.
- Event classification is accepted: state events rebuild snapshots, interaction events support streaming/replay, diagnostic events stay separately controlled, and verified snapshot replay uses explicit schema upcasters with fail-closed integrity checks.
- Event schema/retention is accepted: explicit versions/upcasters, long-lived protected business/replay events, restricted TTL-bound raw diagnostics, pre-persistence filtering, and no deletion of protected canonical events during compaction.
- ModelContext resource lifecycle is accepted: `declared → preparing → active → retiring → closed`, atomic activation, idempotent close, persistent identities only, and Worker leases that borrow resources per Attempt.
- Strict recovery is accepted: no best-effort continuation. Lost lease/session/event continuity makes an Attempt `interrupted`; v1 restarts cleanly in a new Attempt, with fencing against stale Workers. Perfect resume requires a future verified durable checkpoint.
- Runtime session scope is accepted: Pi/DSH semantic session state belongs to one Attempt; cross-Turn continuity is rebuilt from durable Capstone state, and stale Attempt lease tokens cannot publish events.
- Worker lease recovery is accepted: lease loss interrupts the Attempt, advances fencing, rejects stale writes, and never silently retries in v1. Explicit retry creates a new Attempt/session with a durable relation.
- Tool operation safety is accepted: calls carry operation identity and idempotency; unknown/non-idempotent calls are not automatically resent, and admission deduplicates operation plus payload hash.
- Error projection is accepted: stable classes, retryability, related IDs, last safe sequence, and action hints are shared across clients; raw diagnostics remain restricted and Run failure stays limited to integrity/security/persistence scope.
- Intent routing is advisory: `TurnPlan` classification never grants permission; tool allowlisting, admission, and claim binding are hard gates, with observable re-planning and bounded `capability_required` responses.
- TurnPlan is accepted as a minimal auditable contract: route, bounded confidence, capability hints, Context snapshot, source, and revision; hidden classifier reasoning is excluded.
- Jev is accepted as an optional experimental `TurnRouter`: deployment default off, Run-snapshotted mode/model/schema, active before main LLM, shadow asynchronous, server-side redacted input, and explicit safe fallback.
- Jev fallback and payload boundaries are accepted: shadow failure is diagnostic; active failure returns typed `DecisionUnavailable`; explicit ordinary/professional routes remain bounded by hard gates; unspecified mode asks for clarification or deterministic policy; slow LLM fallback is opt-in. `JevPayloadBuilder` is the only request path and sends bounded summaries after redaction/schema validation, never raw networks, tool/evidence payloads, secrets, paths, transcripts, or hidden reasoning.
- Jev evaluation timing is accepted: demo development uses FakeDecisionRouter/fixtures without keys or datasets; optional experiments collect metadata; broad active/default use requires later labeled evaluation.
- TurnRouter interface is accepted: capstone-harness owns an async sanitized-input/typed-decision contract shared by Fake, heuristic, Jev, and LLM comparison implementations; routers only produce auditable TurnPlan decisions.
- Event access is accepted: `read_events` is the durable recovery/replay foundation; `subscribe_events` is optional low-latency delivery and must repair duplicates or gaps through the same `event_seq` read contract.
- Cursor resynchronization is accepted: unavailable or unverifiable cursors return `resync_required` with a verified snapshot and `base_event_seq`; clients rebuild and continue without silently skipping events.
- Reasoning visibility is accepted: every long operation streams bounded progress/status by default; optional `trace_level=detailed` adds redacted explanation summaries, while raw hidden reasoning never enters the public stream. Attempt snapshots freeze the setting until the next Turn.
- Web runtime boundary is accepted: production Web uses assistant-ui plus a Capstone-owned `CapstoneThreadClient`; `@assistant-ui/react-pi` remains a Pi comparison adapter, and browsers never connect directly to Pi/DSH clients or native runtime channels.
- Web transport staging is accepted: v1 uses HTTP JSON plus SSE and cursor recovery; advanced WebSocket support is reserved for human-in-the-loop steering, high-frequency/voice/multimodal interaction, collaboration, or interactive simulation.
- Capstone CLI modes are accepted: the single `capstone` executable defaults to TUI, with explicit `tui`, `chat`, and headless `run` modes sharing the Harness protocol; `grid-agent` compatibility commands remain separate.
- TUI framework staging is accepted: v1 uses Textual Python in `capstone-agent`; Ink/Ratatui/Bubble Tea remain external-client options behind `capstone serve`, including a future single-file client restricted to HTTP JSON + SSE and public recovery/auth contracts.
- Headless output is accepted: `capstone run` emits one final JSON by default, `--events` emits canonical JSONL events, diagnostics stay on stderr, and `grid-agent` compatibility output remains frozen separately.
- TUI projection state is accepted: Textual uses a single `ThreadProjectionStore` for shared snapshots/events/cursors/receipts; widgets render and dispatch commands without owning business state.
- TUI workspace/pages are accepted: two columns with grid left and conversation right, hideable context drawers, an immediate default IEEE-39 page with explicit projection status, exactly one stable Thread-local page per distinct Grid Model, and an independent `active_grid_page_id` that reuses an existing model page without duplication or reordering; concurrent v1 execution remains disabled.
- TUI grid rendering is accepted: Ghostty/iTerm2 prefer Kitty/TGP images from the bounded grid projection, with Unicode/ANSI fallback; image placement remains presentation-only.
- TUI rendering now also has a presentation-only capability policy: startup probe, runtime fallback to Unicode/ANSI, and local image cache keyed by projection/viewport/renderer identity.
- Run termination is accepted: only explicit `close_run` normally terminates the Run; it drains active work, and a closed v1 Thread becomes read-only. Ordinary Turn/model/Context failures leave the Run usable; future multi-Run support can add a new Run under the same Thread.
- The complete discussion is recorded in `docs/superpowers/specs/2026-09-29-agent-interaction-discussion.md`, with explicit Decided / Proposed / Open sections. It is a discussion record, not yet an approved implementation spec.
- Recent proposals add Harness-owned control resolution (`ControlIntent → CommandFactory → CommandExecutor`), visible control Turns without mandatory runtime Attempts, versioned Case batching with pinned Context and blocked-step recovery, and a capability-parity Pi reference mode alongside the empty-capability baseline.
- Six implementation milestones are proposed: public contract/Harness skeleton, single-Run core, model and capability integration, CLI/TUI, Web/Case, then reference and advanced runtime work. No implementation has started from this discussion yet.
- Web, Textual TUI, and headless CLI UI/UX are now specified in `docs/superpowers/specs/2026-09-30-capstone-ui-ux-design.md`; the shared dark operations design system is persisted in `design-system/capstone-agent/MASTER.md`.
- UI/UX is NOT READY for implementation planning. Earlier completion/PASS claims are withdrawn in `docs/superpowers/specs/2026-09-30-capstone-ui-ux-deep-review.md`. Existing App visual strengths and structural gaps are recorded; wireframes and the shared state fixture contract are complete. `capstone-thread/1` read-model types, four canonical fixture documents, the projection-only Web/TUI/CLI action runner, browser protocol parser, transport-facing Thread client, projection store, and fixture transport now exist and pass the relevant suites. The visual MASTER remains a product token draft. Next build the fixture-backed Web/TUI prototype; do not replace the legacy Case App until the new route is verified.
- `grid-agent` application growth is frozen. It remains a pandapower compatibility adapter; new CLI/TUI and agent interaction work goes through the unified Capstone application/harness. `capstone-tui` is shorthand for the unified CLI's TUI mode, not a new package or application. `capstone-agent`, `pandapower-agent`, and `pypsa-agent` are historical peer-agent names to converge behind one Capstone application.
- `Capstone` is the public brand and default executable name. `capstone-agent` is the canonical internal name for the intelligent-agent application layer; `capstone-application` is rejected as verbose and conceptually conflicting with `capstone-app`.
- Historical domain-agent names need asymmetric refactoring: no separate `pandapower-agent` distribution exists; `grid-agent` contains much of its legacy application/compatibility code, while `pypsa-agent` is a real PyPSA assembly package. Candidate target is Capstone-owned model-family capability profiles or isolated profile distributions, with Domain Packs and Authorities retaining their current semantic names.
- Capstone has no real external application consumers, so internal historical APIs and package boundaries may be refactored freely; only the separately frozen `grid-agent` compatibility envelope remains constrained. A public, versioned, trusted Model Capability Profile SPI is required before moving the historical assemblies, because many future grid-computing tools will be composed under one Capstone application.
- The initial `capstone-model-capability-spi` must stay lightweight and implementation-agnostic: identity/version/registration/resolution/trust plus exact selection. It must not make current pandapower/PyPSA model, Case, Authority, network projection, or tool catalog shapes mandatory.
- The approved first SPI baseline is four concerns only: descriptor, registry, factory, and application-profile selection. Optional contribution protocols wait until the historical audit proves a concrete need.
- The SPI package boundary is accepted: create an independent `packages/capstone-model-capability-spi` distribution with no Capstone host, Kernel, Domain Pack, Authority, Pi, DSH, or current-tool imports. `capstone-agent` will populate the trusted registry and host migration adapters.
- The two-layer rule is accepted: the neutral SPI factory returns a `ModelCapabilityProfileHandle`; a named `CapstoneModelCapabilityAdapter` in `capstone-agent` translates it into Kernel or future Capstone application assembly. The rationale prevents confusing a profile handle with a Domain Pack or executable Kernel profile.
- Version/trust rules are accepted: descriptor fields are limited to `profile_id`, `profile_version`, and `spi_version`; trust belongs to closed Registry registration; first resolution is exact and deterministic with no latest/range selection.
- Registry lifecycle is accepted: trusted bootstrap registers and explicitly seals it; production runtime resolves read-only after sealing; host application configuration and model catalog select exact profile identities; only isolated test/development registries may remain unsealed.
- Capability lifetimes are accepted: registration is process-scoped, the profile handle is per active Model Context within a Prepared Run, Worker lease is per task, and Thread/Run state is persistent. A Run may sequence profiles as models change; persistent events store model/revision/profile identities.
- `CapstoneModelCapabilityAdapter` is accepted as the trusted per-profile assembly entry point. It validates compatibility and returns current/future Capstone application assembly; Thread, Run/Turn, Worker, Pi/DSH events, and public output stay above it.
- Adapter output is accepted as a prepared profile-scoped capability contribution: bounded tools, execution/admission bindings, and optional projections are composed by Harness; Kernel ApplicationProfile remains migration-internal.
- Historical audit confirms the existing `ApplicationRegistry` resolves complete Kernel `ApplicationProfile` objects, while `DomainRegistry` and `DomainBinding` already encode today's domain/tool details. The new profile SPI must be independent and use adapters during migration; it must not rename either existing registry or promote `DomainBinding`.

## Where things stand

- Recent durable commits: `7b6738d` (Jev fallback and payload boundary), `36cec9f` (journal entry), `38f22fa` (TurnRouter contract), `56b13ea` (Jev evaluation timing).
- Documentation gates passed: `make doctor`, link checks, `git diff --check`, and the `CLAUDE.md` symlink check.
- Cloud-dev API `/health/ready` and App `/health` returned `200`.
- Project route is `direct`; the canonical optimization worklist remains `docs/superpowers/plans/2026-09-05-capstone-optimization.md`. The active design has not yet been approved or implemented.

## Immediate next steps

1. Define the Capstone harness event/control SPI and projections for CLI, SDK, API, and Web; keep Pi/DSH native events available for runtime comparison without bypassing Authority admission.
2. Decide the remaining open interaction and UI questions, then approve the discussion record before implementation planning.
3. After approval, write and review the implementation specification before invoking the planning workflow.
4. Cloud Provider validation remains separate and needs its own authorization and protected cloud-dev key.

## Ruled-out paths

- Do not share cloud-dev and user-trial databases, buckets, credentials, origins, or mutable run data.
- Do not promote ordinary development pushes directly to user-trial.
- Do not use an old Compose image as evidence for current source.
- Do not claim cloud Provider validation without the separate cloud-dev key.

## Ready-to-paste checks

```sh
git status --short --branch
make capstone-local-rebuild
make doctor
curl -fsS https://capstone-api-production-bb72.up.railway.app/health/ready
curl -fsS https://capstone-app-production-83ef.up.railway.app/health
```
