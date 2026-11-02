# Capstone Agent Framework

## Incremental task organization candidate

2026-10-30 decision: the default lightweight loop uses the direct model runtime.
The request and text-analysis pools remain opt-in experiments, disabled unless
the backend sets `CAPSTONE_EXPERIMENTAL_LLM_POOL=1`. They do not establish a
performance benefit. Tool concurrency, artifact streaming and model timing do
not depend on these pools. The question-led enterprise research mode is an
accepted design, not an implemented release; see the
[discussion record](../superpowers/specs/2026-10-30-enterprise-data-research-analysis.md).

The lightweight instruction-local model request pool is invocation scheduling,
not a second research task ledger or DR mode. Main and admitted text-analysis
sessions share a finite request queue. Same-context requests wait for their
predecessor to return; independent contexts may run within the selected limit.
Queue admission grants no tools, sources, model endpoints or Authority evidence.
Cancellation retains reservations until actual provider cleanup is confirmed.
Public queue/start/return events distinguish waiting from model execution.
See the [asynchronous execution design](../superpowers/specs/2026-10-29-lightweight-async-execution-design.md).

Research-turn clarification (2026-10-23): each instruction advances a continuing
conversation. The user judges analytical adequacy; internal assessment records
actual support and limitations. Imperfect analysis can be delivered as explicitly
limited results and revised in later turns. It must not trigger automatic whole-task
repetition. Permissions, source/version identity, file safety, required persistence
and Authority evidence remain enforced. App1.18/Pack1.15/shared policy1.5 is a local
candidate for this rule; real two-turn and full performance acceptance are pending.

The accepted organization model separates planning/acceptance from execution.
Every executable task has an independent context and explicit selected inputs and
returns. The engine submits the next evidence-supported task or batch, accepts
actual results and decides the next work or whole-goal completion. An empty pool
is not completion. The existing graph ledger and scheduler own the task pool.
See the [incremental design](../superpowers/specs/2026-10-22-incremental-task-pool-design.md)
and [verification](../reviews/2026-10-22-incremental-task-pool.md).
The local Application1.14/Pack1.12 candidate passed a small real protocol check;
full report, parallel performance and other application adapters are not accepted.
Separate model contexts do not establish per-node OS filesystem isolation.

2026-10-22当前校准：规划策略属于共享执行层，应用/Pack仅适配授权能力、来源、领域约束与交付。App1.13/Pack1.11先验证研究入口，电网/复杂聊天未接通。原始请求235939三路并行64.165秒，但218.375秒按failure收口、无报告，不通过146秒（145.914727秒）基线。步骤号和标题行计量已修订，282项App检查/类型通过；独立复审未完成，无Git/cloud/demo变更。以ROOT最新RESUME和编排修复记录为恢复入口，不继续采用旧263.896秒口径。

## Enterprise execution design track

The [v1 design baseline](../superpowers/specs/2026-10-15-enterprise-design-final.md)
preserves the working Thread service, worker, research controller, evidence storage,
professional runtimes and views. It generalizes their model-bound seams into one
autonomous organization mechanism. It does not create a parallel command/event ledger
or keep separate general and professional orchestration as the final architecture.
Runtime integration and acceptance remain implementation gates.
Demo1 and Demo2 are examples, not applications required by this track. The agent
accepts versioned, authorized resources with their native contracts. Business
metrics stay in external resources or the owning professional Pack. View types
are extensible, and new example-specific solver capabilities are separate work.
See the [boundary review](../reviews/2026-10-16-enterprise-scenario-boundary-review.md).

The accepted conceptual direction uses ApplicationProfile as the application-owned,
versioned business capability group and enablement unit. A profile composes Domain
Bindings; each binding selects a Domain Pack. One Capstone task can organize
capabilities from multiple enabled profiles under explicit application grants.
ApplicationProfile remains within the Application ownership layer.

The [enterprise execution design](../superpowers/specs/2026-10-15-pi-enterprise-execution-design.md)
defines the proposed workspace configuration, task snapshots, Pi-native execution,
cross-profile cooperation and frontend contract. These are target contracts, not
implemented guarantees. The runtime descriptions below retain their current scope,
including model-bound profile selection and isolated general Pi execution.

