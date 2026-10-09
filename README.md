# Capstone Agent Framework

English | [简体中文](README.zh-CN.md) | [Try the live demo](https://capstone-app-production-975e.up.railway.app/)

**Connect agent reasoning to domain capabilities, authoritative computation, and verifiable evidence.**

Capstone is a domain-neutral agent framework for applications backed by registered business and scientific systems. An application selects its Domain Packs and authorities. The agent composes their published semantic tools; the authorities own model facts and calculations. The framework binds results, evidence, and model revisions to each run, then exposes them through conversation, reports, and interactive views.

Its first formal application is **power-grid static analysis through an agent conversation**. The workspace connects pandapower and PyPSA models to continuous analysis: ask a question, execute domain tools, inspect the answer, and locate the affected components on the electrical topology.

The design follows four principles:

- **Compose capabilities through contracts.** Tools describe reusable domain actions, with schemas, policies, and guides supplied by the selected Domain Packs.
- **Keep facts with the authority.** Registered systems access models, execute calculations, and produce result datasets and evidence. The agent organizes the analysis and explains the returned facts.
- **Keep the Kernel domain-neutral.** Context, turns, execution trajectories, artifacts, and replay are shared framework services. Domain semantics stay in independently installable packs.
- **Connect each answer to its model and evidence.** Admitted references preserve run and revision lineage, so the App can link text, result tables, topology, and execution records.

![Current Capstone conversation workspace: IEEE-39 topology alongside an agent answer with power-flow results](docs/images/capstone-agent-conversation.png)

The live App above shows a completed IEEE-39 analysis. Its numbers belong to that run.

## Architecture and execution

The four layers define ownership and dependency direction:

```mermaid
flowchart LR
    A[Application] --> P[Domain Pack]
    P --> K[Kernel]
    K --> R[Registered Authority]
```

| Layer | Responsibility |
| --- | --- |
| Application | Select profiles, domain bindings and Providers; own public conversation, API, CLI, and compatibility output |
| Domain Pack | Own semantic tools, contracts, policy, guides, execution, domain state, result/evidence admission, and projections |
| Kernel | Compose the selected capabilities; manage bounded context, turns, trajectories, typed commits, artifacts, and replay |
| Registered Authority | Own model access, revisions, calculations or source-backed facts, result datasets, and evidence |

This ownership diagram does not require calls or imports through every adjacent layer. During execution, the **Application enters the Kernel lifecycle**, which invokes an **injected Domain Pack executor** to call the authority. On return, the **Domain Pack admits and projects authority results**, the Kernel commits typed state, and the Application renders the answer and views. The Kernel does not import authority implementations.

The agent sees allowlisted semantic tools with exact contracts. Raw pandapower/PyPSA objects, arbitrary Python, shell commands, and generic file access stay outside that interface. Numerical claims cross the registered authority contract. Result and evidence references must be admitted for the current run and the required model revision; a model-written reference alone does not establish evidence. Informational answers, such as model catalogs, create no calculation evidence.

See the [framework architecture](docs/architecture/capstone-framework.md) for the contracts and lifecycle, and [pandapower capability composition](docs/architecture/pandapower-capability-composition.md) for the first application's authority boundary.

## Integrate and compose Domain Packs

A Domain Pack packages a domain's tool catalog, schemas, policy, guides, executor, authority adapter, state, and result projections behind the public Kernel SPI. An Application Profile selects named bindings and tool prefixes. Each binding has its own domain state and credential scope; generic output separates framework `core` from `domains.<binding_id>`.

The current [PyPSA Application Profile](packages/pypsa-agent/src/pypsa_agent/profile.py) demonstrates composition:

| Binding | Domain Pack | Tool prefix | Role |
| --- | --- | --- | --- |
| `source` | PyPSA network modeling | `pypsa_model_` | Inspect registered models and derive model revisions |
| `operations` | PyPSA power operations | `pypsa_ops_` | Run dispatch, operational optimization, and AC validation |

The application grants the operations binding access to a typed model reference from the source binding. The source authority verifies the revision; the handoff receipt is persisted for replay, and the target binding admits the reference before execution. Composing packs does not share raw Networks, credentials, or mutable state automatically.

The repository also provides PyPSA capacity-planning and sector-coupling packs. Those are separately selected capabilities; the hosted PyPSA conversation currently binds network modeling and power operations. A read-only inventory reference pack exercises the same SPI outside the grid domain.

To add a domain, register its authority contract, implement a separately installable pack using the public SPI, and select its bindings and any reference grants in an application. Validate packaged resources, contracts, execution, result/evidence admission, and replay against the real authority. The [Domain Pack onboarding guide](docs/guides/domain-pack-onboarding.md) provides the implementation path and conformance checks.

## Start with a question

Open the [demo](https://capstone-app-production-975e.up.railway.app/) or run the App locally. The root page opens the agent conversation directly. Use the **Model** menu or a natural-language instruction to select a registered grid model, then ask questions about that model.

For an IEEE-39 analysis, try a sequence like this:

```text
List the registered pandapower grid models.
Open the ieee39 grid model.
Run an AC power flow and report convergence and total active-power losses.
Using those results, find the three lines with the highest loading.
Show their endpoint buses and the results and evidence supporting the answer.
```

Continue in the same conversation to inspect results or refine the analysis. Each instruction is bound to a model context and run. The **New conversation** action creates a separate Thread; its URL lets you return to it after a page refresh.

In **Capstone** mode, model-based intent recognition separates professional and
general goals. Professional goals use enabled Domain Packs; general goals delegate
to an isolated native Pi agent. **Pi** (direct Pi) mode selects relevant public
business context, then sends the task to that same executor. Switch modes while
the Thread is idle; history, draft and model
selection remain available. General outputs create no Authority results or evidence.
Live news or weather still needs an accessible source. See the
[shared executor design](docs/superpowers/specs/2026-10-09-capstone-pi-delegation-design.md).
Actual model response quality requires separate acceptance; offline checks alone do
not establish it.

Use `/skills` to inspect available skills and their execution role,
`/skill:<name> <task>` to select one, and `/context` to include or exclude public background.
The current model background includes identity, version and history; it does not
include full model tables. Managed PowerSkills/PowerMCP resources have separate
native Pi and professional adapters. See the [resource setup instructions](docs/RUNBOOK.md#共享背景与角色资源).

The conversation is the primary interface. Cases are an independent module; the
default federated conversation does not yet assemble Case execution. Registered
guided workflows and validation fixtures remain at the earlier `/old` entry.

## What you can analyze

| Model family | Current conversation capabilities |
| --- | --- |
| pandapower | Registered model inspection, buses and branches, topology, AC/DC power flow, losses, loading, model-constraint checks, and N−1 analysis |
| PyPSA | Registered model inspection and demand derivation, fixed-capacity economic dispatch, unit commitment, rolling storage dispatch, congested OPF, registered outage security dispatch, and post-dispatch AC validation |

Available operations depend on the selected model and its published capability contracts. The model menu reports when a complete topology is unavailable. See the [pandapower capability matrix](configs/capabilities/pandapower-3.4.0-static-analysis.json), [PyPSA modeling catalog](configs/capabilities/pypsa-1.3.0-modeling.json), and [PyPSA operations catalog](configs/capabilities/pypsa-1.3.0-power-operations.json) for executable scope.

## Link conversation, results, and topology

The topology is a view of an authority-owned model, linked to the analysis through explicit references. The App receives a bounded geometry projection, separate from the agent's model-facing context. Model coordinates preserve registered schematic or geographic structure.

![Agent conversation listing the three lines with the highest loading, alongside their highlighted topology and loading overlay](docs/images/capstone-agent-topology.png)

Ask the agent to list the three lines with the highest loading. The answer presents the ranking, endpoint buses, power flows, and losses; the corresponding grid view highlights the analyzed lines and their loading. This screenshot shows a completed analysis, with names and values recorded for that run's model revision.

For a result such as “the three lines with the highest loading,” follow the linked views:

1. Open the answer's grid action to return to the model view associated with that instruction.
2. Open the structured analysis results. Where a row has an element reference, click its component to locate it on the topology.
3. Pan, zoom, and inspect components. Labels use model names with `bus`, `line`, and `trafo` prefixes; PyPSA links use `link`, so diagram names agree with component references in the answer and tables.
4. Review evidence and execution steps to trace the calculation. Historical instruction views retain their model context; selecting a result restores its matching view.

Numerical overlays use admitted results for the matching model revision and run. Missing values stay neutral. A line-loading color scale describes the returned values; a constraint assessment determines whether a limit is exceeded. Model changes and historical results remain distinguishable through their revision and run references.

Results, reports, and evidence can be revisited through the API. The browser receives bounded projections from private storage. This gives the conversation, table, and topology a common model identity and evidence trail.

## Run locally

You need Python 3.12+, `uv`, Docker Compose, Node.js 22.19+, and npm. For a fresh checkout:

```sh
git clone https://github.com/uukuguy/capstone.git
cd capstone
make setup
make install-pi
make install-pypsa-models
cp deploy/local.env.example deploy/local.env
```

Edit the ignored `deploy/local.env` and replace the example database, storage, operator, and Provider credentials. Keep runtime selectors consistent with the [shared host runtime profile](configs/runtime/host-runtime-v1.json). Provider credentials stay in backend configuration; normal agent conversations use the configured LLM and may incur Provider charges. See the [runbook](docs/RUNBOOK.md#hosted-app-and-deployment) for configuration.

Start the API, pandapower worker, PyPSA worker, and App with the checked-in entrypoint:

```sh
make capstone-local-rebuild
```

Open `http://127.0.0.1:5173/`. Local Compose enables direct conversation access without a browser token. The rebuild checks dependencies and readiness, verifies that API and both workers use the same image, and starts the Vite App when needed. It reuses verified local PyPSA model assets. Run it again after API, worker, or App source changes.

The App also listens on the LAN by default: a phone on the same network can open `http://<computer-lan-ip>:5173/`. Set `CAPSTONE_APP_HOST=127.0.0.1` for computer-only access. Use `make capstone-app-dev` when you want the Vite process in the foreground.

## CLI and compatibility entry points

The CLI remains useful for automation and focused checks. After setup, run an offline pandapower query:

```sh
make doctor
make run QUESTION="IEEE-39节点系统中线路11连接哪两个母线?"
```

For LLM orchestration, configure the CLI Provider as described in the [runbook](docs/RUNBOOK.md#llm-配置与-pi-rpc-路径), then use:

```sh
make run-llm QUESTION="对 IEEE-39 执行交流潮流，并报告有功损耗。"
```

`grid-agent` remains the pandapower compatibility CLI. Its answer, report, and stdout contracts are documented in the [pandapower application guide](docs/PANDAPOWER-APPLICATION.md). The unified `capstone-agent` CLI and guided-case commands are documented in the [runbook](docs/RUNBOOK.md#capstone-统一客户端). Deterministic scripted fixtures support offline validation; they are separate from ordinary LLM conversation.

## Develop and deploy

Use local Compose plus Vite for iteration, cloud development for remote integration checks, and demo for verified user-trial releases. Cloud development and demo have separate databases, artifact storage, credentials, and public origins. Demo promotion uses the exact source revision or artifact verified in cloud development.

Focused App checks are `make test-capstone-app` and `make build-capstone-app`. Repository offline gates are:

```sh
make doctor
make test
make test-e2e
make validate
```

Provider validation is a separate, explicitly authorized check. Deployment procedures and runtime configuration belong to the operational guides:

- [Development and release lifecycle](docs/architecture/capstone-development-lifecycle.md)
- [Railway deployment](deploy/railway/README.md)
- [Cloud Run + Vercel deployment](deploy/cloud-run/README.md)
- [Runbook](docs/RUNBOOK.md)
- [Current project state](docs/status/CURRENT-STATE.md)
