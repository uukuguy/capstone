# Capstone Agent Framework

English | [简体中文](README.zh-CN.md)

Capstone is a capability-first framework for assembling evidence-backed
applications over authoritative business-domain systems.

It separates a domain-neutral Kernel, independently installable Domain Packs,
and application-owned compatibility products. Models compose only bounded
semantic capabilities; a registered authority remains the source of domain
facts and current-run evidence. The [Capstone framework guide](docs/architecture/capstone-framework.md)
is the primary architecture reference.

## Framework Architecture

Capstone keeps four ownership layers distinct:

```text
Application -> Domain Pack -> Kernel -> registered Authority
```

Dependencies flow only to the right. Results and evidence references return
through explicit contracts, rather than reverse imports or raw-object access.
The Application owns its public CLI or UI and any compatibility projection; the
Domain Pack owns domain contracts, policy, guides, execution, projections, and
current-run domain state; the Kernel owns neutral composition and lifecycle;
and the registered Authority owns source-backed or deterministic domain facts,
results, revisions, and evidence.

## Adding an Application

To integrate a new application, define its authoritative system boundary and
versioned semantic protocol; implement a Domain Pack through the public Kernel
SPI; bind that pack from an `ApplicationProfile` with scoped credentials and a
public renderer; then prove provider-free acceptance using real authority calls
and current-run evidence lineage. Dynamic discovery, runtime domain selection,
and multi-domain routing are not currently provided.

## Framework Guarantees

- The model receives only published, executable semantic tools with exact
  schemas, bounded context, policy, and guides.
- The authority, not the model, Kernel, or application, produces domain facts
  and admits their current-run evidence.
- Generic results preserve Kernel-owned `core` and Domain-Pack-owned namespaced
  payloads; an application owns any versioned public compatibility projection.
- Reader-facing factual claims use only authority-admitted result and evidence
  references from the current run.

The full ownership, runtime, composite-output, and current-run evidence
protocols are defined in the [Capstone framework guide](docs/architecture/capstone-framework.md).

## First application: Grid Static Analysis

This repository's first Capstone application is `grid-static-analysis`:
`grid-agent` performs evidence-backed static analysis of registered
power-system networks. An LLM interprets the request and composes
project-defined tools; `gridctl` and the pinned pandapower simulator perform
every deterministic network calculation.

`v1.0.1` is the stable release of the declared static-analysis product scope.
The executable capability matrix remains the authority for current coverage.

## What It Does

- Discovers registered networks and creates controlled declarative models.
- Derives immutable network revisions and analysis scenarios.
- Runs topology, AC/DC/three-phase power flow, AC/DC optimal power flow,
  IEC 60909 short-circuit, state estimation, diagnostics, contingency, risk,
  equivalent-network, and static protection analyses.
- Queries, aggregates, compares, and ranks simulator-owned result datasets.
- Carries verified context across multi-step analysis and continuous reports.
- Records native trajectories and serves a read-only investigation workbench.
- Binds final numerical claims to current-run result and evidence references.

The project covers its declared pandapower static-analysis scope, not every
public pandapower API. Time-series/control workflows, plotting, arbitrary
file/database conversion, and unpinned external solver runtimes remain outside
the model capability boundary. See the
[capability architecture](docs/architecture/pandapower-capability-composition.md)
and the
[executable coverage matrix](configs/capabilities/pandapower-3.4.0-static-analysis.json).

## Grid Application Architecture

```text
Natural-language request
        |
        v
grid-agent + Pi/LLM       intent, tool composition, context, answer envelope
        |
        v  grid-capability/1.0
gridctl + grid-simulator  contracts, registered models, results, evidence
        |
        v
pandapower                deterministic power-system calculations
        |
        v
runs/<question_id>/       operator-visible current-run evidence
```

The LLM chooses from registered semantic tools; it never receives shell,
arbitrary Python, raw pandapower objects, DataFrames, or generic filesystem
access. Numerical and network-specific claims must come back through the
simulator boundary.

## Package Assembly

Capstone's reusable seams assemble domain packages through the Kernel,
capability transport, current-run authority, and application composition.
The pandapower packages below form the first formal application;
`inventory-domain-pack` remains conformance infrastructure, not a selected
second production domain.

The repository now contains six independently buildable Python distributions
and two Pi npm packages. Four distributions assemble the grid product; two form
the read-only inventory reference domain used to prove the public Domain Pack
SPI:

