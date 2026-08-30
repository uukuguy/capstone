# C.1 Task 5 Report: Generic turn and projection lifecycle

## Status

Complete. The generic Kernel now owns nonce-bound turn lifecycle, binding-aware
answer validation/commit, and binding-qualified capability projection without
knowing domain vocabulary.

## Implementation

- Added `TurnController` and `ApplicationInvocationProjector` public exports.
- Added structured `CapabilityKey` routing; unstructured capability aliases,
  foreign runs/turns, undeclared bindings, authority mismatches, and unadmitted
  references fail closed.
- Kept core-tool results and references opaque to domain projection.
- Added binding-scoped authority, state-adapter, projector-registry, and answer
  policy contracts with sanitized ordinary failures and preserved
  `BaseException` propagation.
- Added nonce/active-turn fencing, replay-safe lifecycle records, and
  binding-qualified `AnswerSubmission` metadata.
- Added `ApplicationContextStore.append_many`, a crash-recoverable transaction
  primitive that stages the complete ledger and snapshot before replacement;
  failed projection/answer commits do not publish partial context or answer
  artifacts.

## TDD evidence

- RED: focused Task 5 tests exposed partial two-event commits, unstructured
  capability routing, explicit-turn masking of a foreign event, and partial
  projection persistence.
- GREEN: all four cases pass using structured routing and the Store transaction
  primitive. Additional RED→GREEN coverage verifies empty/invalid batches,
  interruption after ledger replacement and after snapshot replacement,
  restart recovery, replay/materialized-snapshot equality, and marker cleanup.

## Verification

- Task 5 focused (turns/projector/context store): **36 passed**.
- Application plus trajectory answer tests: **181 passed**.
- Capability-agent-kernel full suite: **311 passed**.
- `make check-package-boundaries`: passed.
- `make validate`: passed (24/24 capabilities, release-ready).
- `make doctor`: passed.
- `make test`: passed (690 grid-agent, 165 simulator, 43 PI-tool tests).
- `make test-e2e`: passed (17 tests).
- `git diff --check`: passed.

## Concerns

None known. Existing controller status/resume bookkeeping changes were left
untouched; the package-local generated `uv.lock` was removed as required.
