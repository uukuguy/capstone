# Repository Agent Contract

This file is the repository-wide instruction source for coding agents. Keep
`CLAUDE.md` as a relative symbolic link to `AGENTS.md` so Codex and Claude Code
read the same rules.

## Product and Architecture

Capstone Agent Framework builds evidence-backed applications over registered
business-domain systems. The first formal application is pandapower grid static
analysis; `grid-agent` remains its compatibility CLI. The repository also
contains registered PyPSA applications, capability-named Domain Packs, and an
independent operator App.

Preserve the four ownership layers:

```text
Application -> Domain Pack -> Kernel -> registered Authority
```

This is an ownership and dependency direction, not a requirement to import
through every adjacent layer. Applications select bindings, providers, public
UI/CLI contracts, and compatibility projections. Domain Packs own semantic
tools, contracts, policy, guides, execution, projection, and domain state.
The Kernel owns neutral composition, bounded context, turns, trajectory,
artifacts, replay, and framework `core`. Registered authorities own model
access, deterministic or source-backed facts, revisions, results, and evidence.
Results and evidence return through explicit contracts, never raw objects.
Read [the framework architecture](docs/architecture/capstone-framework.md)
before changing these boundaries.

A new domain needs a separately installable Domain Pack using the public Kernel
SPI, a registered authority, and an application-selected binding. Keep domain
semantics out of the Kernel. Do not couple one Domain Pack to another's state.
Cross-domain model references require an explicit application grant and typed
handoff; a public compatibility projection belongs to its application.

## Authority and Model Boundaries

- An agent may call only published, allowlisted semantic tools with exact
  contracts. Do not give it shell commands, arbitrary subprocesses, Python
  execution, generic file access, caller-selected endpoints, raw DataFrames,
  `pandapowerNet` objects, or authority internals.
- New tools must describe reusable domain actions, not a particular question,
  fixture, network, expected answer, or legacy query alias.
- For pandapower, numerical and network claims cross `gridctl` through
  `grid-capability/1.0`. `gridctl` and `grid-simulator` own registered networks,
  calculations, model revisions, result datasets, and simulator evidence.
  Never invent losses, voltages, rankings, topology, contingency outcomes,
  or evidence.
- PyPSA calculations and model changes stay behind the registered PyPSA
  authority and its selected Domain Packs. Do not pass raw PyPSA Networks
  across application, pack, or Kernel boundaries.
- The model may compose tools and write reader-facing text. Current-run
  result and evidence references are admitted and bound by the application
  and Domain Pack, not asserted by the model. Observation and reporting may
  diagnose a valid answer without replacing authority truth; required answer
  or evidence persistence failures remain fatal.

## Public Contracts and Runtime State

- The pandapower compatibility `run`, `analysis`, and `report` paths write
  exactly one stdout JSON object containing `question_id` and `answer_output`.
  Progress, tool events, warnings, and diagnostics go to stderr. The generic
  application path uses its separate `core` plus `domains.<binding_id>` output.
- Offline informational answers create no run evidence. Simulator-backed
  claims may cite only results and evidence admitted for the current run.
  `runs/` is ignored operator-visible evidence and validation-report storage;
  `.grid-agent/` is ignored internal authentication, runtime, cache, and
  session state. Versioned runtime configuration belongs in `configs/runtime/`.
- The hosted App is a presentation client for the same `/api/v1` contract
  locally and in the cloud. Public demonstration credentials are scoped to
  registered scripted cases; they must not grant Provider access. The browser
  receives bounded API projections, not bucket credentials or raw artifacts.
- The API and worker run from the same backend source/image revision and share
  the PostgreSQL ledger and private artifact storage. Cloud Run, Railway, and
  local Compose must preserve this contract. Never put operator or Provider
  secrets in static App build variables such as `VITE_API_ORIGIN`.
- Provider credentials belong in environment variables or project-owned
  ignored authentication state. Never place them in arguments, logs, commits,
  simulator environments, or answer artifacts.

## Sources of Truth

Read the owning source before changing behavior; do not duplicate changing
counts, prices, limits, versions, or deployment state here.

