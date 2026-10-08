# Railway topology

Railway hosts two separate Capstone stages: the existing `capstone-demo` project
serves user trials, while the `capstone-cloud-dev` project validates
cloud changes. Local Compose remains the high-frequency development loop. Railway
environments can also represent the two stages inside one project, but separate
projects provide the clearest billing, credential, data, and access boundary.

## Environment topology

| Stage | Railway target | Source trigger | Public access | Data and credentials |
| --- | --- | --- | --- | --- |
| Cloud development | `capstone-cloud-dev` | `main` after local gates, deployed deliberately | Open Thread workbench for function validation, selected explicitly | Dedicated PostgreSQL, bucket, operator token and domains; existing Provider key permitted during the current function-validation stage |
| User trial | `capstone-demo` | Release tag or explicit promotion of a verified revision | Registered scripted cases; open Thread workbench when explicitly selected for promotion | Dedicated PostgreSQL, bucket, operator token, Provider key, and domains |
| Local | Docker Compose plus Vite | Working tree changes | Local machine or LAN | Ignored local database, RustFS bucket, and runtime state |

Each Railway stage contains one PostgreSQL service, one private Railway Bucket,
one API service, registered family workers, and one static App service. All backend
roles must use the same tested image or source revision within a stage.
Workers are selected by execution family, such as pandapower or PyPSA. A worker
can host several Domain Packs for its family. Installing a Domain Pack does not
create another service or a dedicated process.
The two stages never share `DATABASE_URL`, artifact storage, operator tokens
or public origins. Provider credentials are separate by default; the current
user-approved function-validation stage permits an existing Provider key.
`VITE_API_ORIGIN` contains only the selected API origin.

The App header shows its package version and source commit. Before uploading an
exact Git release archive, write that archive's full commit to
`packages/capstone-app/build-revision.txt`. This public build receipt contains no
secrets. Verify the header commit against the deployed source before acceptance.
The tracked `development` marker lets local Vite read Git directly; do not accept
a hosted release that shows the development marker.

Match each App upload to its existing build root. Cloud-dev selects
`packages/capstone-app` as its service root, so upload the full release archive.
Demo has no service root override, so upload the archive's
`packages/capstone-app` directory. Both use the App Dockerfile. Upload backend
services from the full archive root. Check the candidate image and actual App
page before acceptance; do not assume the two stages share build-root settings.

Set `CAPSTONE_THREAD_OPEN_ACCESS=true` on the cloud-development API after local
App verification. The App reads `/api/v1/thread-access` and opens directly,
with no login and no browser token. Provider keys remain on the backend workers.
Other deployments keep their current access mode until explicitly configured.

The existing public topology remains the user-trial topology. Set the API start
command to `/app/deploy/entrypoint.sh api` and the Worker start command to
`/app/deploy/entrypoint.sh worker`. Keep one Worker replica initially. The Worker
has no public domain. Set its internal HTTP health check path to `/health` and
its `PORT` explicitly. The worker's `CAPSTONE_WORKER_WAKE_URL` port and the
API's worker wake URL must match that effective runtime port. The cloud-dev
worker currently uses `8080`; local Compose explicitly uses `8766`. Do not
infer the runtime port from the Dockerfile default: Railway can inject `PORT`.
Set the API health check path to `/health/ready` and expose
its generated HTTPS domain. A local SciGRID run peaked near 1.1 GiB; allow
headroom and check Railway metrics before setting a Worker memory cap.

`CAPSTONE_HOSTED_APPLICATION` defaults to `pandapower` for compatibility. A
single-family stage pairs the API and worker with the same application.
The unified `capstone` API uses separate pandapower and PyPSA workers sharing
the stage ledger. Workers lease only their pinned implementation family.

## Federated workbench roles

Validate these roles in `capstone-cloud-dev`, then promote the same verified
source and roles to `capstone-demo` after human acceptance:

| Service | Application | Start command | Health |
| --- | --- | --- | --- |
| `capstone-api` | `capstone` | `/app/deploy/entrypoint.sh api` | `/health/ready` |
| `capstone-worker` | `pandapower` | `/app/deploy/entrypoint.sh worker` | `/health` |
| `capstone-worker-pypsa` | `pypsa` | `/app/deploy/entrypoint.sh worker` | `/health` |