## Standalone intent routing after rollback

The current local recovery candidate restores pre-closure business execution.
An application-owned, tool-free LLM selects ordinary or professional before the
existing execution chain. It does not compile business requirements, rewrite the
request, certify goal coverage or replace the final answer. Recognition can use
its separately configured Provider/model. A failed classifier stops the attempt
with a routing diagnostic; hosted applications do not use keyword fallback.
The experimental closure design remains historical, not current runtime behavior.

After the user-directed rollback, three existing fixes are selectively restored:
the compact activity window, isolated ordinary knowledge answers and final-message
collection. Ordinary answers have no business extension/catalog/Authority handle;
they use the configured lightweight role with thinking off. Process deltas remain
diagnostic and cannot become the formal answer. Task compilation, coverage and
model prewarm remain withdrawn. Model information requests still use the professional
chain; no speed or calculation-free claim is made for that path.

Capstone assembles evidence-backed agent applications over authoritative
business-domain systems. It is the composition boundary between a reader-facing
application, a domain's semantic capabilities, and the registered system that
can actually calculate or retrieve the domain facts.

## Purpose and non-goals

The framework lets a model compose a bounded catalog of semantic capabilities
without making the model, the Kernel, or an application the source of truth.
An authority produces source-backed or deterministic results and admits the
evidence that supports them; the application then presents only claims that its
current run can support.

Capstone is not an LLM shell, a generic REST client, a route around a domain's
access controls, or a generic replacement for an authoritative system. It does
not expose shell access, arbitrary subprocesses, arbitrary code execution,
generic filesystem access, raw business objects, credentials, arbitrary network
endpoints, or undeclared capability aliases to a professional Domain Pack session. The framework also
does not make a domain-specific output envelope a Kernel requirement.

### General Pi task delegation

The continuing-conversation development path retains one Thread/Work while its
instructions use direct answers, authorized native work and explicitly selected
registered models. A stopped instruction remains history and may be retried
explicitly. A new conversation instruction supersedes its old pending input;
the framework must not concatenate the stopped request into new executable work.
Terminal history retains its status and identity in model context. A retained
Work goal is background; it does not silently add obligations to a new turn.
The conversation has no session-wide "current business goal". A goal belongs
to a concrete organized task or its admitted plan, not to every message in the
Thread. Ordinary answers and temporary tool instructions need no business-goal
banner. Later instructions may continue or adjust a referenced task; the retained
Work storage anchor is not an implicit instruction to resume it.
Resource scope also belongs to each instruction. An upload or an open grid is
a contextual cue for the next instruction, not a permanent conversation target.
An explicit file or grid reference takes precedence. A clear continuation may
reuse the referenced task's resources and accepted results. An unrelated new
instruction starts its own scope. When several plausible targets would change
the result, ask a short clarification rather than silently choose one. Stopping
a task preserves its history and resources; it does not authorize its execution
under the next instruction.
Historical user and assistant messages retain their source roles and original
text inside a read-only reference packet. They are not replayed as the new
executor's own assistant trajectory. Only this task's live messages form that
trajectory. Historical instructions, status and factual claims do not
establish current execution or live environment facts. Research summaries carry
an immutable attempt/turn identity and an explicit research-bookkeeping scope,
including in compact recovery windows. An idle research cycle describes that
controller only; it is not an observation of operating-system processes or other
attempts. A new accepted instruction is fresh authorization within existing
grants even when it repeats a terminal request.
The native execution host supplies a separate current-task status snapshot with
its native task ID, parent Attempt ID, capture time and bounded scope. It does
not claim to enumerate other tasks or operating-system processes. Missing
observations are unknown, not zero. Research-cycle status cannot replace this
host execution snapshot; neither snapshot grants new tools or Authority access.
For continuing native tasks, retained research memory is read on demand while
the current research controller is unstarted. Automatic research context begins
only after the current controller has accepted organization or execution state.
The request guard verifies that an idle context has not become active between
context preparation and the model request. Existing research state is preserved;
neither a fresh instruction nor an idle view silently clears it.
Process emphasis follows actual execution: initial thinking, direct tool calls,
or admitted task organization. Task organization selects task steps regardless
of uploaded resources. Host lifecycle timing and unadmitted graph text do not
establish task planning or completed analysis.

