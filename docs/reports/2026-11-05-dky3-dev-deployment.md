# DKY3 development deployment

Update13:06:三区研发 is now the configured default gateway. Its protected
connection file is mode0600. Registry status is connected and its contract is
available. New threadthr_5f2ded6051b79a52a4ab reports the same available default
instance0c266ac6-bf86-4137-ab7c-0e283331ab1f in its input catalog. The executor was
restarted with no running attempts. No model task was started. Evidence:
`runs/dky3-dev-20261105/gateway-default-check.json`. Deferred-gateway records below
are history. Product,continuation and refresh acceptance remain pending.

Entry:http://192.168.72.66:5173/. Page label:`dky3-dev`.
Host:`root@192.168.72.66`; root:`/data/capstone-dky3-dev`;
Compose project:`capstone-dky3-dev`. This is an independent development install.

## Sources and running images

Backend/native source:`2b6dd8a3c55ad8ef1a72db6c81f181ab9c5b560a`.
The current backend source contents match that snapshot. App source:
`c4466005eed49d30e0dbd5b72ac1fde0db4fe74a`,with the explicit deployment label.
The App uses the same-origin API. Its served script is `index-hF9aslOg.js`;
the build object contains the exact App source and `environment:dky3-dev`.
These are retained source snapshots,not dev integration commits. Dev remains6c55e6ee.

| Role | Image SHA-256 |
| --- | --- |
| API and worker | `f1e7448372aae777c8233a2c2ad9f64d3f752a313b8dbbb495ac0a4bd4ac169d` |
| Native executor | `c71dfa5d2353a07a00904ed03dd1eb35fc7955842b80614795016f3840d5e5dd` |
| App | `ffe5d0524387cc06bae6a2b74324409df6200ef4f750b8da368a5e2c5881420b` |

The amd64 base image archives were checksum-verified before loading. Backend
package sources were copied from the exact source archive. The Authority catalog
was rebaked for this installed source. Build-created uv cache ownership was set
for the service account. The native source label names its unchanged source inputs.
PostgreSQL/object images are the pinned20261101 intranet images,with new volumes.

## Isolation and configuration

All Capstone volumes use the `capstone-dky3-dev_` prefix. Database,object-store,
operator and executor-control secrets were generated for this install. Protected
configuration is in `private/` and mode0600 `runtime.env`; no other install's
authentication state was copied. Existing server applications were not changed.
The API binds host loopback8767; only the same-origin App exposes5173.
Skills/MCP management is disabled. Research automation is disabled.

The registered intranet default is Qwen3.8-Flash-Next at192.168.72.69:8013.
The host can reach its model endpoint. No gateway connection was copied or
installed:the user chose to configure it later in the page.

## Verification and remaining work

- Environment label regression:16 Python and17 App checks passed.
- App type check and production build passed.
- Canonical local rebuild passed,API/worker imagee441db29 matched; scoped cache
  maintenance completed. Doctor and whitespace checks passed.
- Remote App,API,worker and native executor are healthy. `/health/ready` returns
  `ready`; PostgreSQL is healthy and object initialization completed.
- API and worker run the same exact image. Static App build identity was checked.
- Real task admission returned `gateway_bound_instance_unavailable`,because no
  gateway is configured. The first check saved threadthr_fc67eace9887aca03c76;
  a second admission-only probe captured the error body in
  thr_9a8cb873859e3d6530ea. Neither request started a model attempt.
- File production,download,continuation and refresh acceptance remain pending.
  No acceptance tag was created. The earlier .63 model-understanding timeout
  remains an upstream known gap; this deployment does not claim it fixed.
- No browser visual acceptance is claimed. No CI,cloud change or main/dev merge ran.

Next:configure the三区 gateway through the page,then run a real task and validate
its saved product,continuation and refresh. Preserve existing/new data on later
updates; do not use `down -v`. This first install has no prior Capstone version
on this host to roll back to.

Evidence:`.capstone-agent/dky3-dev-20261105/` and
`runs/dky3-dev-20261105/`. Source recovery ref:
`refs/capstone/dky3-dev-candidates/20261105`.