| Distribution | Responsibility |
| --- | --- |
| `capability-agent-kernel` | Domain-neutral manifest, contract, executor, projection, authority, tool-catalog, guide, trajectory, and composition interfaces |
| `grid-simulator` | `gridctl`, registered pandapower networks, deterministic calculations, result datasets, and simulator evidence |
| `pandapower-domain-pack` | Pandapower static-analysis domain profile, policy, guides, capability contracts, resource ownership, and compatibility adapters |
| `grid-agent` | CLI, provider/Pi runtime setup, authentication, continuous analysis, reporting, workbench service, and final JSON answer envelope |
| `inventory-reference-service` | `inventoryctl`, a registered read-only catalog, strict `inventory-capability/1.0`, and content-addressed inventory artifacts |
| `inventory-domain-pack` | Inventory profile, policy, guides, contracts, executor, projectors, and current-run artifact authority built only on the public kernel SPI |
| `@capability-agent/pi-tools` | Generic descriptor-driven Pi capability request transport and request capture |
| `@grid-static-analysis/pi-grid-tools` | Grid-compatible Pi extension wrapper that preserves existing `grid_*` tools and guide behavior |

Source-mode development uses the local path dependencies pinned in the package
manifests. Install-mode verification builds all six Python wheels plus both npm
tarballs, installs them outside the repository, and runs smoke checks without
importing from source paths:

```sh
make test-packages
```

The inventory reference domain reuses the unchanged generic Pi transport and
kernel composition path while protected framework paths remain byte-identical.
This proves that a separately packaged, read-only business authority can
instantiate the single-domain framework without copying `grid-agent` or
modifying the kernel. The shipped `grid-agent` CLI still explicitly selects the
pandapower profile; dynamic discovery, runtime domain selection, multi-domain
routing, and governed write actions remain future work.

The external grid compatibility CLI, Pi tool names, `grid-capability/1.0`
protocol, v1.0.1 two-field stdout envelope, stderr diagnostics, `runs/` evidence
layout, and simulator-owned truth contract remain unchanged. The explicitly
generic `analysis-generic` command uses the composite output contract described
below.

## Generic Application Path

The reusable application seam is assembled in one direction:

```text
ApplicationProfile -> AgentApplication -> DomainBinding -> Domain Pack
```

The Kernel owns the framework `core` section (run identity, lifecycle, status,
turn and audit metadata). Each Domain Pack owns its own
`domains.<binding_id>` section and its semantic payload. The generic entry point
preserves both sections and emits the composite `capability-agent-output/1.0`
contract, for example:

```json
{"schema":"capability-agent-output/1.0","core":{...},"domains":{"grid":{...}}}
```

Run the formal built-in pandapower application:

```sh
make application
```

For an explicit instruction file, Provider, or model, use Makefile overrides;
the complete runtime, output, billing, and current-run evidence contract is in
[Pandapower Static-Analysis Application](docs/PANDAPOWER-APPLICATION.md). The
provider-free acceptance gate exercises the same prepared pandapower endpoint
and real semantic `gridctl` calls:

```sh
make validate-application
```

`inventory-domain-pack` is a fixture/conformance reference only; it is not a
second production CLI mode or a claim that a useful second business agent has
been selected. C.1 is complete: both canonical v1.0.1 business task files have
passed through `analysis-generic` with authorized provider evidence, and the
explicit compatibility path preserves the v1.0.1 answer envelope. See
[Pandapower Static-Analysis Application](docs/PANDAPOWER-APPLICATION.md) for
the canonical operator workflow.

The generic composite result is deliberately different from the explicit
v1.0.1 compatibility projection. The `run`, `analysis`, and `report` commands
retain their versioned adapter and its exact two-field stdout object
(`question_id` and `answer_output`); the richer internal result is still
validated before the adapter renders the legacy envelope.

## Quick Start

Prerequisites are Python 3.12+, Node.js 22.19+, `uv`, and `npm`. Provider-backed
analysis additionally needs a supported LLM credential; offline smoke checks do
not.

```sh
git clone https://github.com/uukuguy/grid-static-analysis.git
cd grid-static-analysis
make setup
make doctor
```

Run a deterministic offline smoke check:

```sh
make run QUESTION="IEEE-39节点系统中线路11连接哪两个母线?"
```

Run the primary natural-language agent path:

```sh
cp .env.example .env
# Configure one supported provider credential in the ignored .env file.
make install-pi
make run-llm QUESTION="Run an AC power flow on the IEEE 39-bus network and report active power losses."
```

For project-owned OpenAI Codex OAuth instead of an API key, set
`GRID_AGENT_LLM_PROVIDER=openai-codex` in `.env` before using `make auth-login`;
the login command does not select the provider. You can also select it per
invocation with `make run-llm PROVIDER=openai-codex QUESTION="..."`. See the
[runbook](docs/RUNBOOK.md) for provider setup, authentication precedence,
runtime installation, and failure diagnosis.

