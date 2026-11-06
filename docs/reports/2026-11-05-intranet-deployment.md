# Intranet development update

The intranet runs source snapshot `2b6dd8a3c55ad8ef1a72db6c81f181ab9c5b560a`.
The four roles are healthy and `/health/ready` returns `ready`.
Task acceptance failed. No acceptance tag was created.

## Source and images

This snapshot includes the existing uncommitted development work. It is retained
at `refs/capstone/intranet-candidates/20261105-fixed`; dev remains `6c55e6ee`.
The normal index was not changed. No CI, main integration or cloud update ran.

| Role | Image SHA-256 |
| --- | --- |
| API and worker | `776c30a5cf626f3998d7e62ab81e4e31f1e1b71e15a1ff69af642dddaa2770c4` |
| Native executor | `3c7795200b421dc37f9bf3474a7cab953c828d046e82350c2250f7ddb4313f07` |
| App | `795e8a6253adfdee7a0427fad5c9bcb4123ab281b2905813737e7c74bff89953` |

The initial snapshot73de5adb failed worker startup. The old service was restored.
The new recognition path required an adapter from the registered workbench model
profile to the existing Provider contract. A regression test failed before the
fix; all six runtime tests then passed. Private HTTP targets come from the
registered profile. Generic endpoint validation was not relaxed.

The fixed backend was built on the transferred amd64 backend, with the snapshot's
package sources. Its Authority catalog was rebaked for the new source identity.
Build-created uv cache ownership was restored before startup. Both backend roles
use the same final image. Native source inputs were unchanged by this repair;
its source label was updated. App assets were rebuilt with the new snapshot ID.

## Checks and limits

- Focused backend checks:131 passed,28 skipped. Runtime repair:6 passed.
- App checks:271 passed,1 failed. The failing history fixture includes diagnostic
  events in an API that accepts public events only. It remains unresolved.
- App type checks and production build passed. Staging needed the shared capacity
  configuration and existing hast type declarations. A test selector was typed
  as HTMLDetailsElement; this changed no App runtime behavior.
- Fixed local canonical rebuild:API/worker image8eb5c353, readiness passed.
- Doctor and whitespace checks passed. Scoped local build-cache cleanup ran.
- Remote API,worker,native executor and App are healthy with exact image parity.
- Browser tools had no connected browser. No visual acceptance is claimed.

Real thread `thr_5a191f6f135269742038` failed with
`intent_deadline_exceeded`:the model did not submit its decision within120 seconds.
The CSV was not produced; download,continuation and restore acceptance did not run.
No automatic replay was made. Keep the120-second deadline.

This is a deployed development candidate, not an accepted release. The running
candidate remains available for diagnosis. No acceptance tag names this update.

## Data and recovery

Target:http://192.168.72.63:5173/,Compose project `capstone-intranet`.
No active attempts existed at either switch. PostgreSQL,object storage and managed
resource volumes were preserved. Existing Provider credentials were not changed.
The temporary environment-default experiment was restored before final activation.
Management remains disabled. Other gateway and Kubernetes services were not changed.

Backups:`private/backups/release-2b6dd8a3/` and
`private/backups/pre-2b6dd8a3/ledger.dump` on the server. The earlier6c55e6ee images
and configuration remain available for rollback. Never restore an old database
dump over newer user data for a source rollback.

Evidence:`.capstone-agent/intranet-20261105/` and
`runs/intranet-release-20261105/events.json`. Server build inputs are under
`/home/dmdba/capstone-intranet/releases/2b6dd8a3/`.
