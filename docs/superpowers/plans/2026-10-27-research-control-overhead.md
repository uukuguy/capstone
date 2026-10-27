# Research control overhead implementation plan

**Goal:** Remove redundant planner turns from interactive enterprise research while retaining source identity and honest limitations.

**Architecture:** The application-owned research controller admits validated child returns and settles advisory nodes. Domain authority boundaries remain unchanged. The planner chooses new work and delivery; it does not repeat deterministic registration. Strict review mode retains explicit review.

The user has requested record-and-continue behavior and removal of repeated handoff, checks and retries. This plan implements that accepted direction. Do not treat an automatic registration as independent verification or user acceptance.

## Scope and sequence

- [x] In `enterprise-graph-runtime.mjs`, combine validated child settlement, record and advisory assessment into one protected checkpoint. Preserve result refs and declared limitations. Missing checks produce a limited result, never a fabricated pass. Invalid or unknown associations retain their diagnostics and cannot gain trusted references.
- [x] Add controller tests for automatic dependent-task dispatch, missing checks, strict-mode behavior, foreign references and replay.116 controller tests and14 pinned-SDK cases pass (0.95s and8.33s).
- [ ] Align tool descriptions and continuation guidance with automatic registration. Prevent repeated status polling from creating model work when there is no decision to make.
- [ ] Make automatic receipt, remaining limitations, main-chain work and final response timing visible in execution records. Do not label a locally saved return as completed host admission.
- [ ] Rebuild locally and verify through a new conversation in the existing Vivaldi tab. Measure child completion to dependent dispatch and final answer separately. Stop abnormal idle runs.

## Evidence to retain

Transport fix0fffe239 passes137 tests. It is locally rebuilt as imagec0226499f93e9c201581a23f201fb5238e993fc61172ff608ad759d72c6ffc48. Real trial attempt_b00880d6422c9d88 has record calls0.437s and0.689s. It also has repeated overview reads and two unavailable bash calls. Summary child ended12:54:27, but the outstanding parent model action started12:54:11 did not return before manual cancellation at12:57:35. Do not assert that this stall is a continuation-wakeup defect without further evidence. The trial is not accepted.