Systematic diagnosis is an application-owned native foundation capability with
an on-demand method guide and host-persisted reported records. Ordinary use is
a single report of the issue, observed outcome and next action; manual IDs,
hashes and probe reservation are not required. Scoped correction and repetition
budgets permit useful independent work and limited delivery. Known field errors
receive bounded correction guidance; unknown required persistence remains fatal.
Diagnostic records cannot grant tools, certify their own findings or become
Authority evidence. Research quality findings remain advisory gaps; professional
calculations retain their Pack and Authority contracts. See the
[design](../superpowers/specs/2026-10-25-unified-conversation-diagnostics-design.md)
and [acceptance record](../reviews/2026-10-25-unified-conversation-diagnostics.md)
for the implemented scope and verification limits. These local development changes
do not establish cloud or user-trial deployment.

The application can delegate general goals to a separate native Pi executor.
Capstone mode first uses a model-based intent node to select goals and dependencies.
Business goals retain the Domain Pack and Authority path. General goals use the
isolated executor. Direct Pi mode uses a separate semantic context selector, then
the same executor, managed configuration and native tools. It does not prepare a
professional plan or Domain Pack tools. Both modes retain the visible Thread
history and current model selection. Selection failures remain retryable; there
is no keyword fallback.

The general executor owns private task workspaces and native read/write/edit/bash
execution. It cannot access business host directories, Authority endpoints or
host credentials. The application can provide authorized public material copies
in a protected task input area. Provider access uses a revocable relay grant. Pi discovers
managed settings, context files, skills and extensions through its native conventions;
the application supplies bounded conversation, dependency observations and public
business context. The present model projection supplies identity, public version
and history, not full model tables. A sample network bundled with a skill does
not stand for the selected business model.

New typed requests cross `capstone-pi-task/2`; text-only legacy `/1` recovery is
retained. Results use `capstone-pi-task-result/1`.
Host-issued sources identify observed tool output; they do not prove that a web
document is correct. Saved work products have bounded, hash-checked bytes.
Native results admit neither Authority results nor simulator evidence. Public
object versions in the separate checked context are bound by the host.
Typed external observations may supplement a business goal; changing a business
model still requires an explicit Domain Pack contract and authority admission.
Accepted recognition decisions, executor identity and child task identity are fixed
for retry. An unknown prior execution outcome must not trigger blind side-effect replay.

### Shared business context and role resources

The application owns `capstone-business-context/1`: an immutable Thread snapshot,
per-goal object and material selection, explicit exclusions, public outcomes and
coverage. Public projections keep source identity and version. Historical results
need new current-run admission before professional reuse. Domain Packs own domain
projection semantics; the Kernel owns no grid-specific mapping. Context grants
data access within the task; it does not publish tools.

Three execution roles have distinct resource profiles: `harness_engine`,
`delegated_pi` and `direct_pi`. The last two are execution identities under the
existing Capstone/Pi modes. Checked-in native settings and
the separately planned `agent-resources.json` configuration select fixed
sources and role adapters. Managed installation, actual SDK loading and exact
tool schema checks must succeed before a resource is ready. Accepted profile
revisions and protected installations persist for retry; revocation or missing
bytes fail explicitly. New tasks use the new configuration.

Native Pi loads the pinned PowerSkills pandapower skill and ten bounded PowerMCP
tools through the managed MCP extension. Harness uses an original Domain Pack
adapter guide and the Authority-owned `analysis.run` operation
`diagnostic.structural`. The Authority exports its current model snapshot and
invokes PowerMCP `load_network` and `audit_network`; exact contracts, frozen
revision, result persistence and evidence admission enforce the boundary. Prompt
text alone does not enforce it. Raw upstream skills and MCP tools require role
adaptation; installation alone does not make them professionally compatible.

The App selects `/skills`, typed `/skill:<name> <task>` and `/context` from the
server's bounded input catalog. UI actions create no model request. Ordinary text,
including unknown slash text, cannot expand into a native command. Submission
binds role, resource revision, original input and context choices atomically.
The default federated conversation has no assembled Case execution service;
its Case operation is unavailable. The independent Case module and `/old`
compatibility entry remain separate contracts.

