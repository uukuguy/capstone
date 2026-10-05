# Live Session Checkpoint

> Updated: 2026-10-05 12:05 CST. **Session remains active — not a final handoff.**

## Current work

M11 implementation and cloud HTTP acceptance passed. Real cloud Web acceptance
remains pending because Chrome control cannot connect. Do not mark M11 complete.
The user approved inline execution and cloud-dev deployment. Provider execution
and user-trial promotion remain outside the authorization.

## Verified state

- Main contains runtime source `595e602` and additional tests `e128789`.
  No runtime source changed during remote acceptance.
- Full `make check-release` passed, including E2E 39 + 3, App 171,
  coverage 24/24, installed-package checks and source setup.
- Disposable PostgreSQL: 19 passed. Each real Authority environment:
  2 passed / 1 opposite-family skip. Focused App replay/focus: 32 passed.
- Local rebuild, matrix 5/5, both public cases, and normal-mode restoration passed.
- Remote private preflight and Thread matrix: 5/5 passed.
  Receipt: `runs/capstone-m11/remote/m11-750fa3caf36f4202.json`.
- Both remote legacy cases passed in validation mode and again in normal mode:
  `runs/capstone-m11/remote/legacy-ff2198411ada.json` and
  `runs/capstone-m11/remote-normal/legacy-08a7ec68d8dd.json`.
- Before worker restart, read-only DB counts showed zero active Attempts and
  sessions. After restart and after normal restoration, the Thread snapshot,
  53 events, reports/results/evidence and six network views match:
  `runs/capstone-m11/remote/retention-{before,after,normal}.json`.
- Both private workers report `normal`; API validation endpoint returns 404.
  API/App readiness, both catalog families, public Provider denial and public
  Thread creation/read denial passed. No Provider work was submitted.
- Temporary SSH registration/key files removed; disposable PostgreSQL
  `capstone-m11-test-postgres` stopped. No application data was deleted.

## Final cloud deployment

Target: `capstone-cloud-dev`, project
`5eecde6b-fec2-40d2-8b26-427025b02b96`, environment `production`
(`5afd6aeb-07a6-4320-92e9-4bf193a442cb`).

| Role | Normal-mode deployment |
| --- | --- |
| API | `c7fe98e9-3e92-47ab-b826-2ca4af09f758` |
| pandapower worker | `8aa5840f-4d26-4477-a2d3-e120032a3786` |
| PyPSA worker | `3e8348ab-31dc-4984-be26-c9775ad864c1` |
| App | `1c428e30-4f1c-4308-87cd-962b4fc337e7` |

All use source `595e602`; API reused the exact verified image. The manifest
`runs/capstone-m11/deployment.json` records full hashes, digests and rollback
settings. Validation opt-in is empty on all backend roles. Local mode is normal.

## Next action: browser acceptance only

The user approved opening a new Chrome window; it opened, but tab listing
still timed out. Extension/native-host diagnostics passed. Supported recovery
requires plugin repair through the client's UI. Do not bypass Browser with
shell/AppleScript or a separate browser automation surface.

The user asked what “Settings → Computer Use” means. Official documentation
places it in the ChatGPT desktop application. An async question asks whether
the current client is Orca, ChatGPT desktop, or Codex. Give instructions for
the actual client; do not assume ChatGPT menus exist in Orca.

After connection recovery, open:
`https://capstone-app-production-83ef.up.railway.app/?thread=thr_2353b828e0025c28f556`.

Use the current cloud-development operator credential through the password
field. The local `.capstone-agent/auth/railway-operator.token` is stale for
this target; read protected cloud API configuration in memory without printing
or copying credentials. Verify result cards, matching current diagram,
refresh/reconnect and legitimate focus; check history behavior where available.
Use existing committed history only. Normal-mode submissions can invoke a
Provider and are not authorized. Do not assert execution recovery of old
process-local Authority Contexts after worker restart.

## Owning records

- Plan: `docs/superpowers/plans/2026-10-05-capstone-m11-cloud-federated-thread-implementation.md`.
  Task 5 Step 2 and the Web portion of Step 3 remain open.
- Verification: `docs/reviews/2026-10-05-capstone-m11-cloud-verification.md`.
- Main has no pending runtime changes. Documentation checkpoint is being
  committed; append the commit to JOURNAL immediately.
- Preserve `capstone-demo`, Provider credentials, user work and main `var/`.
