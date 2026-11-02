# Research control overhead implementation plan

**Goal:** Remove redundant planner turns from interactive enterprise research while retaining source identity and honest limitations.

**Architecture:** The application-owned research controller admits validated child returns and settles advisory nodes. Domain authority boundaries remain unchanged. The planner chooses new work and delivery; it does not repeat deterministic registration. Strict review mode retains explicit review.

The user has requested record-and-continue behavior and removal of repeated handoff, checks and retries. This plan implements that accepted direction. Do not treat an automatic registration as independent verification or user acceptance.

## Scope and sequence

- [x] In `enterprise-graph-runtime.mjs`, combine validated child settlement, record and advisory assessment into one protected checkpoint. Preserve result refs and declared limitations. Missing checks produce a limited result, never a fabricated pass. Invalid or unknown associations retain their diagnostics and cannot gain trusted references.
- [x] Add controller tests for automatic dependent-task dispatch, missing checks, strict-mode behavior, foreign references and replay.116 controller tests and14 pinned-SDK cases pass (0.95s and8.33s).
- [x] Align tool descriptions and continuation guidance with automatic registration. Overview reads in advisory mode wait for actionable returns, with cancellation; they do not repeatedly return unchanged state for model polling.117 controller and14 SDK tests pass.
- [x] Permit one advisory finish call carrying the model's whole-goal decision and selected delivery. Keep exact review persistence, reference validation and replay; strict mode still requires its explicit review reference.
- [x] Preserve an actual returned producer statement when supplied observation aliases cannot be resolved; omit unknown refs and retain limitations, never convert them into passed checks.
- [x] Distinguish saved returns from host registration in execution records; show return submission duration as such, not full handoff duration. Existing main-chain finalization timing remains separate.180 focused App tests and TypeScript pass. Live visual acceptance remains pending.
- [x] Rebuild locally and verify through a new conversation in the existing Vivaldi tab. Latest7513fc34 trial completed43.426s, with0.175–0.187s registration,0.384s dependent dispatch,10.556s final tail, no failed/retried calls. Large report acceptance and immutable policy text alignment remain follow-ups.

## Evidence to retain

Transport fix0fffe239 passes137 tests. It is locally rebuilt as imagec0226499f93e9c201581a23f201fb5238e993fc61172ff608ad759d72c6ffc48. Real trial attempt_b00880d6422c9d88 has record calls0.437s and0.689s. It also has repeated overview reads and two unavailable bash calls. Summary child ended12:54:27, but the outstanding parent model action started12:54:11 did not return before manual cancellation at12:57:35. Do not assert that this stall is a continuation-wakeup defect without further evidence. The trial is not accepted.