## Primary Workflows

| Goal | Command |
| --- | --- |
| Inspect runtime readiness | `make doctor` |
| Offline deterministic smoke check | `make run QUESTION="..."` |
| LLM-led single question | `make run-llm QUESTION="..."` |
| Continuous multi-question analysis | `make analysis INSTRUCTIONS=path/to/instructions.txt` |
| Compatibility alias for continuous analysis | `make report INSTRUCTIONS=path/to/instructions.txt` |
| Formal pandapower application | `make application [INSTRUCTIONS=...]` |
| Generic registered application | `make analysis-generic APPLICATION=... INSTRUCTIONS=...` |
| Provider-free application acceptance | `make validate-application` |
| Build and serve the read-only workbench | `make trajectory PORT=8765` |

`grid-agent run` writes exactly one JSON object to stdout:

```json
{"question_id":"...","answer_output":"..."}
```

Progress, diagnostics, and tool events stay on stderr. Continuous analysis also
emits one final answer envelope whose `answer_output` points to the generated
report.

## Results, Evidence, and Workbench

Simulator-backed runs store operator-visible artifacts under
`runs/<question_id>/`. Final claims can cite only result and evidence references
admitted for the current run. Pure informational offline answers do not create
simulation evidence.

Internal authentication, managed Pi runtime files, caches, and session state
stay under the ignored `.grid-agent/` directory. Versioned runtime configuration
stays under `configs/runtime/`.

Start the local read-only trajectory workbench with:

```sh
make trajectory PORT=8765
```

It serves the UI and API on `http://127.0.0.1:8765`. The workbench projects
recorded facts for investigation; it cannot mutate runs or replace simulator
truth.

## Verification

```sh
make doctor
make test
make test-e2e
make validate
make validate-application
make test-inventory
make test-packages
```

`make validate-provider PROVIDER=<id> [MODEL=<id>]` is optional, requires
explicit credentials, and may incur provider charges.

## Repository Layout

| Path | Responsibility |
| --- | --- |
| `packages/capability-agent-kernel/` | Domain-neutral Python kernel contracts, composition, tools, guides, and trajectory primitives |
| `packages/grid-simulator/` | `gridctl`, registered models, pandapower execution, results, and evidence |
| `packages/pandapower-domain-pack/` | Pandapower domain profile, contracts, policy, guides, resources, and adapters |
| `packages/grid-agent/` | CLI, Pi/LLM runtime, context, reports, workbench service, and answer envelope |
| `packages/inventory-reference-service/` | Read-only registered inventory authority, protocol, artifacts, and `inventoryctl` |
| `packages/inventory-domain-pack/` | Reference inventory Domain Pack using the public kernel SPI and generic Pi transport |
| `packages/pi-capability-tools/` | Generic descriptor-driven Pi capability transport and request capture |
| `packages/pi-grid-tools/` | Grid-compatible Pi tools wrapper, guides, and request capture |
| `packages/trajectory-workbench/` | Read-only React/TypeScript trajectory investigation UI |
| `configs/` | Versioned capabilities, policies, provider catalog, and runtime configuration |
| `validation/` | Offline, scripted-Pi, semantic, and optional provider validation suites |
| `docs/` | Runbooks, architecture, design history, plans, and durable project state |

## Documentation

- [Capstone framework architecture](docs/architecture/capstone-framework.md) — implemented Kernel, Domain Pack, application, authority, and evidence boundaries.
- [Runbook](docs/RUNBOOK.md) — setup, authentication, execution, evidence, and troubleshooting.
- [Manual validation guide](docs/MANUAL-VALIDATION.md) — reproducible human acceptance procedure.
- [Capability registration and composition](docs/architecture/pandapower-capability-composition.md) — scope and LLM tool orchestration boundaries.
- [Analysis context architecture](docs/architecture/analysis-context.md) — verified multi-step context model.
- [Trajectory event architecture](docs/architecture/trajectory-events.md) — authoritative native execution chronology.
- [Current project state](docs/status/CURRENT-STATE.md) — structural snapshot and implementation entry points.
- [Repository agent contract](AGENTS.md) — stable Codex/Claude Code rules and sources of truth.

## Security and Contribution Boundaries

Keep credentials in environment variables or ignored project-owned auth state.
Do not place secrets in command arguments, committed files, logs, simulator
environments, or evidence. New model capabilities must remain reusable,
contract-defined, allowlisted, and executed by their registered authority—never
question-specific shortcuts or arbitrary execution surfaces.