## Four layers and dependency direction

The four layers have distinct ownership:

```text
Application -> Domain Pack -> Kernel -> registered Authority
```

Dependencies only flow rightward. Result and evidence references return through
explicit contracts; they are not reverse imports, raw-object escape hatches, or
an invitation for an outer layer to recreate authority facts.

| Layer | Owns | Must not own |
| --- | --- | --- |
| Application | Application selection, public CLI or UI, provider setup, reader-facing rendering, and compatibility projection | Domain semantics, raw authority objects, credentials in model-visible state, or a mandatory Kernel schema for its public interface |
| Domain Pack | Domain contracts, policy, guides, provisioning, executor, projectors, domain state, output contract, and current-run authority adapter | Kernel internals, another domain's state, or the authority's raw implementation |
| Kernel | Neutral composition, tool and guide materialization, bounded context, turns, trajectories, artifacts, replay, audits, and framework-owned `core` lifecycle output | Domain capability semantics, pandapower objects, domain credential logic, or a product-specific answer schema |
| Registered Authority | Registered domain access, deterministic calculations or source-backed retrieval, revisions, result datasets, and evidence | Model planning, application presentation, or unbounded caller-selected execution |

An application declares an `ApplicationProfile`; `AgentApplication` owns the
run lifecycle; each `DomainBinding` injects a selected Domain Pack's public
contracts. A binding names its domain payload and tool namespace, keeps
credentials scoped, and denies cross-domain data sharing. Domain Packs
communicate with an authority through their declared executor/protocol instead
of importing its implementation into the Kernel.

Profile preparation now distinguishes authority and native configurations.
`DomainRuntimeProfile` retains the professional authority contracts.
`NativeDomainRuntimeProfile` declares a `PackManifest`, resource profile,
result contract, policy and guides without a model or substitute authority.
The same `ApplicationProfile`, `DomainBinding` and `DomainRegistry` select both.
`prepare_application(required_binding_ids=...)` prepares only the requested
bindings while retaining the full profile and its reference grants. An empty
selection starts no resources. Unknown bindings fail before credential issuance.

Native preparation uses an application-supplied `NativeBindingPreparer` and
returns an immutable `NativePreparationReceipt`. Capstone's Pi adapter checks
the registered executor's published resource profile and load receipt. It does
not interpret business metrics or execute a model during preparation. Native
observations remain distinct from authority results. The current authority
runner rejects selected native bindings before starting resources; native
continuous execution and model-free Thread integration remain planned work.

### Imports, calls, and evidence are different relationships

The layer ordering above constrains ownership and dependencies; it does not
require an import through every adjacent layer. The implemented source imports
are:

```text
Application -> Kernel public application API
Application -> selected Domain Pack public factory
Domain Pack -> Kernel public SPI
Domain Pack -> explicitly allowlisted Authority protocol/resource API
```

The Kernel has no import of a concrete registered authority. In the pandapower
pack, the sole simulator import permitted by the static boundary gate is
`from grid_simulator.capabilities import contract_root` (an alias is allowed).
This public installed-resource function locates the directory containing the
authority-owned capability JSON; it does not admit registry classes, simulator implementation modules,
raw networks, or arbitrary simulator calls. The pack retains an exact simulator
package dependency, declared in its `pyproject.toml`, so resource availability
is checked in clean wheel installation. The schema is not copied into a new
independently maintained contracts package. The AST check enforces declared
source imports; it is not a sandbox for malicious dynamic Python code.

Runtime calls use injected interfaces, not reverse implementation imports:

```text
Application -> Kernel lifecycle -> injected Domain executor -> Authority
```

Evidence returns through validated contracts, in the opposite data direction:

```text
Authority -> Domain admission/projector -> Kernel typed state/commits -> Application
```

Returning a reference does not expose an authority object or let the Kernel
recompute a domain fact. The Domain Pack still owns semantic admission, and
the application still owns its public compatibility projection.

## Runtime and tool protocol

At startup, the selected Domain Pack provisions a trusted endpoint for the
current workspace, materializes its published contracts, policy and guide index,
builds an allowlisted tool catalog, and creates an authority scoped to the
current run. The generic model transport turns an allowed tool invocation into
the Domain Pack's bounded protocol request; the executor sends it only to that
prepared endpoint. Tool input cannot choose a command, endpoint, protocol,
authority, or credential.

