# Repository Agent Contract

This file is the repository-wide instruction source for coding agents. Keep
`CLAUDE.md` as a relative symbolic link to `AGENTS.md` so Codex and Claude Code
read the same rules.

For displaying logs and content output, please use the ASD-STE100 specification, or meet 80% of the ASD-STE100 specification.

## Product and Architecture

Capstone Agent Framework builds evidence-backed applications over registered
business-domain systems. The first formal application is pandapower grid static
analysis. The user has withdrawn the `grid-agent` CLI compatibility requirement;
its old package still contains formal pandapower runtime modules pending migration.
The repository also
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

## Development and Release Architecture

Capstone has three execution lanes: local Compose plus Vite for high-frequency
iteration, an isolated cloud-development stage for remote integration
validation, and an isolated user-trial stage for stable releases. The local
lane is not a substitute for cloud verification, and the cloud-development
lane is not a user-data or production lane. Read the normative
[development and release lifecycle](docs/architecture/capstone-development-lifecycle.md)
before changing deployment, release, or environment behavior.

- Cloud development and user trial must never share PostgreSQL, artifact
  buckets, operator tokens, public origins, or mutable
  run/session/evidence data.
- Provider credentials are separate by default. For the current function
  validation stage, the user permits existing Provider credentials and
  explicitly selected open Thread access without a login screen. Keep
  credentials in backend protected variables; do not expose them to the App.
- API and worker within one stage must use the same tested backend source
  revision or exact image digest. A user-trial release promotes that exact
  verified revision or digest; ordinary development pushes must not update the
  user-trial stage.
- The local API, worker, and App path is rebuilt with
  `make capstone-local-rebuild` before remote validation. Do not test an old
  Compose image and call the result current.
- `local-dev` serves `cloud-dev` development tests and release verification.
  `local-demo` serves `cloud-demo` reproduction, emergency repairs and release
  verification. At rest it follows the accepted cloud-demo source and feature
  scope; record any temporary repair or release candidate difference. Do not
  update local-demo with ordinary development builds or make the local versions
  equal solely for convenience. Preserve existing data during source realignment.
- Cloud-development validation covers readiness, App health, registered cases,
  Provider behavior when separately authorized, reports, evidence replay, and
  API/worker identity before promotion. Failed releases roll back to the last
  verified user-trial revision.
- After every cloud-dev deployment passes its required validation, create and
  push an annotated Git tag for that stage. After every demo deployment passes
  its required validation, create and push a separate annotated Git tag for
  demo, even when both stages use the same source revision. Use
  `cloud-dev-<YYYYMMDD-HHMM>-<short-sha>` and
  `demo-<YYYYMMDD-HHMM>-<short-sha>`. Each tag must point to the exact deployed
  and verified source commit. Its annotation records the stage, source/image
  identity, deployment IDs, and verification receipt or report. Failed or
  incomplete validation must not receive an acceptance tag. Never move or
  reuse an existing tag.
- Hosted App build variables may contain only the selected API origin. Provider
  and operator secrets stay in protected environment variables or ignored
  authentication state and never enter source, logs, arguments, or artifacts.
- Public demonstration access, when enabled for a no-login App smoke target,
  remains limited to registered scripted cases and never grants Provider access.

## Authority and Model Boundaries

- A professional Domain Pack session may call only published, allowlisted semantic tools with exact
  contracts. Do not give it shell commands, arbitrary subprocesses, Python
  execution, generic file access, caller-selected endpoints, raw DataFrames,
  `pandapowerNet` objects, or authority internals.
- Application-owned general tasks may delegate to the isolated native Pi
  executor. Its native tools operate only in private task workspaces, without
  business files, authority handles, or host credentials. General observations
  and products never become Authority results or simulator evidence implicitly.
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
| Development and release lifecycle | [Lifecycle architecture](docs/architecture/capstone-development-lifecycle.md) |
| Structural state and recovery baton | [Current state](docs/status/CURRENT-STATE.md), [resume](docs/status/RESUME-NEXT-SESSION.md) |

## Working in This Repository

- `dev` is the default development integration branch. Feature, fix, docs and
  chore PRs target dev. Experiments enter dev only as scoped reviewed work.
  `main` holds accepted release baselines; release PRs target main and run full
  verification. Hotfixes start from the actual accepted deployment tag and flow
  back to dev. Do not rewrite shared history.
