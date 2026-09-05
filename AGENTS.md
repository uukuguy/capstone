# Repository Agent Contract

This file is the repository-wide instruction source for coding agents. Keep it
compatible with both Codex and Claude Code. `CLAUDE.md` must remain a relative
symbolic link to this file so the two tools read identical instructions.

## Product Contract

This repository builds **Capstone Agent Framework**, a capability-first
framework for evidence-backed applications over authoritative business-domain
systems. `grid-static-analysis` is its first formal pandapower application;
`grid-agent` remains that application's stable compatibility CLI.

Capstone separates a neutral Kernel, Domain Packs, application assembly, and
registered domain authorities. New work must preserve that direction: the
Kernel owns reusable composition, bounded context, trajectory/artifact/replay
primitives, and framework `core`; a Domain Pack owns domain contracts, policy,
guides, executor, projectors, and current-run authority; an application owns
its selected binding and any public compatibility projection. Read
`docs/architecture/capstone-framework.md` before changing these boundaries.

## Four-Layer Dependency Direction

```text
Application -> Domain Pack -> Kernel -> registered Authority
```

Dependencies flow only to the right. Result and evidence references return
through explicit contracts; no layer may import or expose another layer's raw
implementation. A new domain must add a separately installable Domain Pack
through the public Kernel SPI, register its authority, and select that binding
from an application. It must not add domain semantics to the Kernel, couple to
another Domain Pack's state, or turn a compatibility projection into a
framework-wide output requirement.

## First Application Contract: Grid Static Analysis

- The default CLI contract writes exactly one JSON object to stdout with
  `question_id` and `answer_output`.
- Progress, diagnostics, tool events, and warnings go to stderr.
- Numerical and network-specific claims must cross the simulator boundary
  through `gridctl` using `grid-capability/1.0`.
- Never guess losses, voltages, rankings, topology, contingency outcomes, or
  evidence. Use simulator results from the current run.

## Ownership and Trust Boundaries

- `grid-agent` owns question handling, answer composition, Pi/LLM runtime setup,
  continuous context, tracing, reporting, and the final answer envelope.
- `gridctl` and `grid-simulator` own registered network access, deterministic
  calculations, model revisions, result datasets, and evidence.
- pandapower objects, DataFrames, callable names, and raw simulator internals
  stay behind the simulator boundary.
- Observation, projection, validation, and reporting may diagnose execution but
  must not replace simulator truth or block an otherwise valid primary answer.

## Model Capability Boundary

Pi/LLM may use only project-defined grid tools, including bounded
context/decision tools published by the project, and `grid_guide_open`. The
model returns reader-facing final text; `grid-agent` binds current-turn
result/evidence references and commits the answer deterministically.

Do not expose or add model capabilities for:

- shell commands or arbitrary subprocesses;
- generic file read, write, or edit operations;
- arbitrary Python or pandapower function execution;
- raw `pandapowerNet` objects or DataFrames;
- legacy query aliases;
- question-, fixture-, network-, or expected-answer-specific shortcuts.

New capabilities must be semantic, reusable across questions, contract-defined,
allowlisted, and executed through the selected Domain Pack's registered
authority. For the grid application that authority is `gridctl`.

## Evidence and Runtime State

- Offline informational answers do not create run evidence.
- Simulator-backed answers persist current-run results and evidence under
  `runs/<question_id>/`; final claims may cite only references admitted for that
  run.
- `runs/` is ignored operator-visible evidence and validation-report storage.
- `.grid-agent/` is ignored internal authentication, runtime, cache, and session
  state.
- Versioned runtime configuration belongs under `configs/runtime/`.
- Provider credentials stay in environment variables or project-owned ignored
  authentication state. Never place secrets in arguments, logs, committed files,
  simulator environments, or answer artifacts.
- Do not delete or migrate a user's existing main-worktree `var/` data during
  source cleanup.

## Authoritative References

Do not duplicate frequently changing facts in this file. Read the owning source:

| Information | Source of truth |
| --- | --- |
| Published capability coverage | `configs/capabilities/pandapower-3.4.0-static-analysis.json` |
| Simulator package and version pin | `packages/grid-simulator/pyproject.toml` |
| Runtime setup, authentication, commands, and evidence inspection | `docs/RUNBOOK.md` |
| Capability registration and LLM composition architecture | `docs/architecture/pandapower-capability-composition.md` |
| Capstone framework, application, and Domain Pack boundaries | `docs/architecture/capstone-framework.md` |
| Model-facing execution policy | `packages/pandapower-domain-pack/src/pandapower_domain/resources/policy/system-policy.md` |
| Model-facing pandapower guides | `packages/pandapower-domain-pack/src/pandapower_domain/resources/guides/` |
| Structural project state | `docs/status/CURRENT-STATE.md` |
| Active recovery baton | `docs/status/RESUME-NEXT-SESSION.md` |

## Working Rules

- Preserve unrelated tracked and untracked user changes; stage only task-owned
  paths.
- Prefer `rg` and `rg --files` for repository discovery.
- Use `apply_patch` for text edits and explicit non-destructive commands for
  filesystem operations such as creating the approved symbolic link.
- Keep `README.md` and `README.zh-CN.md` aligned whenever shared product facts,
  commands, headings, or references change.
- Keep stable rules here and route volatile details to the authoritative
  references above.

### Isolated worktree setup

An isolated worktree is an implementation aid, not the delivery endpoint. Unless
the user explicitly requests branch-only delivery, integrate accepted changes
back into the main checkout and verify its real application entry point before
claiming completion. Preserve unrelated work and exclude unaccepted changes;
do not delete a worktree containing user data or deferred work to simulate closure.

A new Git worktree does not include ignored local runtime state. Before running
tests that exercise Pi, `gridctl`, or the JavaScript tools in an isolated
worktree, run these commands from that worktree:

```sh
make setup
make install-pi
make doctor
```

`make setup` creates the simulator virtual environment and installs locked Node
dependencies; `make install-pi` creates the ignored, pinned
`.grid-agent/runtime/pi` runtime. A missing managed `gridctl` or Pi CLI is an
environment-setup failure, not evidence of a product regression. Do not copy
ignored runtime/authentication state from another worktree.

## Verification

For behavior changes, run the smallest focused test first and then the supported
repository gates:

```sh
make doctor
make test
make test-e2e
make validate
```

`make validate-provider PROVIDER=<id> [MODEL=<id>]` is optional, requires
explicit provider credentials, and may be billed. Do not run it without that
authorization.

Documentation-only changes must at minimum pass link/symlink checks,
`git diff --check`, and `make doctor`. Preserve the stdout envelope,
simulator-boundary, and current-run evidence contracts in every change.
