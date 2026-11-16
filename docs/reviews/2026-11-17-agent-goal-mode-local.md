# Agent goal mode local verification

Status: local stage-A acceptance passed; dev integration remains open.
Source9dd95faf adds historical resource admission;261c22a1 includes the native response-envelope correction;
product7295e003 binds product references to the current Attempt ledger.
Local canonical rebuild8 passed readiness, API/worker image identity and scoped
cache maintenance. Image d6ceea569426308f8f813c7b813a83f110e6b0dc0d658ee4e5d5967b9b728db4.
Cloud and demo deployments did not change.

## Acceptance correction

Browser review showed the second Attempt reconstructed draft text instead of reading
the original bytes. Earlier completed states prove scheduling only. Rebuilt9dd95faf
closed this gap in threadthr_3c95f96fd5338e7477ba: exactly two Attempts, continue
then complete. The second emitted agent_resource_open and historical_input_delivered.
The original download is157 bytes, SHA256
57d0b274afdf19404a3e2f82fd5e4370534d963ddda0119c19ebccc04a742d0e.
The final report's computed digest, byte count and random marker match the original.
Its resource is resource_a31983c4817c5900000ec6613dc7cc53/version1. Exact receipts:
root ignored runs/agent-goal-exact-resource-20261117/. Vivaldi candidate5174 showed
completed state, persisted count and downloadable final after refresh, reusing the
existing conversation and artifact panes.

## Evidence

- Focused local gate:221 backend tests and44 App tests, plus TypeScript checks.
  PostgreSQL covered concurrent continuation and service reconstruction without
  database skips. Logs: `/tmp/capstone-goal-focused-final.log`.
- Real model and native tools: threadthr_a6e25356c6e5e5d2d651 retained one failed
  Attempt, then completed two successive Attempts without another user instruction.
  Their progress receipts were continue then complete. API restart did not lose
  the goal or create another successor. Goal completed with3 admitted Attempts.
- Downloads after API restart: draft1600 bytes, SHA256
  a8f39d81c64c88c88ae6f3cd92d31e05a5fe1c611681b09c3ad9286ee63ef0d0;
  final4372 bytes, SHA256
  86de18911094194fd2f5868663fb4c9eb9aac636e8fa113ff2e599cb1610553e.
  Both sizes and hashes match saved artifact projections. An original draft version
  remains downloadable even when the later Attempt emits another draft version.
- Worker restart: threadthr_e7e0a61c43b3ed501196 reached ready after its first
  completed Attempt. The native worker was restarted at that durable boundary.
  It admitted one successor and completed the goal with exactly2 Attempts;
  receipts are continue and complete. Evidence in root checkout ignored
  `runs/agent-goal-worker-restart-20261117/`.
- Controls: threadthr_d2ec97c6a45a5cfd04f5 saved control-draft.md before pause.
  Pause reached user_pause with no current Attempt. Objective revision advanced
  to3, resume admitted a new running Attempt, and cancel reached cancelled with
  no current Attempt. Original draft publications remain in history. Evidence:
  `runs/agent-goal-control-20261117/`.
- Budget: threadthr_cda21d4ed80e96aa3d5b retained all failed/interrupted Attempts.
  Its fourth Attempt saved a draft and submitted continue; the goal paused with
  attempt_budget_exhausted. No fifth Attempt was admitted. Evidence:
  `runs/agent-goal-acceptance-20261116/budget-stop-evidence/`.
- CI: PR125 head4de7139b passed focused macOS run43905965730. The earlier run
  43905462039 failed at the scope allowlist before tests; fixed without changing
  the verification scope. This is not a release or cloud acceptance.

## Review limits and corrected failures

Real trials found and corrected gateway identity publication, missing frozen input,
worker wake, forwarding into the actual native instruction, product-ref admission
and the native XML/JSON response-envelope conflict. Failed probes are preserved.
No result has been relabelled as successful. Independent reviewer dispatch failed
because its configured model was unavailable; no independent review pass is claimed.
Local code review and focused tests do not establish arbitrary external-effect
exactly-once execution. Existing unknown-outcome protection remains required.

Stage A adds Agent Work goals. Long-term Control Goals, shared task boards and
external trigger delivery remain later stages and are not claimed by this record.