The model receives the current question, bounded framework context, the domain
policy and guides, and exact schemas for the registered semantic tools. It may
decide which of those tools to call and return reader-facing prose. It does not
validate itself: the controller validates typed calls, the authority produces
facts, and projectors accept only authority-admitted results into domain state.
The controller then binds the turn's consumed and produced result/evidence
references before committing the answer.

This separation makes tool exposure a two-party publication decision. A
capability must be declared by the Domain Pack and executable by its registered
authority. Documentation alone never registers a model tool, and an
implementation that is not published by the selected profile is not exposed.

## Composite output protocol

Explicit multi-binding assembly is supported: an `ApplicationProfile` selects
all bindings up front, each invocation carries its controller-owned binding
identity, and the runtime publishes each domain's catalog and guides alongside
one shared `agent_` core tool set. Runtime descriptor `capability-agent-runtime/1.1`
supports multiple bindings; the single-binding `1.0` format remains supported.
Each binding retains its own workspace, credential scope, authority, state,
claim admission and output. A claim cannot mix references owned by different
bindings. Multi-binding admission records the individual binding decisions.

Selecting two packs does not authorize either pack to consume the other's
state, result, evidence or model. A trusted application may declare a
`ReferenceGrant` for one opaque reference kind, source, target, purpose and
capability family. The handoff service verifies the source revision, records a
replayable receipt, and asks the target authority to admit it before the
target capability runs. Other cross-binding sharing remains denied.

The hosted Thread adapter prepares the same application-granted handoffs for
its bound model and verified descendants. Its Pi descriptor names the private
handoff index; the transport supplies a receipt only to the granted target
capability family. Answer admission uses the Packs that participated in the
current Turn. An unused selected Pack does not downgrade another Pack's verified
result. Published guide reads carry no authority references; they do not replace
calculation evidence or grant cross-domain access.

The generic application result is composed from independently validated Kernel
and Domain Pack contracts. Its generic shape is exactly:

```json
{"schema":"capability-agent-output/1.0","core":{},"domains":{"<binding_id>":{}}}
```

`core` is Kernel-owned and records the framework run lifecycle, references,
audits, and diagnostic metadata. Each `domains.<binding_id>` object is built
and validated by that binding's Domain Pack; it contains the domain-specific
status and business payload. A domain may add only its own namespaced payload;
it cannot redefine `core` or make its payload appear to be a framework result.

An application may render or project this composite result into a versioned
public interface. That is a vertical compatibility adapter owned by the
application, not by the Kernel. In particular, the grid compatibility adapter
owns the historical two-field `question_id` / `answer_output` projection. The
Kernel neither owns nor requires that grid envelope for another application.

## Current-run evidence protocol

Offline informational answers create no simulator or authority evidence.
Answer assurance is an advisory evaluation, separate from application execution.
It cannot replace or prefix the model's answer, downgrade a successfully committed
turn, change completion counts, or abort subsequent questions. Evaluation errors
produce an `answer_evaluation_unavailable` note with `limited` assurance.
Provider/runner failures preventing answer
submission, protocol errors, reference-integrity errors and commit failures
still fail the run. A typed domain-tool failure can be represented by a
committed limited answer and continue. `core.status=completed` means processing
finished, not that all answers are verified. Successfully committed turns have
`status=success`; assurance appears separately in the report's numbered evidence
evaluation appendix, never in its unsuccessful count.
For a successful current-turn read of a published guide, a Domain Pack may
preserve model-written informational text with `guide_access_verified`.
This verifies access to the published source, not answer semantics or numerical
claims; it cannot stand in for a failed authority call.
Successful stateless capabilities whose published contracts require no evidence
do not block that guide path (for example, operation discovery and parameter
schemas); failed calls or missing declarations do not receive this exemption.
The Kernel passes turn- and binding-scoped guide receipts to admission, without question matching
or domain interpretation. This assurance uses answer-admission sidecar1.1;
existing assurance modes retain1.0 and the reader accepts both versions.
Simulator- or authority-backed answers persist result and evidence artifacts
under the current run, conventionally `runs/<run_id>/`, and only references
admitted for that run may support final factual claims. A result reference
identifies a returned authority result; evidence references identify the
supporting current-run artifacts. The answer commit, report, and replay record
their lineage rather than trusting prose alone.