Set `PORT=8080` for all backend roles. Give workers no public domains. Keep
one replica per worker. Cloud-dev workers use authenticated event-driven wake
for Thread and compatibility work, so an empty queue does not poll PostgreSQL.
Enable Serverless only with this tested worker revision. Wait for both new
worker deployments to succeed and pass
health and artifact checks before deploying the API. Its catalog refreshes
family availability on each catalog or admission check. Use the two private origins from
[`cloud-dev.variables.example`](cloud-dev.variables.example).

The shared Docker build bakes registered Authority catalog metadata, bound to
the installed runtime artifact, so waking does not reload every registered
model. The snapshot payload participates in artifact verification. A missing
or mismatched snapshot blocks startup; it is not a cache of mutable models,
results or worker health. Rebuild the local lane and all backend roles together
when changing this build recipe.
The existing demo retains port 8766; its worker origins use that same port.
The [demo checklist](demo.variables.example) selects the same runtime profile
with stage `user-trial`. A promoted open workbench has no browser login gate;
its older public demo credential still permits scripted cases only.

Normal local Compose and cloud development select
`CAPSTONE_RUNTIME_PROFILE=capstone-workbench-v1`. The versioned
[`host-runtime-v1.json`](../../configs/runtime/host-runtime-v1.json) fixes shared
runtime settings and role commands. The same launcher checks Provider presence
on workers and waits for both family workers before API startup. Settings that
conflict with the profile fail startup with the configuration key only.
Infrastructure origins, database, storage, credentials and capacity remain
environment values. Compare `/app/.capstone-agent/host-runtime.json` in all
three roles against the local receipt: contract and source artifact hashes
must match. The source hash includes source, locks, installed Python package
versions, the pinned build recipe and six model assets. It does not hash secrets
or stage-specific infrastructure. The installed artifact hash also includes
the Authority catalog and must match all backend roles within each stage.
ARM and x86 can produce different floating-point revision hashes for generated
models; compare source identity across architectures, and installed identity
across stages with the same architecture. Snapshots still require their exact
installed artifact identity. A receipt proves alignment; actual App,
Provider and evidence checks still gate acceptance.
Save role-keyed receipt objects (`api`, `pandapower`, `pypsa`) and run
`python deploy/verify_host_runtime.py local-receipts.json cloud-receipts.json`.
Exit0 accepts matching receipts; any drift rejects alignment.

For the bounded M11 acceptance, set `CAPSTONE_THREAD_VALIDATION=m11` and
`CAPSTONE_DEPLOYMENT_STAGE=cloud-development` on all backend roles. This selects
fixed instructions over real prepared Authorities without constructing a
Provider session. Unknown instructions fail. Private
`GET /api/v1/validation/m11` must confirm both workers before the driver sends
any Thread command. Public demo credentials cannot use this endpoint or Threads.

For this separate scripted validation mode, explicitly set
`CAPSTONE_RUNTIME_PROFILE=` in both lanes; it is not the normal workbench
profile. First rebuild locally with these opt-in variables in the command environment
and `make capstone-local-rebuild`. Run `make validate-thread-m11` with
`CAPSTONE_M11_API_ORIGIN` and `CAPSTONE_M11_OPERATOR_TOKEN` in protected environment
state. The command writes bounded private receipts below `runs/capstone-m11`.
Do not place tokens in command arguments or logs. Exit 0 means automated checks
passed; exit 1 means failure; exit 2 means setup is missing or invalid. Browser,
deployment identity, restart retention, and legacy report checks are separate.

Record the tested source and prior service settings before deploying to cloud
development. Preserve existing databases, buckets, and sessions. On failure,
restore the prior cloud-development revision and configuration. After acceptance,
remove `CAPSTONE_THREAD_VALIDATION` from all roles, redeploy the same tested source,
and verify health and both catalog families. Do not submit a Provider-backed
Thread without separate authorization. User-trial promotion is a separate action.

Railway Hobby cannot configure credentials for a private container registry, so
the current source-build topology remains supported. When a registry is
available, promote the exact verified backend image digest from cloud-dev to
demo instead of rebuilding it for the trial environment.

## Cloud-dev to demo promotion

### Cloud-dev idle policy

Cloud-dev must sleep automatically and wake on access. The accepted target is
a very small idle bill with reliable first access, not absolute zero at the
cost of a fragile startup chain. Start with Serverless on API and both family
workers. Keep the small static App running for first-page reliability, plus a
small PostgreSQL baseline. Measure database CPU and
memory after removing idle worker polling; consider database sleep only if
its residual cost justifies the extra TCP wake dependency. Storage remains
billable. Keep the PostgreSQL volume, private bucket and all Thread history.

