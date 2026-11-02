# Unified Conversation and Diagnosis Implementation Plan

> For agentic workers: use subagent-driven-development for independent tasks,
> with focused tests and review. The coordinator owns integration and status.

**Goal:** One continuing conversation supports direct answers, native tools and
business tasks, distinct process views and systematic diagnosis.

**Architecture:** Reuse Thread/Work, accepted native bindings, business planning,
registered professional runners and existing conversation components. Select
capabilities from trusted host publication, rather than limiting them by entry type.

**Tech Stack:** Python, the pinned Pi SDK, JavaScript, React and TypeScript.

## Global constraints

- Follow `docs/superpowers/specs/2026-10-25-unified-conversation-diagnostics-design.md`.
- Research quality findings default to recorded gaps and continuation. Grid results
  retain objective Pack/Authority admission. Both permit bounded justified retries.
- Preserve permissions, exact source versions, required persistence, unknown-outcome
  recovery, existing data, messages, composer and product views.
- Work in the initialized `.worktrees/dev-macos-ci` worktree on
  `feat/unified-conversation-diagnostics`. Preserve root metadata edits.
- No cloud/demo deployment or full release gate. Distinguish implementation,
  verification, integration and deployment at each boundary.

## Task 1: Shared native capability selection

Files: `packages/capstone-agent/src/capstone_agent/native_conversation.py`,
`packages/capstone-agent/tests/test_native_session_profile.py` and
`packages/capstone-agent/tests/test_enterprise_normal_chat.py`.

Consumes trusted executor publication and a session preset. Produces the existing
frozen `capstone-native-conversation/1` binding used by command and worker adapters.

- [x] Add a failing test with a current graph-capable executor:
  `binding_for_session(original, 'general-chat') == binding_for_session(original, 'enterprise-research')`.
  Preserve legacy preset behavior when the executor lacks current organization.
- [x] Run `uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_native_session_profile.py -q`.
- [x] Select the shared registered profile when the trusted executor publishes its
  graph and policy contracts. Preserve frozen retries and explicit resource grants.
- [x] Test a direct answer and a tool/research follow-up under the same Work through
  real command/worker adapters. Inspect registered professional context activation;
  retain all grid fact and result admission contracts.
- [x] Commit the verified slice; journal its actual scope.

## Task 2: Built-in systematic diagnosis

Files: new `resources/systematic-diagnosis.mjs` and focused Node tests under
`packages/capstone-agent`; integration in `resources/general-sdk.mjs`,
`native_task_context.py`, `general_pi_server.py` and revision inputs as needed.

Consumes application grants, task identity, observed issues and declared probes.
Produces structured diagnostic receipts and recoverable records, never Authority truth.

- [x] Test grant-controlled parent/child tool publication through the SDK path.
- [x] Test issue evidence, a falsifiable hypothesis, minimal probe, actual outcome,
  failed/not-run checks, working-example comparison and rejected hypotheses.
- [x] Test justified retries, finite time/attempt policy and no budget reset when
  changing an issue label. Exhaustion retains work and returns an actionable gap.
- [x] Persist through existing host receipts/context and test recovery in a fresh
  runtime. Model-writable state is not host-certified evidence.
- [x] Include an on-demand guide; do not depend on personal skill paths. Probe
  execution uses existing authorized tools. Advisory gaps do not become hard gates.
- [x] Run focused Node and Python publication/consumer tests, review and commit.

## Task 3: Process views from actual execution

Files: `packages/capstone-app/src/CapstoneAssistantThread.tsx`, a focused process
projection module if needed and existing conversation/process tests.

Consumes actual graph/tasks, tool calls, public model progress and Attempt state.
Produces thinking, tool-chain or business-task presentation without session keywords.

- [x] Add failing render tests for direct answers, actual native tool chains,
  recorded business plans, live transitions and refresh replay.
- [x] Reuse ActivityItems, TaskStepProcess, ExecutionGraphProcess and current reader
  and fold state. Show public thinking status/summary only; never fabricate content.
- [x] Preserve failure, cancellation, timing and missing historical record states.
- [x] Run focused Vitest and `npm run check`; inspect desktop/mobile browser views.
- [x] Review, commit and journal the verified scope.

## Task 4: Integration and real entry acceptance

- [x] Review the whole change against the accepted design and fix material findings.
- [x] Run affected native runtime, profile, command/worker and App development gates;
  record duration. Do not invoke release verification for development integration.
- [x] Run `make capstone-local-rebuild`; verify roles, readiness and App. Run scoped
  project cache cleanup after validation/use.
- [x] Verify real direct answer, tool work, research follow-up, products, refresh,
  recoverable failure and exhausted diagnosis. Verify registered grid calculation
  against its Authority contract; isolated-runner tests do not prove unified execution.
- [x] Record incomplete grid integration explicitly if any remains. Update canonical
  worklist, review receipt, JOURNAL and recovery checkpoint.
- [x] Update VERSION-CONTROL/INDEX and regenerate/inspect PROJECT-OVERVIEW using
  ui-ux-pro-max. Push a scoped PR to dev, pass its gate and integrate.
- [x] Refresh actual dev control state after merge and verify its real entry point.

## Initial verification

The reused worktree passes doctor and12 native session-profile tests. The approved
design is the full target; presentation work alone cannot close execution integration.
