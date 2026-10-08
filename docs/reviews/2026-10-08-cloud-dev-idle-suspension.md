# Cloud-dev idle suspension

The user reports no cloud-dev users and requests reducing idle CPU and memory
costs there first. Demo remains available for user trials. This operation
stops cloud-dev compute without deleting persistent storage or changing demo.

## Findings

The supplied billing screenshots show accumulated charges of $2.43 for
cloud-dev and $1.37 for demo. They do not establish an hourly or daily rate.
Cloud-dev CPU plus memory totals $2.4137; its volume charge is $0.0075.
Live control-plane reads confirm both stages had five active deployments and
Serverless disabled on every service. Cloud-dev also had three `main` push
triggers, for App, API and the pandapower worker. Demo had no push triggers.

The current Thread worker also checks the ledger every 0.25 seconds when idle.
This is a separate program efficiency issue. Merely enabling Serverless would
not establish that the workers can sleep: database and private network traffic
count toward Railway activity. Worker idle efficiency remains deferred while
the unused cloud-dev stage is suspended.

## Operation and verification

Project: `capstone-cloud-dev`, `5eecde6b-fec2-40d2-8b26-427025b02b96`.
Environment: `5afd6aeb-07a6-4320-92e9-4bf193a442cb`.

The three cloud-dev deployment triggers were recorded and removed. Service
source settings remain intact. The five running deployments were removed in
App, API, worker, PyPSA worker and PostgreSQL order.

| Service | Stopped deployment |
| --- | --- |
| App | `6f0ff615-eebd-41ae-8554-46f28ba96236` |
| API | `0e8ba2f4-0abc-4307-922f-dec4799ea01e` |
| pandapower worker | `1208203c-b6c6-4fef-9a34-947870a15e88` |
| PyPSA worker | `dd76e366-f508-4c83-b0c1-64c325c53e00` |
| PostgreSQL | `38b6d68a-3617-4685-b5c2-741fbaff3e4e` |

Readback confirms zero active cloud-dev deployments and zero push triggers.
The exact deployment records are `REMOVED` with `deploymentStopped=true`.
The PostgreSQL removal returned an operation error; it was not retried.
Control-plane reconciliation confirms it did stop successfully.

Retained resources:

- PostgreSQL volume `aa131e4a-74e1-4fb4-a21f-584de5c4fffc`.
- Private artifact bucket `0dee2c91-98a4-4a35-9b22-1fd2cd543ba7`.
- All five service definitions, source settings and protected variables.

Demo project `a7a503b3-9f48-480d-8090-f063bab3b8db` has an identical before/after
control-plane projection: service/deployment IDs, state, settings, volume,
bucket and triggers. Its API `/health/ready` and App `/health` both return 200.
No demo mutation, Thread command or Provider call was made. Existing history
was not edited or deleted. Retained volume IDs prove retention of the storage
resources; a new database content audit was not needed for deployment removal.

Ignored receipts under `runs/cloud-dev-idle-20261008/`: `before.json`,
`restore-config.json`, `actions.json`, `after.json`, `verification.json` and
`stopped-deployments.json`. Trigger settings and prior deployment/source
identities are recorded without credentials. No acceptance tag was created.

## Recovery boundary

Cloud-dev is suspended and cannot serve remote validation until restarted.
Restore PostgreSQL first, then both workers, API and App using the recorded
deployment history, or deploy one newly verified backend revision to all roles.
Check readiness and runtime/source identity before validating. Old deployment
images have a finite Railway retention window; a later recovery can require
rebuilding the original source. Keep development push triggers disabled during
idle periods. Validate any resumed deployment before creating its stage tag.

Running-container CPU and memory charges should cease after teardown. Storage
charges and already accumulated charges remain. A later billing graph is needed
to verify the actual fee slope; immediate control-plane stop is not a new bill.

References: [Railway deployment Remove](https://docs.railway.com/deployments/deployment-actions),
[Serverless activity](https://docs.railway.com/deployments/serverless),
[image retention](https://docs.railway.com/pricing/plans), and
[stage lifecycle](../architecture/capstone-development-lifecycle.md).
