# Task 1 Report: Neutral Completion Projection Hook

## Summary

Task 1 is implemented and verified. The Kernel runner now accepts an optional
completion projector, invokes it once after the final committed turn and
before provider shutdown/report publication, and carries its value on
`ApplicationOutcome.completion_projection`.

The projector receives a domain-neutral `CompletionProjectionContext`. Ordinary
projector exceptions are bounded to the
`completion_projection_unavailable` diagnostic and leave the application
outcome completed with a `None` projection. Control-flow exceptions remain
uncaught.

## Files Changed

- `packages/capability-agent-kernel/src/capability_agent/application/runtime_protocols.py`
  - Added `CompletionProjectionContext` and `CompletionProjector`.
- `packages/capability-agent-kernel/src/capability_agent/application/runner.py`
  - Added the constructor hook and outcome field.
  - Invoked the hook after all turn commits and before report publication.
  - Preserved the projection on both completed and failed outcomes.
  - Bounded ordinary projector failures with the existing diagnostic path.
- `packages/capability-agent-kernel/tests/application/test_completion_projection.py`
  - Added ordering and bounded-failure contract tests.
  - Uses `_valid_binding()` and the established runner fixture setup so
    preflight validates the binding.
- `packages/capability-agent-kernel/tests/application/test_runner.py`
  - No content change was required; its `FakeController` and `_valid_binding()`
    helpers are reused by the new projection tests.

## Verification

Focused kernel tests:

```sh
uv run --project packages/grid-agent pytest \
  packages/capability-agent-kernel/tests/application/test_completion_projection.py \
  packages/capability-agent-kernel/tests/application/test_runner.py -q
```

Result:

```text
65 passed in 0.44s
```

Targeted static diagnostics:

```sh
uv run --project packages/grid-agent pyright \
  packages/capability-agent-kernel/src/capability_agent/application/runtime_protocols.py \
  packages/capability-agent-kernel/src/capability_agent/application/runner.py \
  packages/capability-agent-kernel/tests/application/test_completion_projection.py
```

Result:

```text
0 errors, 0 warnings, 0 informations
```

Whitespace:

```sh
git diff --check
```

Result: exited `0` with no output.

## Initial Failure and Repair

The first focused run reached the new tests but failed because the exception
test accessed `outcome.result.core.diagnostic_codes`. `CoreRunResult` exposes
diagnostic references; diagnostic codes are recorded through the runner's
`_record_diagnostic` seam. The test now captures that seam and asserts the
exact bounded code:

```text
completion_projection_unavailable
```

Temporary diagnostic prints were removed. Narrow `Any` casts keep the
intentionally lightweight `SimpleNamespace` fixtures type-checkable without
changing runtime behavior.

## Concerns

- The repository-wide Pyright command still reports 24 pre-existing errors in
  unrelated reporting, hosted API, ledger, network-view, worker, and simulator
  files. The targeted diagnostics for all Task 1 modified source/test files
  are clean.
- The compatibility `test_runner.py` helper file was not edited because its
  existing `_valid_binding()` and `FakeController` fixtures already satisfy
  the new hook tests.
