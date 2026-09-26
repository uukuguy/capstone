# Cloud Run and Vercel topology

Build the repository `Dockerfile` once and push one immutable image digest to
Artifact Registry. The [deployment template](deploy.example.sh) assigns that
same digest to a Cloud Run API service (`api`) and a Cloud Run worker pool
(`worker`). The API serves `/api/v1` and `/health/ready`; the worker pool has no
HTTP endpoint. One worker instance is the initial capacity. Both roles share
one Cloud SQL PostgreSQL database and one private GCS bucket. The model assets
and managed Pi runtime are verified during image build; turns do not download
models.

Prepare these resources before reviewing or running the template:

1. Cloud SQL PostgreSQL and a `capstone-database-url` Secret Manager secret.
   A Unix-socket URL can use
   `postgresql://USER:PASSWORD@/DB?host=/cloudsql/PROJECT:REGION:INSTANCE`.
   Give the API and worker identities Cloud SQL Client access.
2. A private GCS bucket. Give the worker identity object create/read access
   and the API identity object read access for current-run report/evidence
   delivery. Both identities need access to the named secrets.
3. A `capstone-operator-token` secret with one long random value. It is the
   same logical token for both roles and is never bundled into the App.
4. A stable API hostname and the Vercel App HTTPS origin. Bind
   `CAPSTONE_ALLOWED_HOSTS` to the API hostname and
   `CAPSTONE_ALLOWED_ORIGINS` to the App origin. The public demo endpoint
   supplies a scoped demonstration credential when the App loads.

Set the seven variables required by `deploy.example.sh` in the operator's
shell, review the command, and run it only as an authorized deployment. The
Cloud Run service request timeout is configured for SSE; the App reconnects
from its last event sequence when a connection ends. A worker replacement can
interrupt an in-flight turn after its lease expires, while committed answers
remain readable. Cloud Run worker pools do not autoscale; scale them explicitly
after measuring load.
The worker's `CAPSTONE_SESSION_IDLE_SECONDS=600` releases a session after ten
minutes waiting for the next instruction. It does not interrupt a running turn
or report. An expired session keeps its committed answers but cannot resume;
the visitor can reset the case and start a new run.
Each worker pool instance starts with `CAPSTONE_WORKER_MAX_SESSIONS=8`; tune this
against measured memory, then add worker pool instances for aggregate capacity.
The deployment template accepts `CAPSTONE_WORKER_INSTANCES` and
`CAPSTONE_WORKER_MAX_SESSIONS` as optional shell settings for these two limits.
When a worker is full and another session has waited one second, the shared
ledger reserves the globally longest idle session for eviction after a
30-second grace period. Active turns are preserved.

On Vercel, set the project root to `packages/capstone-app`, use the checked-in
`vercel.json`, and set `VITE_API_ORIGIN` to the API's HTTPS origin. This value is
public in the static build. Provider keys, operator tokens, database URLs, and
bucket credentials must stay out of Vercel build variables.

The deployment template enables `CAPSTONE_PUBLIC_DEMO=true` on the API. Visitors
enter the App automatically with a scoped demonstration credential and can run
registered scripted cases. Refresh restores the current tab's last run without
creating another session. Provider sessions still require the separate operator token.

References: [Cloud Run worker pools](https://docs.cloud.google.com/run/docs/deploy-worker-pools),
[Cloud Run service health checks](https://docs.cloud.google.com/run/docs/configuring/healthchecks),
[Cloud Run request timeout](https://docs.cloud.google.com/run/docs/configuring/request-timeout),
[Vite on Vercel](https://vercel.com/docs/frameworks/frontend/vite).
