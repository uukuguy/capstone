# GitHub Issue Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or inline task execution. Track each task below and review before integration.

**Goal:** Deliver simple screenshot feedback, Chinese AI communication and controlled background repair-to-PR using the accepted dev/demo lifecycle.

**Architecture:** A Python repository tool owns GitHub input, trusted policy, durable task leases and bounded model requests. The model supplies structured classification and patches; secret-free Docker checks validate candidate code. A separate GitHub adapter publishes permitted comments, branches and PRs, with no merge or deployment permission.

**Tech Stack:** Python 3.12 standard library, SQLite, GitHub CLI/API, OpenAI-compatible vision/chat adapter, Docker and GitHub Actions.

**Latest user steering:** Deliver command-driven assisted operation first. The current AI session performs reasoning and passes structured decisions/patches to tools; no independent paid model calls, automatic polling/repair/comments or schedule activation. Timer and autonomous executor are deferred. Manual local CLI and readonly workflow_dispatch must work without a model key. Any optional model adapter remains disabled. Do not implement or activate a permanent daemon to satisfy the earlier draft.

**2026-10-10 acceptance:** Reviewed tooling is integrated into local main `b145cda`. Source tests, real App sandbox probes and readonly intake pass. The checklist below includes live publication and recovery requirements; it is not marked complete while the independent App, formal operator image/configuration and remote CI remain unavailable. See [verified scope and pending operations](../../reviews/2026-10-10-issue-workflow.md). No product feedback is declared repaired.

## Global Constraints

- AI identity: 小石 · Capstone AI, using a separate verified GitHub App for writes. Never inherit personal publisher credentials. Development-origin Issues are authorized and follow the same workflow; creating an Issue does not start repair.
- Default unspecified user environment: cloud-demo; explicit user environment overrides it. Screenshot version is separate evidence.
- Public communication is Chinese. Screenshot plus one sentence, or screenshot alone, is valid intake; preserve original content.
- Never execute Issue text as commands, expose secrets, alter business data or reuse ignored authentication in repair workspaces.
- Only maintainer commands authorize repair; approved queue policy can authorize scheduled low-risk work. Default PR-only, no auto-merge or deployment.
- One repair at a time, bounded retries/budget, durable recovery and reconciliation of uncertain external writes.
- Shared API/worker/App changes require both real local entrypoints before acceptance; missing gates remain pending.
- No billed product Provider validation. Background model calls remain disabled until an explicit budget is configured.

## Task 1: Intake, policy and durable queue

Files: `tools/issue_automation/{__init__,policy,store,github,model}.py`, `configs/development/issue-automation.json`, `tools/tests/test_issue_automation.py`.

Interfaces: policy validates trusted config; GitHub reads issues/comments/permissions and performs reconciled writes; SQLite records task input/policy identities, leases, budgets and action receipts; model returns validated Chinese triage objects.

- [ ] Add failing tests for cloud-demo defaults, explicit overrides, minimal/screenshot input, command authorization, duplicate jobs, stale lease recovery and budget refusal.
- [ ] Run `python3 -m pytest tools/tests/test_issue_automation.py -q`; verify missing module/behavior failures before implementation.
- [ ] Implement bounded JSON transport, current-session structured decisions and private SQLite storage; include `task_id`, `input_hash`, `policy_sha`, `source_sha`, `state`, `lease_until`, `action_key` in receipts.
- [ ] Test unsupported commands, unknown versions, bot-event exclusion, sensitive-output rejection, private URL/redirect refusal and uncertain-write reconciliation.
- [ ] Commit only tool/config/test paths; review task evidence.

## Task 2: Repair and lifecycle orchestration

Files: `tools/issue_automation/{repair,service,cli}.py`, remaining focused tests under `tools/tests/`.

Interfaces: `python3 -m tools.issue_automation.cli` supports doctor, scan, triage, fix, retry, pause, status, daemon and release-status. Repair consumes bounded source context, returns validated text-file replacements/patches, validates in isolated Docker and creates a draft PR linked to its Issue. Commands never auto-deploy.

- [ ] Add failing integration tests for triage→needs-info→new reply→ready→repair→PR, pause, failed tests and restart recovery.
- [ ] Implement isolated source export, path/size checks, bounded source selection and model patch rounds; execute candidate tests with no host secrets or business mounts.
- [ ] Reconcile existing branches/PRs; never call failed/absent checks successful. Mark real local validation pending in draft PRs.
- [ ] Implement exact-commit stage acceptance and Issue release status without bypassing verified tags or asserting user confirmation.
- [ ] Run focused suites; verify loopback fake model/GitHub endpoints and real local Git/Docker behavior without paid calls.

## Task 3: Triggering, developer entrypoints and governance

Files: `.github/ISSUE_TEMPLATE/user-feedback.md`, `.github/workflows/issue-automation.yml`, `Makefile`, `docs/architecture/capstone-development-lifecycle.md`, `docs/RUNBOOK.md`, aligned README pair and status register/index.

- [ ] Reduce user template to title/short description with optional image; no maintainer form shown to users.
- [ ] Add readonly workflow_dispatch status entrypoint using trusted default-branch source; no scheduled jobs or automatic Issue/comment processing in the first release. Configure no deploy/merge workflow permission.
- [ ] Add `make issues-doctor`, `issues-scan`, `issues-create`, `issues-triage`, `issues-begin`, `issues-complete` and `issues-status`; persist private SQLite/task receipts under ignored project state, no secrets in arguments/logs. No daemon entrypoint activates work.
- [ ] Link one governing procedure from lifecycle; distinguish implemented, configured and active features.
- [ ] Register existing history/answer/response-scale/wake feedback as Chinese Issues, preserving explicit local-demo scope where the user supplied it.

## Task 4: Review, integration and operational validation

- [ ] Run focused automation tests, existing affected Makefile/verification checks, `make doctor`, link/symlink checks and `git diff --check`.
- [ ] Review scope, credential isolation, lease recovery, CI trigger identity and dev/demo acceptance boundaries; fix material findings.
- [ ] Integrate accepted feature branch into main without staging unrelated dirty documents; synchronize management references into affected branches without changing frozen baseline tags.
- [ ] Push exact implementation branch and accepted main only after gates; publish scoped labels/Issues and verify remote identities.
- [ ] Verify current-session command intake, structured judgment, workspace and publication paths without external model calls. Record actual operational limits; no daemon/schedule/paid model activation in this release.

Do not mark complete merely because workflows and files exist: verify the command flow, remote intake, task recovery and absence of automatic execution, and report any unavailable App identity or candidate validation capability explicitly.