| Topic | Source |
| --- | --- |
| Product overview and local entry points | [README](README.md), [中文 README](README.zh-CN.md), [runbook](docs/RUNBOOK.md) |
| Framework layers, output, and evidence | [Capstone architecture](docs/architecture/capstone-framework.md) |
| pandapower capability registration and LLM composition | [Capability architecture](docs/architecture/pandapower-capability-composition.md) |
| Published pandapower coverage | [Executable capability matrix](configs/capabilities/pandapower-3.4.0-static-analysis.json) |
| Simulator pin | [grid-simulator manifest](packages/grid-simulator/pyproject.toml) |
| Model-facing grid policy and guides | [Policy](packages/pandapower-domain-pack/src/pandapower_domain/resources/policy/system-policy.md), [guides](packages/pandapower-domain-pack/src/pandapower_domain/resources/guides/) |
| Hosted App and local operations | [Runbook](docs/RUNBOOK.md#hosted-app-and-deployment) |
| Cloud deployment | [Railway](deploy/railway/README.md), [Cloud Run + Vercel](deploy/cloud-run/README.md) |
| Structural state and recovery baton | [Current state](docs/status/CURRENT-STATE.md), [resume](docs/status/RESUME-NEXT-SESSION.md) |

## Working in This Repository

- Preserve unrelated tracked and untracked user work. Stage only task-owned
  paths. Do not delete or migrate existing main-worktree `var/` data.
- Prefer `rg` and `rg --files` for discovery. Use `apply_patch` for text edits
  and explicit non-destructive commands for filesystem operations.
- Keep `README.md` and `README.zh-CN.md` aligned when shared product facts,
  commands, headings, or references change. Write for readers; move detailed
  procedures into the runbook and volatile status into `docs/status/`.
- An isolated worktree is an implementation aid. Unless the user requests
  branch-only delivery, integrate accepted changes into the main checkout
  and verify its real entry point. Preserve deferred work and user data.
- A fresh worktree lacks ignored runtimes. Before testing Pi, `gridctl`, or
  JavaScript tools there, run `make setup`, `make install-pi`, and
  `make doctor`. Missing managed runtimes are setup failures, not product
  regressions. Do not copy ignored authentication state from another worktree.

### Local rebuild and deployment

When local API, worker, or App source changes, use the checked-in rebuild
entrypoint instead of starting Compose with an old image:

```sh
make capstone-local-rebuild
```

`deploy/rebuild_local.sh` loads the ignored `deploy/local.env`, validates the
Compose configuration, rebuilds the API and worker image from the current
checkout, force-recreates both roles, waits for PostgreSQL/object storage and
the worker, checks `/health/ready`, verifies that API and worker run the same
image digest, and ensures the Vite App is reachable. If the App is not already
running, it starts a background dev server and records its PID/log under the
ignored `.capstone-agent/` directory. Set `CAPSTONE_START_APP=0` to skip that
step, `CAPSTONE_LOCAL_PULL=1` when base images should also be refreshed, or
`CAPSTONE_LOCAL_ENV_FILE=/path/to/local.env` when using a different local
environment file. Before the Docker build, the script verifies the six pinned
PyPSA assets in `.grid-agent/runtime/pypsa-models` (or the directory named by
`CAPSTONE_PYPSA_MODEL_LIBRARY_DIR`) and stages them under the ignored
`deploy/local-model-assets/` build directory, so a local rebuild does not
redownload model files. The script never prints secret values.

The App remains a separate Vite development process because Compose does not
host the static App. It listens on `0.0.0.0` by default so a phone on the same
LAN can open `http://<computer-lan-ip>:5173/`; set `CAPSTONE_APP_HOST=127.0.0.1`
to restrict it to the computer. `make capstone-app-dev` remains the foreground
alternative when interactive logs are needed. A stale browser session should
be refreshed or reset before starting a new case.

## Verification

Run the smallest focused check for the changed behavior, then the repository
gates needed for its scope. Supported offline gates are:

```sh
make doctor
make test
make test-e2e
make validate
```

Use the full gates for integration or release claims; a focused App or
documentation change does not itself justify repeating every suite.
Documentation-only changes require link and symlink checks,
`git diff --check`, and `make doctor`. `make validate-provider PROVIDER=<id> [MODEL=<id>]`
is optional, may be billed, and requires explicit authorization.
Every change must preserve the compatibility stdout envelope, authority
boundaries, and current-run evidence rules.