Railway applies `sleepApplication` on the next deployment. Observe at least
ten minutes with no App clients, event streams, health probes or task polling.
Use control-plane metrics to check actual sleep without waking services. Page
entry streams actual component readiness and admits controls only when all
checks pass. A browser's bounded activity window can keep workers available;
an indefinitely open idle page cannot. Stop inactive subscriptions and resume
from durable state without clearing the local workspace. No-client keepalive
is forbidden. Then
check first-page recovery, an owned registered scripted case, reports, replay
and source identity. Repeat the idle/wake cycle and record total residual
cost plus cold-start time. A configured toggle alone is not acceptance.

Disable cloud-dev automatic development triggers during controlled releases.
Do not change demo. The earlier manual stop is a maintenance record, not
acceptance of this automatic policy. The
[2026-10-08 suspension receipt](../../docs/reviews/2026-10-08-cloud-dev-idle-suspension.md)
records this stage's recovery boundary.

Resume the recorded PostgreSQL deployment first, then both workers, API and
App. Use the recorded source or deploy one locally verified revision to every
backend role; check readiness and source identity before remote validation.
Keep automatic development triggers disabled unless deliberately re-enabled
for an active validation period. Manual suspension itself does not receive an
acceptance tag. A resumed deployment must pass the usual stage validation
before receiving a new cloud-dev tag or being promoted to demo.

### Promotion checks

1. Run local gates and exercise the local App with `make capstone-local-rebuild`.
2. Deploy the same source revision to `capstone-cloud-dev`.
3. Check `/health/ready`, a registered scripted case, a separately authorized Provider case, report
   generation, evidence replay, and API/Worker source or image identity.
4. Record the verified revision and promote that exact revision or image digest
   to `capstone-demo` under a release tag.
5. Recheck the demo health endpoint and one registered public case.
6. Roll back the demo to the previous verified revision when a release fails.

The cloud-dev App uses `CAPSTONE_PUBLIC_DEMO=true` so its no-login flow can
exercise the registered public cases. Keep its URL internal. Provider keys are
separate by default; the current function-validation stage may use existing
credentials as authorized by the user. Set `CAPSTONE_PUBLIC_DEMO=false` only for API-only or
operator tests that do not run the App. The demo API uses
`CAPSTONE_PUBLIC_DEMO=true`. Public credentials permit registered scripted
sessions only. Optional `CAPSTONE_PUBLIC_PROVIDER` and `CAPSTONE_PUBLIC_MODEL`
remain defaults for private Provider sessions and are not required for demo access.

The variable checklists in [`cloud-dev.variables.example`](cloud-dev.variables.example)
and [`demo.variables.example`](demo.variables.example) contain names and safe
placeholders only. They are review aids, not complete Railway credentials.

Set these variables on **both** backend services, using Railway service and
bucket variable references or protected values in the project UI:

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection URL, shared by API and worker |
| `CAPSTONE_OPERATOR_TOKEN` | Same private operator token in both roles |
| `CAPSTONE_PUBLIC_DEMO` | `true` on the API for automatic public demonstration access |
| `CAPSTONE_THREAD_OPEN_ACCESS` | `true` for the current cloud-dev function trial; opens Thread operations without a browser token |
| `CAPSTONE_HOSTED_APPLICATION` | `capstone` for the unified API; the selected family for each worker |
| `CAPSTONE_PUBLIC_PROVIDER` | Optional private Provider default |
| `CAPSTONE_PUBLIC_MODEL` | Optional private Provider model default |
| `CAPSTONE_SESSION_IDLE_SECONDS` | Selected by the [shared runtime contract](../../configs/runtime/host-runtime-v1.json); release idle compatibility sessions |
| `CAPSTONE_WORKER_MAX_SESSIONS` | `12` for the measured public demo on one worker replica; tune after measuring memory and latency |
| `PORT` | Explicit worker listen port; cloud-dev uses `8080`, local Compose uses `8766` |
| `CAPSTONE_WORKER_WAKE_URL` | Worker private origin with the effective worker `PORT`; cloud-dev uses `http://capstone-worker.railway.internal:8080` on API and worker |
| `CAPSTONE_ALLOWED_HOSTS` | API public hostname only, without scheme |
| `CAPSTONE_ALLOWED_ORIGINS` | App HTTPS origin only |
| `CAPSTONE_ARTIFACT_BACKEND` | `s3` |
| `CAPSTONE_ARTIFACT_BUCKET` | Bucket `BUCKET` credential, not display name |
| `CAPSTONE_S3_ENDPOINT` | Bucket `ENDPOINT` credential |
| `AWS_ACCESS_KEY_ID` | Bucket `ACCESS_KEY_ID` credential |
| `AWS_SECRET_ACCESS_KEY` | Bucket `SECRET_ACCESS_KEY` credential |
| `AWS_DEFAULT_REGION` | Bucket `REGION` credential |