The current-run authority verifies the applicable result/evidence relationship
and rejects references outside the run or references it cannot admit. A
projected state, a cached display, a fixture, or an evidence-inspection tool is
not a substitute for the primary result contract. Replay and reporting can
diagnose a run, but do not create facts or make an otherwise invalid evidence
chain valid.

## Integrating a new application

An application integration is an explicit assembly, not dynamic discovery:

1. Define the authoritative system boundary and a reusable, versioned semantic
   capability protocol. Decide which facts, revisions, result references, and
   evidence the authority can return.
2. Implement a Domain Pack using the public Kernel SPI: published contracts,
   policy, guides, trusted endpoint provisioner, executor, current-run
   authority adapter, projectors, state adapter, output contract, and
   acceptance profile.
3. Define an `ApplicationProfile` and `DomainBinding` that select the pack,
   namespace its tools and output, scope credentials, and declare its public
   output renderer or compatibility adapter.
4. Materialize the runtime from that profile. Verify that only published,
   executable semantic tools and digest-bound guides reach the model.
5. Prove provider-free acceptance with real authority calls, current-run
   evidence lineage, answer audits, report creation, and replay. Run separate
   authorized authority/provider checks where credentials and billing permit.

The application must keep provider credentials outside arguments and artifacts,
keep diagnostics on its diagnostic channel, and preserve its stated public
output contract. It must not alter the Kernel merely to introduce a domain
term, raw object, or legacy answer shape.

The [Domain Pack onboarding guide](../guides/domain-pack-onboarding.md) maps
these responsibilities to the inventory reference files and gives a stable
provider-free conformance entry for SDK and fixed HTTP authority examples.

## Verified grid application

`grid-static-analysis` is the first formal Capstone application. Its
`pandapower-domain-pack` supplies grid contracts, policy, guides, a `gridctl`
executor, projectors, and the current-run authority adapter. `grid-simulator`
owns the registered networks, pandapower calculations, result datasets, model
revisions, and evidence. Numerical and network-specific claims cross the
`gridctl` `grid-capability/1.0` boundary.

The `analysis-generic` path emits the composite result with Kernel-owned `core`
and pandapower-owned `domains.grid`. Provider-free application acceptance has
executed real semantic `gridctl` calls and checked current-run lineage, context
reuse, answer audit, report creation, replay, and the composite output.
Authorized provider runs have exercised the canonical business task suites
through that generic path. These results verify the first application's
assembly and compatibility boundary, not a claim that every prospective domain
has been accepted.

The stable `grid-agent` compatibility commands remain a vertical adapter. They
write exactly one JSON object to stdout with `question_id` and `answer_output`;
progress, diagnostics, tool events, and warnings belong on stderr. This is a
grid application contract, not the generic Capstone output protocol.

## Conformance proof and deferred scope

The read-only `inventory-reference-service` and `inventory-domain-pack` prove
that an independently installable domain can use the public Kernel SPI and
unchanged generic Pi transport without modifying protected framework paths.
Inventory is conformance infrastructure, not a production application and not
a runtime-selectable `grid-agent` mode.

The complete inventory profile supplies provisioning, detached state, domain
output validation, admission, guides and presentation through those same public
interfaces. Its conformance executes two real authority-backed turns and checks
report isolation and replay; installed-wheel tests exercise this application
outside the source tree. No inventory branch is added to the Kernel or grid CLI.

The repository's [two-binding acceptance](../../packages/inventory-domain-pack/tests/test_multi_binding_application.py)
explicitly assembles pandapower and inventory in one application. It calls both
registered authorities over two turns, reuses each binding's context, submits
separately owned claims through the real controller, and verifies namespaced
output, current-run evidence, report creation and replay. The scripted provider
supplies decisions only. Explicit claims use `TurnController.submit`; the
application's provider interface returns reader-facing text. A managed Pi
startup smoke also loads both published catalogs and guides through the default
generic extension without provider I/O.

