# Cloud-dev automatic idle sleep

The user requires no manual start: an unused cloud-dev stage sleeps, and an
incoming visit wakes it. The earlier manual suspension is not acceptance of
that requirement. Demo stays unchanged while this work is validated.

The accepted goal is a very small idle bill with reliable wake, rather than
zero cost at any price. Evaluate the entire stage: idle resource charges,
cold-start latency, first-command success, state safety and operational burden.
Use Railway Serverless for API and family workers. Keep the small static App
running so the first HTML request cannot expose a cold-start gateway error;
the App can then recover bounded API cold starts. Start with PostgreSQL
running at its measured idle footprint to avoid serial database cold starts.
Evaluate database sleep only if its residual cost is material and TCP wake is
reliable. Report retained database and storage cost explicitly. Do not call
process-idle memory free or a Serverless toggle proof of actual sleep.
Retain the volume and bucket.
Pre-change Railway samples from 2026-10-08 05:00–07:40 UTC show mean App memory
0.024 GB and PostgreSQL memory 0.047 GB. At the published $10/GB/month rate,
their memory-only continuous-use estimate is about $0.71/month. This excludes
CPU, storage, active compute, transfer and the account subscription. Database
CPU before the fix averaged 0.107 vCPU; measure again without worker polling.
These samples are not proof of an idle bill or of sleeping services.
Traffic from a visitor wakes the App/API; API startup already probes workers.
Page entry streams bounded, truthful component status through
`GET /api/v1/workbench-preparation` (NDJSON,
`capstone-workbench-preparation/1`). It first shows service connection, then
session/history readiness, then each family tool as its parallel wake finishes.
Never publish credentials, private origins, database internals or fake percent
completion. A failed component retains progress and a retry action. The
public projection authorizes no command or Provider access. Older hosts without
this endpoint keep the existing access bootstrap.
Page entry waits for database readiness and authenticated wakes of all workers
before returning Thread access. Until this succeeds the App shows a single
preparation state and offers no model controls or command input. An open
following event stream keeps workers warm every two minutes only within a
bounded activity window. Page-open and SSE heartbeats are not user activity.
After 15 minutes without keyboard, pointer, touch or scroll activity and with
no active task or unresolved submission, stop the subscription without
unmounting the workspace. Hidden pages release the subscription immediately;
this does not cancel server work. History, draft, graph and reading position
remain visible. Focus/visibility restoration or renewed interaction starts
readiness checks before command controls reopen. Recovery uses a small local
progress surface rather than a full-screen blocker. Preserve focus without
scrolling on readiness. Failed preparation keeps commands gated and offers
retry. No independent background keepalive runs
after the activity window. Active execution keeps its lease and cannot be
evicted for idle savings. First-page waiting has a bounded three-minute abort
and offers a retry on failure. Existing drafts and histories stay intact.

This activity policy follows the researched distinction between browser
presence and actual use; see the [commercial patterns research](2026-10-08-cloud-idle-commercial-patterns.md).
Accepted Thread work must send authenticated wake signals to both family
workers. Each worker broadcasts a signal to its legacy and Thread schedulers.
An idle Thread scheduler must not poll the database. It may sweep its bounded
process cache locally. It scans at startup, drains queued work after wake,
retains retry/recovery behavior after errors, and stops cleanly. Wake signals
received during a task must not be lost. Active tasks retain lease renewal.

Read-only App requests tolerate bounded cold-start 502/503/504 and transport
failures. Non-idempotent requests are not blindly replayed. Command retries
retain their existing command and idempotency identities. Storage and already
incurred charges remain; actual idle/wake state and resource metrics, not just
a configured toggle, gate cloud acceptance.

All backend roles use one tested commit. Local rebuild and integration gates
precede cloud changes. Cloud-dev is resumed with Serverless enabled and kept
available after validation. Development push triggers remain disabled to avoid
unrelated builds while testing sleep. No demo mutation or Provider call is
required. A cloud-dev acceptance tag follows complete stage validation.

## Cold-start correction from cloud verification

The first full browser wake of revision `2ef57c8` took 125.862 seconds. Input
admission remained safe, but this delay is rejected as the UX acceptance result.
Startup waited for family workers serially and each backend repeatedly ran
Authority catalog exporters that load every registered model.

Generate the bounded registered catalog documents once during the image build
using the same fixed Authority exporters. Bake a read-only snapshot bound to
the installed source, locks, versions, assets and build recipe. Its metadata
payload participates in the runtime artifact identity. The launcher derives
the identity; the loader rejects missing, malformed or mismatched snapshots.
Plain CLI paths without a hosted artifact identity retain Authority export.
Wake both family workers concurrently. Keep actual family availability probes
and command admission checks; an installed catalog is not worker readiness.

This snapshot covers only the immutable registered catalog for the image. It
does not cache user model changes, current Context state, calculation results
or evidence, and does not bypass exact revision checks when a model is opened.
Repeat actual sleep and browser wake after the correction before acceptance.

Independent image builds exposed random Kerber example generation. The
pandapower Authority must seed registered factories by their stable factory
identifier, serialize construction and restore the previous random state.
Registered fixture revisions must match across independent exports and model
opens. Existing stored model artifacts and historical evidence stay intact.