If a new session remains `pending` while deployment health checks pass, check
the worker's effective listen port and the API wake URL first. A successful
health check does not prove that API-to-worker wake requests reach that port.
After fixing the URL, redeploy the affected role from the same verified
revision and verify a fresh scripted session reaches `ready` and completes.

The bucket must already exist. Railway buckets use virtual-hosted S3 URLs for
new buckets; older buckets can use path-style URLs. Check the bucket Credentials
tab before release. The API streams sequenced events to the App, and the App
reconnects using the last sequence after a dropped connection. If a worker is
replaced during a turn, its lease expires and the session becomes interrupted;
committed turns remain readable.
For legacy session-only stages, enable Railway Serverless on the API and worker after verifying the private
wake request starts a pending session. Keep the small static App running so a
visitor's first page request does not meet a cold-start 502; its read-only API
requests retry transient 502/503/504 responses. Leave PostgreSQL running. The
worker checks pending work on startup and on authenticated wake requests; it
does not poll PostgreSQL when no sessions are active. A sleeping worker may
respond with a transient 502 during startup; the API retries, and a pending
session status read requests another wake. The first case opening can take
longer after sleep. Check actual usage before assuming the Hobby plan's $5
monthly included usage covers the deployment.
The idle timer pauses while a turn or report is running. An expired session
cannot accept another turn; visitors can reset that case and start a new run.
When all slots in a replica are occupied and another session has waited one
second, the shared ledger reserves the globally longest idle session for
eviction after a 30-second grace period. Active turns and reports remain
protected. Add worker replicas for aggregate capacity;
adjust the per-replica setting only after measuring memory.

For an all-Railway deployment, create the App service from
`packages/capstone-app` as its root directory. Its Dockerfile builds Vite and
serves the static files with Caddy. Set `VITE_API_ORIGIN` to the API's HTTPS
origin, for example `https://${{capstone-api.RAILWAY_PUBLIC_DOMAIN}}`, and set
the App health check path to `/health`. Generate public HTTPS domains for the
API and App, and use the App hostname for `CAPSTONE_ALLOWED_ORIGINS` on both
backend services. Only the API and App need public domains. The App build
contains the public API origin; it must never contain the operator token or
storage credentials.

Vercel remains an alternative static host: set its project root to
`packages/capstone-app` and use the checked-in `vercel.json` with the same
`VITE_API_ORIGIN`.
The original registered-case page at `/old` obtains a demonstration credential
from the API on each load and opens
automatically. This credential can run only registered
scripted cases; a refresh restores the tab's last run without creating another
session. Provider sessions require the private operator token.

The current root Thread workbench uses the selected open access mode. It does
not ask users to enter a token. Workers use their existing Provider credentials.

## Railway control-plane connection

Use the existing Railway CLI account login for deployment operations. Before
uploading, check the selected project with the local operator utility:

```sh
python3 deploy/railway/control_plane.py \
  --project-id <existing-project-id> --expected-project capstone-cloud-dev
```

The utility performs a read-only query and reports the effective proxy/direct
route. It does not create credentials or change the proxy configuration. It
retries transport failures at most three times, with one- and two-second waits.
Authentication, permission and certificate failures stop immediately with
separate diagnostic codes. Errors omit raw CLI output and credential values.

Operator scripts can import `run_read` for explicit GraphQL queries and
deployment/variable lists, and `run_write` for other operations. Writes invoke
the CLI once. A timeout or lost write response reports `write_outcome_unknown`;
read deployment or variable state before issuing another write. Do not retry an
upload merely because its response was lost.

References: [Railway background workers](https://docs.railway.com/guides/cron-workers-queues),
[Railway buckets](https://docs.railway.com/storage-buckets),
[Railway health checks](https://docs.railway.com/deployments/healthchecks).
