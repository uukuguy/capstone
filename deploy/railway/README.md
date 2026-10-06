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
| User trial | `capstone-demo` | Release tag or explicit promotion of a verified revision | Registered scripted cases through the public demo credential | Dedicated PostgreSQL, bucket, operator token, Provider key, and domains |
| Local | Docker Compose plus Vite | Working tree changes | Local machine or LAN | Ignored local database, RustFS bucket, and runtime state |

Each Railway stage contains one PostgreSQL service, one private Railway Bucket,
one API service, registered family workers, and one static App service. All backend
roles must use the same tested image or source revision within a stage.
The two stages never share `DATABASE_URL`, artifact storage, operator tokens
or public origins. Provider credentials are separate by default; the current
user-approved function-validation stage permits an existing Provider key.
`VITE_API_ORIGIN` contains only the selected API origin.

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

## Federated cloud-development acceptance

Use these roles only in `capstone-cloud-dev`:

| Service | Application | Start command | Health |
| --- | --- | --- | --- |
| `capstone-api` | `capstone` | `/app/deploy/entrypoint.sh api` | `/health/ready` |
| `capstone-worker` | `pandapower` | `/app/deploy/entrypoint.sh worker` | `/health` |
| `capstone-worker-pypsa` | `pypsa` | `/app/deploy/entrypoint.sh worker` | `/health` |

Set `PORT=8080` for all backend roles. Give workers no public domains. Keep
one replica per worker and disable sleeping during Thread acceptance: Thread
Attempts use polling. Wait for both new worker deployments to succeed and pass
health and artifact checks before deploying the API. Its catalog refreshes
family availability on each catalog or admission check. Use the two private origins from
[`cloud-dev.variables.example`](cloud-dev.variables.example).

Normal local Compose and cloud development select
`CAPSTONE_RUNTIME_PROFILE=capstone-workbench-v1`. The versioned
[`host-runtime-v1.json`](../../configs/runtime/host-runtime-v1.json) fixes shared
runtime settings and role commands. The same launcher checks Provider presence
on workers and waits for both family workers before API startup. Settings that
conflict with the profile fail startup with the configuration key only.
Infrastructure origins, database, storage, credentials and capacity remain
environment values. Compare `/app/.capstone-agent/host-runtime.json` in all
three roles against the local receipt: contract and logical artifact hashes
must match. The artifact hash includes source, locks, installed Python package
versions, the pinned build recipe and six model assets. It does not hash secrets
or stage-specific infrastructure. A receipt proves alignment; actual App,
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
