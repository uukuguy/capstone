# Railway topology

Create one PostgreSQL service, one private Railway Bucket, one API service, and
one always-on worker service. Deploy the API and worker from the **same immutable
backend image digest** built from the repository `Dockerfile`. Set the API start
command to `/app/deploy/entrypoint.sh api` and the worker start command to
`/app/deploy/entrypoint.sh worker`. Keep one worker replica initially. The worker
has no public domain or HTTP health check. Set the API health check path to
`/health/ready` and expose its generated HTTPS domain. Start with at least
4 GiB memory for the worker's scientific Python environments; check actual
usage before changing replica or resource limits.

Set these variables on **both** backend services, using Railway service and
bucket variable references or protected values in the project UI:

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection URL, shared by API and worker |
| `CAPSTONE_OPERATOR_TOKEN` | Same private operator token in both roles |
| `CAPSTONE_PUBLIC_DEMO` | `true` on the API for the public demonstration login |
| `CAPSTONE_ALLOWED_HOSTS` | API public hostname only, without scheme |
| `CAPSTONE_ALLOWED_ORIGINS` | Vercel App HTTPS origin only |
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

On Vercel, set the project root to `packages/capstone-app` and configure
`VITE_API_ORIGIN` to the Railway API's HTTPS origin. The App build contains that
public origin; it must never contain the operator token or storage credentials.
The API fills the App's demonstration credential on first load; visitors click
the existing login button to enter. This credential can run only registered
scripted cases; Provider sessions require the private operator token.

References: [Railway background workers](https://docs.railway.com/guides/cron-workers-queues),
[Railway buckets](https://docs.railway.com/storage-buckets),
[Railway health checks](https://docs.railway.com/deployments/healthchecks).