The separately installable `pypsa-model-authority` and
`pypsa-network-modeling-domain-pack` provide registered model opening, typed
scalar and snapshot load-demand derivation, bounded inspection, and validation. The independent
`pypsa-power-operations-domain-pack` publishes fixed dispatch, unit commitment,
rolling storage dispatch, congested OPF, registered line-outage security
dispatch, and post-dispatch AC validation.
The `pypsa-capacity-planning-domain-pack` publishes registered generator
expansion, joint capacity and commitment, two-period investment, two-scenario
stochastic investment, and a near-optimal capacity alternative. The MGA
capacity objective and its system cost are separate result fields.
The `pypsa-sector-coupling-domain-pack` publishes registered
electricity-to-hydrogen, heat-pump, hydrogen and heat storage, and multi-port
CHP balances. Heat storage derives snapshot COP from registered ambient
temperatures and a fixed linear formula.
The [modeling](../../configs/capabilities/pypsa-1.3.0-modeling.json) and
[operations](../../configs/capabilities/pypsa-1.3.0-power-operations.json) and
[planning](../../configs/capabilities/pypsa-1.3.0-capacity-planning.json) and
[sector coupling](../../configs/capabilities/pypsa-1.3.0-sector-coupling.json)
catalogs identify their separate protocols and tools. An application-owned `ReferenceGrant` can permit an opaque model
revision to cross from one named binding to another for one purpose and
capability family. The Kernel records a content-addressed receipt in the
replayable context before target execution; both source and target authorities
verify the current-run revision. The Operations executor replays the receipt
and verifies its source, target, purpose, and model revision before requesting
the registered solver authority; the Planning and Sector executors apply the same grant
boundary. Installed-wheel smoke exercises modeling-to-Operations,
modeling-to-Planning, modeling-to-Sector, and a test-only receiver. The grid CLI selection
remains unchanged.
The grid/reference packages and PyPSA packages currently require separate
Python environments: the pinned pandapower and PyPSA releases require
different pandas major versions. The installed proofs compose two PyPSA
bindings, not a pandapower/PyPSA application in one interpreter.

The neutral `capstone-agent` owns a persistent session lifecycle and three
adapters: headless JSON request, interactive terminal, and loopback HTTP/SSE.
It selects only source-registered application workers through a bounded,
sequenced JSONL protocol. CLI and HTTP use the same `WorkerSession` API;
application workers own Profile assembly, Domain Pack selection, and the
current-run authority. The `grid-agent` compatibility entry remains the
pandapower adapter; `pypsa-agent` owns the PyPSA two-binding application.
Scripted demos and Provider routes share the Kernel's incremental turn runner.
Only the selected worker can read its admitted result/evidence references.
The legacy `tools/capstone_client.py` request command remains available. No
adapter performs dynamic Pack discovery or gives the model subprocess or file
capabilities.

Capstone does not yet provide dynamic plugin discovery, runtime domain
selection, cross-domain conflict resolution, or a chosen
second production application. Governed writes, approval flows, authenticated tenant/actor scope,
idempotency, compensation, and write-capability governance are likewise
deferred. The C.2 GitHub Repository Intelligence record is a working theory,
not an implemented or selected domain.

## Domain design rules

1. Define reusable semantic capabilities and an explicit, versioned authority
   protocol before exposing model tools.
2. Keep authority internals, credentials, and raw domain objects out of
   model-visible tools and Kernel contracts.
3. Make a Domain Pack own contracts, policy, guides, executor, projections,
   current-run admission, state validation, and its namespaced output payload.
4. Let the Kernel own neutral lifecycle, trajectory, artifact, replay, audit,
   and composite `core` concerns; do not couple it to a domain vocabulary.
5. Bind reader-facing factual claims only to current-run, authority-admitted
   result and evidence references.
6. Treat an application's public compatibility output as an application adapter,
   never as a framework-wide domain or Kernel rule.
7. Demonstrate provider-free acceptance first, then conduct authorized
   real-authority and provider checks separately. Fixtures prove conformance;
   they do not prove a production domain.

For grid-specific capability composition and operational details, see
[`pandapower-capability-composition.md`](pandapower-capability-composition.md)
and [`PANDAPOWER-APPLICATION.md`](../PANDAPOWER-APPLICATION.md).
