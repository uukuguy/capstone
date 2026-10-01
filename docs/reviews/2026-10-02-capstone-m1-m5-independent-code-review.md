# Capstone M1–M5 Independent Code Review

> Independent review completed against `main` at `9a07dc8`, then remediation verified at `497338d`.

## Scope

The review covered the M1–M5 implementation, Thread service and Harness boundaries, Web/TUI projections, provider-free validation, tests, and the prior M1–M5 review findings. The reviewer did not modify production code.

## Initial verdict

**REQUEST CHANGES** — 0 Critical, 2 Important, 2 Minor.

### Important findings

1. **A completed Turn could be retried again.** `InMemoryThreadService` and `PostgresThreadService` selected an interrupted/failed/cancelled Attempt without checking for a completed sibling under the same Turn.
2. **The provider-free M5 runner did not persist its summary.** It printed JSON but did not create the report file promised by the M5 plan.

### Minor findings

1. The new provider-free adapter was outside the standard Pyright scope and had 14 targeted diagnostics.
2. `HarnessAttemptRunner` contained two Ruff cleanliness findings: an unused `Any` import and an unused exception binding.

## Remediation

Commit `497338d` addresses all four findings:

- Both Thread service implementations now reject a retry when any Attempt for the Turn has already completed. PostgreSQL target selection is deterministic (`created_at DESC, attempt_id DESC`) under the existing thread transaction lock. A regression test covers failed original → completed retry → rejected retry.
- `validation/run_m5_provider_free.py` writes a bounded `m5-provider-free-summary.json` under each supplied artifact root and announces the path on stderr. The summary includes counts and artifact root metadata; stdout remains the bounded JSON projection.
- `pyrightconfig.validation.json` and `make check-types-validation` cover the provider-free adapter. The validation-specific Pyright run reports zero errors.
- The two Harness Ruff findings are removed.

The earlier M5 synthetic-reference finding is fixed by `9a07dc8`: the provider-free adapter forwards only Authority-declared `result_ref`, `result_refs`, `evidence_ref`, and `evidence_refs`. Evidence-only topology results and result-only derived queries are accepted when the Authority declares those shapes; no payload hashes are invented.

## Verification after remediation

- `make validate-thread-m5-provider-free`: passed for pandapower and PyPSA; persisted summaries exist for both rows.
- `PYTHONPATH=. uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_thread_attempts.py -q`: 19 passed.
- `PYTHONPATH=. uv run --project packages/grid-agent pytest validation/test_m5_matrix.py validation/test_m5_provider_free.py -q`: 10 passed, 1 skipped.
- `make check-types-validation`: passed, 0 errors.
- Targeted Ruff checks: passed.
- `git diff --check`: passed.
- `make doctor`: passed.

Repository-wide `make validate` remains blocked by the pre-existing protected `packages/grid-simulator` baseline mismatch. `make capstone-local-rebuild` remains environment-blocked when the Docker/OrbStack socket is unavailable. These are recorded in the M5 verification and recovery documents and are not silently treated as passed.

## Final recommendation

**APPROVE after remediation**, subject to the documented environment gates. Every future M stage must dispatch an independent code review before the stage is declared complete.

## Follow-up review

An independent follow-up review against remediation commit `497338d` returned **APPROVE**. It confirmed the retry guard, persisted provider-free summaries, validation Pyright gate, and Harness cleanup. PostgreSQL integration execution remains environment-blocked because no local PostgreSQL is available at `/tmp:5432`; the SQL path was reviewed statically.
