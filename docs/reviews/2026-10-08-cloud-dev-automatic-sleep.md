# Cloud-dev automatic sleep verification

Status: passed for source `8b88af9`. Two actual idle/wake cycles pass,
including a foreground page that remains open. No Provider call is made.

The user accepts a small idle bill, requires automatic access wake, and keeps
browser pages open. This replaces the earlier manual suspension as the active
cost policy. Demo remains unchanged.

For a foreground page, the App releases its subscription after 15 minutes
without real interaction and without active or uncertain work. Railway then
needs about 5–10 minutes without network activity to sleep the compute lane.
The expected combined window is about 20–25 minutes after the last activity,
not immediate sleep. The measured no-client cycle needed an extended
observation beyond ten minutes, so allow roughly 20–30 minutes in operations;
do not promise an exact suspension deadline. Hidden pages release their subscription sooner. Existing
tabs must load the new App bundle once for the new activity policy to apply.

## Source and runtime

Source: `8b88af94ece827caaa988ecc650a66320f033e20`.
The uploaded source is a clean Git archive plus the six verified pinned model
assets. It contains no local runtime, user data or authentication state.
All four deployment messages record this commit. Backend installed sources,
locks, package versions, Python version, model assets and build recipe have
the same source artifact hash as local acceptance:
`d2a862c8d98737055810e49d563a470af372a39f66d8e83b377aba541b022787`.
Full installed identity, including Authority catalog metadata, matches all
three cloud backend roles:
`ba73684a9ba99314f12c6b1ba0963f5bb7166584591d921f0ebdb80909ad1741`.
The local ARM installed identity is
`a24f19a3a718b2841116da447f0925a29f2e05bb73cc3c8dec6e77889ff53b54`.
The source and exact within-stage checks in `deploy/verify_host_runtime.py`
pass. Different architectures do not relax snapshot or model revision checks.

| Service | Deployment | Idle policy |
| --- | --- | --- |
| App | `b87ae506-fda1-4c19-b079-602f4ad8ddac` | Small static service stays available |
| API | `445d9a8c-a191-4e26-92f9-4c67eee63aca` | Serverless |
| pandapower worker | `530eeee2-7272-4425-b706-225202aa76d4` | Serverless |
| PyPSA worker | `a042681a-3499-46a2-8b13-b8ad8769ee92` | Serverless |
| PostgreSQL | `4c13697c-5442-4163-9949-53a82f015893` | Small durable baseline stays available |

The volume `aa131e4a-74e1-4fb4-a21f-584de5c4fffc` and bucket
`0dee2c91-98a4-4a35-9b22-1fd2cd543ba7` are retained.
Automatic development push triggers stay disabled. A task-specific temporary
SSH key was used to read bounded runtime receipts, then revoked and removed.

## Local and functional checks

- Full `make test`, `make test-e2e`, `make validate` and `make doctor` pass.
  The full test run includes 580 backend tests, 189 simulator tests, 347 App
  tests and 156 workbench tests. The runtime gate also passes 22 focused tests,
  including source drift and per-stage installed identity checks.
- `make capstone-local-rebuild` passes. API and both workers share image
  `sha256:c1f5f4d9197de789b1726de5b53ab7573065bd8785aadbbe840801db24537b53`.
- Desktop, phone and landscape checks retain drafts through inactivity and
  recovery. Desktop input focus returns after admission. A real long local
  conversation retains its message scroll position through two cycles, with
  no POST requests. The loaded workspace remains mounted.
- Public registered pandapower and PyPSA scripted cases complete three turns
  locally and in cloud-dev. Reports and admitted evidence replay pass for
  both. These checks make no Provider call and use only owned test sessions.
- One cloud verification read encountered a TLS EOF. Its owned compatibility
  session expired before the next turn. The partial receipt is retained; a
  fresh owned case passes with bounded read recovery. Writes were not blindly
  replayed.
- Cloud App health and its current preparation/activity bundle pass. Warm
  workbench preparation takes 0.602 seconds. This is not a cold-start result.

## Idle and wake measurements

Revision `2ef57c8` completes a ten-minute no-client interval ending at
09:41:48 UTC: API and both workers are `SLEEPING`; App and PostgreSQL remain
`SUCCESS`. Normal browser entry then wakes the lane without an operator start.
Input remains absent during preparation, and only an owned Thread is created.
However, the complete first entry takes 125.862 seconds, with the preparation
response arriving after 114.585 seconds. This latency is rejected for UX
acceptance. The owned Thread is archived and the background browser closed.

