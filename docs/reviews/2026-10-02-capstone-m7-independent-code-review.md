# Capstone M7 ResultProjection Independent Code Review

## Review scope

This review covers the M7 ResultProjection contract, Domain Pack projection
bridge, Thread terminal admission and persistence, event replay, and Web result
and topology focus changes in the working tree on 2026-10-02.

## Initial independent review

The independent review requested changes for six findings:

1. Pyright errors in the Kernel projection path.
2. Unbounded result projection append in the in-memory and PostgreSQL stores.
3. Terminal admission not passing authoritative diagram identity to the
   normalizer.
4. Projector failures propagating into Attempt failure instead of becoming a
   typed unavailable projection.
5. Snapshot event replay failures being treated as a successful live load.
6. Web row focus claiming success for an element absent from the current
   diagram.

## Remediation

All six findings were addressed in the same working tree:

- Kernel event/result values are narrowed before iteration and normalization;
  changed-file Pyright reports zero errors.
- `MAX_RESULT_PROJECTIONS = 64` is shared by the Python protocol, both Thread
  persistence adapters, and the Web event replay projection. Immutable terminal
  events retain their own bounded projection payload; snapshots retain the
  recent catalog window.
- Domain projectors emit an internal diagram-element identity declaration.
  Terminal admission validates element refs and overlay targets against that
  declaration and strips the internal field before the public event/snapshot.
  Element-bearing projections without this declaration are rejected.
- Domain projector calls and per-projection normalization are guarded. An
  invalid or unavailable projector yields a bounded `status: unavailable`
  projection tied to the admitted result/evidence refs, so the already admitted
  answer remains visible.
- Initial event replay is strict: malformed, incomplete, non-contiguous, or
  cursor-inconsistent history raises and leaves the client unavailable instead
  of advancing silently to the snapshot tail.
- Web focus validates the element against the current diagram before writing
  focus state and shows `当前电网图中没有这个元件，无法定位` when validation fails.

## Initial remediation verification evidence (historical)

- Full Capstone Agent suite: `364 passed, 29 skipped, 1 warning`.
- Pandapower Domain Pack projection tests: `5 passed`.
- Web suite: `156 passed`; TypeScript check and production Vite build pass.
- Pandapower provider-free matrix: `5/5` passed.
- PyPSA provider-free matrix: `3/3` passed, including namespaced result and
  evidence references.
- `make doctor`, Ruff, Pyright on changed Kernel/service modules, and
  `git diff --check` pass.
- `make capstone-local-rebuild` rebuilt the current source and reported healthy
  API, worker, PostgreSQL, object storage, and App processes.

The seven PostgreSQL unit cases were also attempted with the local Compose
credentials. They could not connect from the host because Compose does not
publish the database port; rerun them from inside the Compose network or with
an externally reachable test DSN before claiming direct database execution
coverage.

## Review disposition

**Initial independent review: REQUEST CHANGES.**

The six requested changes are implemented and verified above. The database
execution limitation is recorded explicitly; it is an environment limitation,
not a silently skipped product assertion. Future changes to the ResultProjection
contract or Thread persistence must trigger another independent review before
the next milestone is closed.

## Follow-up independent review — 2026-10-03

The follow-up review re-checked the current working tree after the initial
remediation. It found and accepted two additional fixes:

- Snapshot restoration now truncates a live event page at the captured
  `last_event_seq`. Events committed after the snapshot are left for the normal
  catch-up pass instead of making a valid restore enter the offline state. A
  concurrent-page regression test covers this race.
- `PandapowerResultProjector.project_admitted` always uses the per-result
  evidence tuple admitted for the current run. An empty or stale authority hint
  can no longer hide that evidence; missing current-run evidence remains a hard
  projection failure. A regression test covers an empty authority hint.

Follow-up verification:

- Web: `157 passed`; TypeScript check and production Vite build pass.
- Capstone Agent: `364 passed, 29 skipped, 1 warning`.
- Pandapower Domain Pack projection: `6 passed`.
- PostgreSQL Thread persistence: `10 passed` against a temporary isolated
  PostgreSQL 17 container.
- Provider-free matrices: pandapower `5/5`, PyPSA `3/3`.
- `make doctor`, changed-source Pyright/Ruff, `git diff --check`, and
  `make capstone-local-rebuild` pass; the rebuilt API/worker image reports
  digest `sha256:763849bfaf009ccd73e6a280eae4534e7cbbc12401ebc0ce10dfa9a527d7d170`.

## Final disposition

**FOLLOW-UP PASS.** M7 may close for the stated demo-stage scope. The review
record remains intentionally two-part: the initial review requested changes,
and the follow-up accepted the corrected working tree.