- Current project control and canonical worklists live on dev. Main copies are
  release snapshots. Both permanent branches require PRs and Linux/macOS
  checks, with zero mandatory approvals and no force push or deletion. Record
  any administrator emergency bypass. Branch heads do not imply deployment.

- Keep project control bidirectionally aligned. Changes to implementation, branches,
  PRs, validation or deployment update `docs/status/VERSION-CONTROL.md` and its
  generated `PROJECT-OVERVIEW.html`. Decisions made through the control graph
  update owning designs, executable plans, canonical worklist and affected branch
  copies before reporting alignment complete. Every graph update uses
  `ui-ux-pro-max`, re-layout and browser checks, including source edges and crossings.
  Close verified merged branches; preserve unmerged work and recovery references.
  The graph centres on active nodes, exact sources for the four deployments and
  actual research branches. The dev spine retains important cloud deployments
  and major branch merges. Move ordinary edits and interim candidates into
  history details; do not label paused plans or archived references as active.

- The development control graph and its canonical register are owned by `dev`.
  Update and integrate them into `dev`; a feature-branch copy or screenshot alone
  is not a completed control update. Main contains only a release snapshot.
  At each major development boundary, record implementation, verification, merge
  and deployment state before reporting completion. After a PR merge and dependent
  branch synchronization, refresh the graph in the actual dev checkout and inspect
  that page. Show current branch HEADs explicitly, even when ordinary control
  commits are omitted from the milestone graph. Keep those HEADs distinct from
  product milestones and exact deployed source revisions. The generated snapshot
  records its generation time; do not create an endless commit cycle merely to
  embed the snapshot's own commit hash.
  Apply these controls as standing instructions without asking the user to repeat
  them or repeatedly restating them in progress updates.

- Use [the project control overview](docs/status/PROJECT-OVERVIEW.html) as the
  shared development and release alignment view. Maintain its canonical
  [version register](docs/status/VERSION-CONTROL.md) and regenerate the same
  HTML after material package, branch, PR, validation or deployment changes,
  before reporting progress. Keep implemented, verified, merged and deployed
  states distinct. Do not turn planned edges into actual Git merge claims.
  Keep an overview of the current development focus, important historical
  deployment commits and important release versions. Show only necessary and
  important Git nodes, connected through verified Git ancestry. All Git nodes
  use one content schema: change title, branch and revision, feature changes,
  verification state and detail links. Deployment cards connect to their exact
  source nodes and use a background distinct from main.
  Mainline, branch and deployment-reference edges use distinct visible styles
  and boundary-aligned arrowheads. Local and cloud cards use distinct backgrounds.
  Node summaries and feature/acceptance records come from the canonical register.
  Keep them aligned with actual project state and affected working-branch copies.
  Prefer a wide layout that shows the full overview without internal scrolling
  on desktop. Preserve readable node content and accurate edge attachment when
  re-layout or scaling changes the graph.
  Prefer shared-foundation and application research nodes to the right of dev,
  while balancing card height, deployment cards and whitespace across both sides.
  Overall visual balance takes priority over a rigid left/right category rule.

- Keep secondary architecture research in the
  [Capstone core capability evolution notebook](docs/superpowers/specs/2026-10-07-capstone-core-evolution-discussion.md)
  as the shared record. It is not the active delivery worklist. Resume this
  discussion when the user starts it; offer a reminder only at a particularly
  important design or implementation boundary. Do not automatically make its
  open questions the next task. Read it before related design work. Ground proposals in
  the actual implementation and practical grid work. Update the notebook with
  conclusions, open questions, and implementation feedback; distinguish
  proposed designs, accepted decisions, and verified behavior.
- Preserve unrelated tracked and untracked user work. Stage only task-owned
  paths. Do not delete or migrate existing main-worktree `var/` data.
- Prefer `rg` and `rg --files` for discovery. Use `apply_patch` for text edits
  and explicit non-destructive commands for filesystem operations.
- Keep `README.md` and `README.zh-CN.md` aligned when shared product facts,
  commands, headings, or references change. Write for readers; move detailed
  procedures into the runbook and volatile status into `docs/status/`.
- An isolated worktree is an implementation aid. Unless the user requests
  branch-only delivery, integrate accepted development changes into the dev checkout
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
Every change must preserve the supported Capstone output contracts, authority
boundaries, and current-run evidence rules.
