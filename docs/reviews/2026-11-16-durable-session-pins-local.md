# Durable session pins: local acceptance

Product source: `981ddc3dd25b98c05962699dfb241212b1d4176e`, preceded by
`dbdb3202`. Owner: capstone-agent/capstone-app. Destination: dev. CI, PR and
integration are pending separate approval; cloud/demo/main remain unchanged.

## Cause and recovery

The localhost browser origin held an empty pin list. The127.0.0.1 origin held ten
pins and an older six-pin subset. All ten referenced Threads existed. Pin state
was stored only in origin-scoped localStorage, so switching App entry addresses
hid the original selection. The previous tab migration did not cover origins.

The existing Vivaldi tab loaded the corrected127.0.0.1 App and automatically
imported the ten originals into PostgreSQL. The same tab then opened localhost:
all ten pin links appeared there too. No Thread was recreated, deleted or
archived. Original browser records and pin-only recovery evidence remain intact.

## Persistence and failure checks

- Focused gate:86 backend/interface/scope checks and83 App checks passed, with
  TypeScript validation. The backend includes real disposable PostgreSQL tests:
  eight concurrent clients retain every pin, a new service instance reads them,
  explicit unpin survives late legacy import, and empty state retains revision.
- Workspace isolation and public-demo denial passed. Cleanup refuses a pinned
  Thread at its backend deletion boundary. Malformed legacy records are retained;
  valid records can still import without replacing the authoritative list.
- Failed reads retain confirmed state. Lower-revision responses cannot replace
  newer state. Failed writes retain intended values. A lost write response can
  be retried without toggling the saved value in reverse.
- API restart preserved all ten original identities and revision1. Independent
  localhost/127 API reads returned the same state. Final canonical rebuild also
  preserved the exact set. No model/Provider task was needed for this repair.
-272 governance checks passed,3 existing conditions skipped. Doctor, whitespace
  checks and live-snapshot2 Python/3 Node checks passed.

Independent read-only review found one write-retry defect in the first candidate.
The intended-operation replay regression failed before the correction, then
passed. A second review of the corrected source found no actionable regression.

## Runtime identity

`make capstone-local-rebuild` ran for the final product source. API and all three
workers use image
`47cc7638098bfc89648b1f58296f781fdecc8d60c4a51dd7ed91a9f0ff822bc8`.
Readiness and source-file hash comparison passed. The App runs on the initialized
candidate checkout at5173. Scoped build-cache maintenance is part of the rebuild.
Operator receipts, screenshots, review logs and original pin evidence are in the
ignored `runs/session-pins-investigation-20261116/` directory.

The current no-login stage shares pins within a workspace. Future account-scoped
preferences require the accepted user/workspace identity contract; this repair
does not introduce a user identity or merge deployment databases.
