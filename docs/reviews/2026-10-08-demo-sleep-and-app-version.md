# Demo release acceptance

Status: passed for deployment, registered cases, persistence, and per-page idle
recovery. Source `ed2524f5774eb105178ba3f52d34ad36706b5cf8` is the exact source
accepted under `cloud-dev-20261008-1941-ed2524f`. Demo has multiple trial users.
Whole-stage zero-traffic cold-start timing was not isolated in this live stage.
No Provider request was made by this verification.

## Deployed identity and isolation

All four deployment messages bind to the accepted commit. All three backend
roles report stage `user-trial`, the expected role and application, ready
dependencies, and the same source and installed identities as cloud-dev:

- Source artifact: `d2a862c8d98737055810e49d563a470af372a39f66d8e83b377aba541b022787`.
- Installed artifact: `ba73684a9ba99314f12c6b1ba0963f5bb7166584591d921f0ebdb80909ad1741`.
- Runtime contract: `48d470f5626f3b2abfd8a7c483f569f7e32721384dd343142b71cafdb80fa5ef`.

| Service | Accepted deployment | Image digest |
| --- | --- | --- |
| App | `cc6321c6-60d5-4f5b-aadc-e5f704327a0b` | `sha256:8f09e2661a0eb43a2e4158c99371c475b7d6f69ab9b27fe3e7ec445f7a9d5419` |
| API | `38508535-2a5c-4646-895e-1a3b560742dd` | `sha256:48859dc3a865ed945e86469d75255e5983c4e4dfd592ba46c7200ba2c0404af0` |
| pandapower worker | `e8bad5f8-fa7d-4c8d-9358-8e04d167bb64` | `sha256:578423d58e9d1bddff7e6512e66b12551d08d90a2093b6a6b73075258d42230c` |
| PyPSA worker | `4b64611d-5d17-4b7f-9587-8eff444c53e0` | `sha256:81f669f31e97aa9f7441f133a7e2c46feeee1b7e73532d9b028c10e0b2c4216b` |

PostgreSQL deployment `43710069-17bb-44fd-b3d6-266f6dc5a431` is unchanged.
Database, bucket and operator credentials differ from cloud-dev. Existing demo
Provider credentials and no-login Thread access remain protected backend
configuration. Demo private worker origins retain port 8766. Serverless is
enabled on API and both workers before their new deployments. The static App
and PostgreSQL remain available. No user Thread or active task was closed.

Demo has no App service-root override, so its upload uses the archive's App
directory. The first full-root App candidate `8d4e5d20-dadf-4dbb-9c2f-bebb0c96d949`
used the wrong build entry and was rejected. The old App still returned HTTP
200; only the corrected App deployment above is accepted. The Railway runbook
now records the different App upload roots for cloud-dev and demo.

## Verification

Fresh local release gates pass: `make doctor`, `make test`, `make test-e2e`,
`make validate`, App build and local rebuild. App tests: 348 passed. Local API
and both workers use image
`sha256:c1f5f4d9197de789b1726de5b53ab7573065bd8785aadbbe840801db24537b53`.
The [cloud acceptance](2026-10-08-cloud-dev-app-version.md) precedes promotion.

Demo API and App health pass. Preparation emits real API, database, pandapower
and PyPSA readiness frames; warm preparation completes in 0.528 seconds.
Both registered public scripted cases pass three turns, report and evidence
reads. Earlier owned reports retain their SHA-256 hashes and their evidence
remains readable after upgrade. No customer content is used for these checks.
Desktop and 390-pixel mobile layouts show `v0.1.0 · ed2524f` correctly.

The retained-page check simulates the 15-minute browser inactivity deadline,
then leaves that foreground page open during real cloud observation. It closes
its subscription, gates input, and retains its unsent draft, Thread URL,
topology camera and scroll position. The test uses an owned empty Thread, so
its scroll position is zero; this is not a claim about a long-history viewport.
On real pointer interaction, preparation gates input and completes in 1.891
seconds with the stage still serving traffic. Draft, focus, camera and scroll
are preserved; no command POST is sent. This is a live-stage workspace recovery
measurement, not an isolated cold-start measurement.

Initial control-plane observation has a local-machine pause and is not a
continuous quiet-window receipt. Platform logs contain container stop/start
events, but those alone do not establish an isolated full-stage sleep duration.
A later observation still finds active services. The user confirms multiple
demo visitors, some with pages open. No traffic or customer connections were
forced to stop for a global sleep test. The
[cloud-dev automatic sleep acceptance](2026-10-08-cloud-dev-automatic-sleep.md)
owns the isolated sleep and cold-wake measurements for the unchanged mechanism.

New pages release their subscription after 15 minutes without real activity
and without active or uncertain work. Actual user activity keeps services
available. Tabs still running the old bundle need one refresh to load this
policy. An open page alone is not sufficient reason to keep the new bundle
connected. No claim of a zero-cost month is made for a live trial stage.

## Cleanup and recovery

Only owned test Thread `thr_8ee3bb6237703a094341` is archived. The background
browser is closed. The task-specific SSH key is revoked and removed; local
observation and keep-awake processes are stopped. Existing user data is retained.

Rollback baselines, if required: App `ae649096-c8c6-4827-8a84-52c20a532ab5`,
API `e1cc5a94-1700-47d8-8603-9f625f8fd60e`, pandapower worker
`504a337f-cb58-4274-bcb5-34bcc766a3d7`, PyPSA worker
`5e0f4dc0-c53b-4fd2-bcc7-c93f46d5b391`. Restore their matching stage
configuration together; do not roll back or delete the database or artifacts.

Bounded receipts are in ignored `runs/demo-idle-promotion-20261008/`:
`demo-bindings.json`, `demo-runtime-alignment.json`, `demo-cases.json`,
`demo-history-replay.json`, `demo-preparation.json`, `demo-browser.json`,
`demo-resume.json`, `live-demo-idle-scope.json` and cleanup receipts.