The corrected no-client cycle starts at 10:32:46 UTC. Both workers sleep
within the ten-minute window; API is still awake at that boundary. Extended
control-plane observation confirms all three asleep before browser entry at
about 12 minutes 21 seconds. HTTP logs show no newer application requests in
the interval. The exact platform inactivity sample is not a user-facing SLA.

Normal first entry on `8b88af9` takes 20.165 seconds, including creation of an
owned Thread. The preparation response starts after 9.373 seconds. Input is
blocked throughout preparation. The only POST is owned Thread creation; no
analysis command or Provider request is sent. Both registered three-turn cases
then pass again, with reports and evidence. Reports from the earlier deployed
revision retain their exact SHA256 values and all five evidence reads pass.

For the retained-page cycle, background Playwright advances only the
15-minute browser inactivity timer. Browser time continues to run and the
page remains open through a real ten-minute cloud idle interval, from
10:49:15 to 10:59:15 UTC. API and both workers are `SLEEPING` at the end;
App and PostgreSQL remain `SUCCESS`. HTTP logs show no renewed requests.
The workspace, draft and electric topology stay visible throughout.

A real pointer interaction then recovers the connection in 11.408 seconds.
The compact progress panel leaves the workspace mounted. Input is disabled
until all services and refreshed projections are ready. Draft, input focus,
topology viewBox and message scrollTop are unchanged; no POST is sent.
This cloud check uses an empty owned Thread; the nonzero long-history reading
position check is local. The owned Thread is archived after verification and
the background browser is closed. User Threads are not changed.

Demo API/App health remains 200, and deployment IDs, instances and sleep
settings remain byte-for-byte equal to the pre-operation projection. Both
stages have no automatic main-push deployment triggers. This acceptance
applies to cloud-dev; it does not promote or modify demo.

The `4eaa555` candidate passed local suites, but independently built cloud
workers exposed different registered Kerber model revisions. These factories
use Python random state. Acceptance is blocked until the Authority creates
the registered examples reproducibly and all runtime identities match. The
API and App have not been promoted to this candidate.

Revision `cdd4e74` makes independent cloud worker catalogs identical. Local ARM
and cloud x86 still differ in generated floating-point revisions for
`example_multivoltage`, `lv_schutterwald` and `mv_oberrhein`. Revision `8b88af9`
therefore records separate source and installed identities, plus architecture.
Source identity must agree across stages; full installed identity must agree
within each stage and across matching architectures. Exact snapshot validation
is preserved. Its two new gate checks fail before the change and pass after it.

## Evidence and limits

Ignored, secret-free receipts are under `runs/cloud-dev-idle-20261008/`:
`identity-deployment-source.json`, `identity-source-bindings.json`,
`local-identity-runtime.json`, `cloud-identity-runtime.json`,
`identity-app-build-verification.json`, `local-identity-scripted.json`,
`cloud-identity-scripted.json`, `idle-cycles.json` and per-cycle control-plane samples.
The corrected cold and retained-page records are `cold-2-browser.json`,
`idle-2-complete.json`, `idle-3-complete.json` and `resume-3-browser.json`.
`cloud-after-cold-scripted.json` and `pre-release-history-replay.json` verify
post-wake execution and earlier persisted evidence. Initial ten-minute API
delay and rejected candidates remain recorded rather than overwritten.
Background browser screenshots are under `output/playwright/`.

The account subscription, retained storage, active calculation time and
transfer are separate from idle compute. Short metric windows do not prove a
monthly invoice. The operating policy follows the
[accepted design](../superpowers/specs/2026-10-08-cloud-dev-idle-sleep-design.md)
and [commercial research](../superpowers/specs/2026-10-08-cloud-idle-commercial-patterns.md).

The 10:50:00–10:57:00 UTC retained-page metric window gives these means:

| Retained service | Memory (GB) | CPU (vCPU) |
| --- | --- | --- |
| Static App | 0.021150 | 0.000048 |
| PostgreSQL | 0.067272 | 0.000262 |

At the documented memory and CPU rates, the combined idle resource estimate
is about USD 0.89/month. The earlier no-client window estimates USD 0.83/month.
This is an incremental running-resource estimate,
not a total account bill or an invoice guarantee. Storage, transfer, active
work and the account plan are excluded. Rates come from
[Railway pricing](https://docs.railway.com/pricing/plans); sleep behavior comes
from [Railway Serverless](https://docs.railway.com/deployments/serverless).
Railway states that a slept service accrues no compute charges in its
[idle-cost guide](https://docs.railway.com/guides/cut-idle-costs-serverless).
The estimate above covers the retained App and database, rather than adding
the sleeping API and workers' prior resident memory.
