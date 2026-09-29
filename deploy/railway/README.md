# Railway topology

Railway hosts two separate Capstone stages: the existing `capstone-demo` project
serves user trials, while the planned `capstone-cloud-dev` project validates
cloud changes. Local Compose remains the high-frequency development loop. Railway
environments can also represent the two stages inside one project, but separate
projects provide the clearest billing, credential, data, and access boundary.

## Environment topology

| Stage | Railway target | Source trigger | Public access | Data and credentials |
| --- | --- | --- | --- | --- |
| Cloud development | `capstone-cloud-dev` | `main` after local gates, deployed deliberately | Internal testers and the development App origin | Dedicated PostgreSQL, bucket, operator token, Provider key, and domains |
| User trial | `capstone-demo` | Release tag or explicit promotion of a verified revision | Registered scripted cases through the public demo credential | Dedicated PostgreSQL, bucket, operator token, Provider key, and domains |
| Local | Docker Compose plus Vite | Working tree changes | Local machine or LAN | Ignored local database, RustFS bucket, and runtime state |

Each Railway stage contains one PostgreSQL service, one private Railway Bucket,
one API service, one on-demand Worker service, and one static App service. API and
Worker must use the same tested backend image or source revision within a stage.
The two stages never share `DATABASE_URL`, artifact storage, operator tokens,
Provider credentials, or public origins. `VITE_API_ORIGIN` contains only the
selected API origin.

The existing public topology remains the user-trial topology. Set the API start
command to `/app/deploy/entrypoint.sh api` and the Worker start command to
`/app/deploy/entrypoint.sh worker`. Keep one Worker replica initially. The Worker
has no public domain. Set its internal HTTP health check path to `/health` and
its `PORT` to `8766`. Set the API health check path to `/health/ready` and expose
its generated HTTPS domain. A local SciGRID run peaked near 1.1 GiB; allow
headroom and check Railway metrics before setting a Worker memory cap.

Railway Hobby cannot configure credentials for a private container registry, so
the current source-build topology remains supported. When a registry is
available, promote the exact verified backend image digest from cloud-dev to
demo instead of rebuilding it for the trial environment.

## Cloud-dev to demo promotion

1. Run local gates and exercise the local App with `make capstone-local-rebuild`.
2. Deploy the same source revision to `capstone-cloud-dev`.
3. Check `/health/ready`, a registered scripted case, one Provider case, report
   generation, evidence replay, and API/Worker source or image identity.
4. Record the verified revision and promote that exact revision or image digest
   to `capstone-demo` under a release tag.
5. Recheck the demo health endpoint and one registered public case.
6. Roll back the demo to the previous verified revision when a release fails.

The cloud-dev App uses `CAPSTONE_PUBLIC_DEMO=true` so its no-login flow can
exercise the registered public cases. Keep its URL internal and use a separate
Provider key and limits. Set `CAPSTONE_PUBLIC_DEMO=false` only for API-only or
operator tests that do not run the App. The demo API uses
`CAPSTONE_PUBLIC_DEMO=true`, `CAPSTONE_PUBLIC_PROVIDER=deepseek`, and
`CAPSTONE_PUBLIC_MODEL=deepseek-flash`.

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
| `CAPSTONE_PUBLIC_PROVIDER` | `deepseek` on the API when `CAPSTONE_PUBLIC_DEMO=true` |
| `CAPSTONE_PUBLIC_MODEL` | `deepseek-flash` on the API when `CAPSTONE_PUBLIC_DEMO=true` |
| `CAPSTONE_SESSION_IDLE_SECONDS` | `600` on the worker; release a session after ten minutes waiting for the next instruction |
| `CAPSTONE_WORKER_MAX_SESSIONS` | `12` for the measured public demo on one worker replica; tune after measuring memory and latency |
| `CAPSTONE_WORKER_WAKE_URL` | `http://capstone-worker.railway.internal:8766` on both API and worker; local Compose uses `http://worker:8766` |
| `CAPSTONE_ALLOWED_HOSTS` | API public hostname only, without scheme |
| `CAPSTONE_ALLOWED_ORIGINS` | App HTTPS origin only |
| `CAPSTONE_ARTIFACT_BACKEND` | `s3` |
| `CAPSTONE_ARTIFACT_BUCKET` | Bucket `BUCKET` credential, not display name |
| `CAPSTONE_S3_ENDPOINT` | Bucket `ENDPOINT` credential |
| `AWS_ACCESS_KEY_ID` | Bucket `ACCESS_KEY_ID` credential |
| `AWS_SECRET_ACCESS_KEY` | Bucket `SECRET_ACCESS_KEY` credential |
| `AWS_DEFAULT_REGION` | Bucket `REGION` credential |

The bucket must already exist. Railway buckets use virtual-hosted S3 URLs for
new buckets; older buckets can use path-style URLs. Check the bucket Credentials
tab before release. The API streams sequenced events to the App, and the App
reconnects using the last sequence after a dropped connection. If a worker is
replaced during a turn, its lease expires and the session becomes interrupted;
committed turns remain readable.
Enable Railway Serverless on the API and worker after verifying the private
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
The App obtains a demonstration credential from the API on each load and opens
automatically. This credential can run only registered
scripted cases; a refresh restores the tab's last run without creating another
session. Provider sessions require the private operator token.

References: [Railway background workers](https://docs.railway.com/guides/cron-workers-queues),
[Railway buckets](https://docs.railway.com/storage-buckets),
[Railway health checks](https://docs.railway.com/deployments/healthchecks).
