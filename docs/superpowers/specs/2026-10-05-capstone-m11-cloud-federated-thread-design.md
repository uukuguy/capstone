# M11 Cloud-development Federated Thread Validation

## Purpose and status

Run the existing unified Thread application with pandapower and PyPSA family
workers in `capstone-cloud-dev`. Verify the M8 model lifecycle, M9 admitted
result projections, and M10 Authority topology through the remote Thread API
and Web replay path.

The user approved this written specification on 2026-10-05. The
[implementation plan](../plans/2026-10-05-capstone-m11-cloud-federated-thread-implementation.md)
defines the execution steps. Implementation and remote HTTP acceptance are
recorded in the [verification record](../../reviews/2026-10-05-capstone-m11-cloud-verification.md).
All required acceptance, including real cloud Web replay/focus and worker
restart retention, passed on 2026-10-05. Normal runtime is restored; Provider
validation and user-trial promotion remain separate actions.
M10 implementation and local verification are complete. Its cloud smoke used
the legacy pandapower scripted-session API and does not establish remote PyPSA
Thread acceptance.

## Baseline components and gaps at specification approval

- `capstone_agent.federated_hosted` already loads bounded catalogs from fixed
  exporters and builds the unified API. It never executes domain Attempts.
- `deploy/entrypoint.sh` already selects `capstone:api`, `pandapower:worker`,
  and `pypsa:worker`. Family workers lease their own Thread Attempts.
- Local Compose already runs this topology. Railway currently has one
  pandapower API and one worker.
- Both hosted family adapters currently construct Provider-backed Pi sessions.
  Legacy `scripted-demo` sessions do not exercise the M10 Thread provider.
- `validation/thread/provider_free_host.py` supplies deterministic sessions to
  the prepared runtime, but uses an in-memory service and a local HTTP test
  client. It is a reference for a remote validation adapter, not evidence of
  remote PostgreSQL or worker behavior.
- The existing public demo API and its tests allow registered cases in
  `provider` mode with fixed Provider settings. This conflicts with the
  repository requirement that public credentials allow scripted cases only.
  Correcting that boundary is a prerequisite to M11 public-App acceptance.
- Family availability is currently probed when the federated assembly starts.
  Deploy both workers before the API and verify both families at API startup.
  Dynamic availability refresh is outside this slice.

## Options and selected approach

| Approach | Benefit | Limitation |
| --- | --- | --- |
| Unified API and two family workers, with bounded deterministic validation | Exercises the intended topology without Provider billing | Needs an explicit validation-only session adapter |
| Separate single-family API stages | Uses existing deployment settings | Does not prove switching within one Thread |
| Unified topology with Provider-only acceptance | Exercises normal Pi sessions | Requires separate billing authorization and cannot satisfy the first no-Provider gate |

Select the first approach. Reuse the existing application assemblies, prepared
runtime, Harness, PostgreSQL service, Domain Packs, and Authorities. Add only
the deployment and validation seams required to exercise them. A later,
separately authorized Provider check measures natural-language behavior.

## Deployment contract

| Role | Service | Application | Start command | Port |
| --- | --- | --- | --- | --- |
| Unified API | `capstone-api` | `capstone` | `/app/deploy/entrypoint.sh api` | `8080` |
| pandapower worker | `capstone-worker` | `pandapower` | `/app/deploy/entrypoint.sh worker` | `8080` |
| PyPSA worker | `capstone-worker-pypsa` | `pypsa` | `/app/deploy/entrypoint.sh worker` | `8080` |

All three backend roles use one tested source revision or one exact image
digest, and the cloud-development PostgreSQL ledger and private artifact
storage. Each worker starts with one replica and remains running during
acceptance: Thread Attempts use polling, so legacy session wake behavior does
not prove that sleeping Thread workers can resume.

The API configures `CAPSTONE_FAMILY_HEALTH_URLS` with both actual private worker
origins on port 8080. Its legacy session wake URL points to `capstone-worker`.
Each worker's wake URL points to its own private origin. Family workers receive
`CAPSTONE_FEDERATED_CATALOG_CONTEXT=true`; the entrypoint pins their execution
family. Health paths remain `/health/ready` for API and `/health` for workers.

Only API and App have public domains. `VITE_API_ORIGIN` contains the selected
API origin only. The App's public credential remains limited to registered
scripted sessions; Thread validation uses the existing private operator
authentication path. Tokens stay in protected environment or ignored browser
authentication state and never enter static files, screenshots, or reports.

No user-trial deployment, Provider call, source-trigger change, data migration,
or secret rotation is part of this slice. Existing cloud-dev data is retained.

## Public demo correction

Accept only allowlisted `scripted-demo` session creation with the public demo
credential. Reject `provider` mode, supplied Provider/model options,
unregistered cases, access to private or Provider sessions, and Thread routes.
Preserve private operator support for both existing session modes.

Align the legacy App's public session creation with this API contract. Keep
the server-side checks authoritative. Test request admission and subsequent
status, event, result, report, and evidence access. Existing Provider sessions
remain readable by the private operator, without being exposed to public demo
credentials. Do not migrate or delete them.

## No-Provider Thread validation

Introduce an explicitly selected cloud-development validation mode at the
application composition boundary. Default runtime behavior remains unchanged.
Reuse the prepared session-builder seam so model binding, current-run admission,
M9 projection, M10 topology generation, and public event persistence remain the
production path. Keep deterministic scripts in validation-owned source.

The adapter supports a finite, source-registered scenario set for `ieee39` and
`regional-six-bus`. It checks the exact model, family, context, and instruction
sequence before invoking published semantic capabilities. Numerical answers,
model revisions, results, evidence, and topology come from real Authorities.
Scripted decisions do not supply expected numerical results or bypass admission.

Unknown instructions and unsupported scenarios fail explicitly. This mode must
not fall back to a Provider. Selecting it must bypass Provider credential
resolution and ordinary-conversation LLM routing. Test that Provider session
construction is never called, even when protected Provider settings exist.

The remote driver submits normal authenticated Thread commands and reads
snapshots and event pages. It cannot supply code, shell commands, endpoint
URLs, tool names, or arbitrary tool arguments through the API. Reuse existing
validation contracts where they apply; do not expose the in-memory test host
as a network service or add a general remote execution API.

Validation mode is recorded in every receipt. Restore the normal configured
runtime after the deterministic checks and recheck health and catalog without
submitting Provider work. Do not describe this as a Provider-backed test.

## Acceptance matrix

| Check | Required evidence |
| --- | --- |
| Deployment identity | API, both workers, and App deployment IDs; backend revision/digests; explicit ports and application selectors |
| Catalog and health | Both family health probes pass; catalog contains the registered models from both exporters; counts derive from the registry |
| Family ownership | Real PostgreSQL Attempts for each family complete only through the matching worker; negative cross-family claim test passes |
| Context reuse | Repeated analysis of the current model uses the same active Context and Authority binding |
| Switching and reopening | One Thread switches from IEEE-39 to regional-six-bus; explicit reopen produces a fresh Context and records the reason |
| PyPSA topology | Completed prepared-runtime Attempt emits Authority-backed diagram/layer events matching its model context and revision |
| Results and evidence | Admitted result/evidence refs are current-run and match the selected model; invalid foreign references are rejected |
| Web replay | Refresh and reconnect reconstruct the same answer, result projections, and current-model diagram from API history |
| Safe focus | A valid current element focuses; foreign revision, unknown element, and historical-page focus are declined |
| Retained history | After worker restart, committed Thread snapshots/events remain readable; do not claim restoration of process-local Authority state |
| Reports and artifacts | Both registered legacy scripted application paths complete and expose report/evidence through existing endpoints; report this separately from Thread topology proof |
| Public access | Public credentials can run only registered scripted cases and cannot start Provider or private Thread work |
| No Provider I/O | Deterministic mode bypass tests and runtime receipts show that the validation invoked no Provider |

Use explicit deadlines for every remote poll. Record failures and skipped
checks separately; neither counts as a pass. A `200` health endpoint, catalog
entry, legacy case diagram, fixture replay, or source deployment alone does not
satisfy the remote M10 topology check.

## Verification and release sequence

1. Add focused coverage for public admission, the validation session seam,
   family ownership, and real prepared PyPSA topology events.
2. Run local integration and required release gates; rebuild the current API,
   workers, and App with `make capstone-local-rebuild`.
3. Record a concrete deployment manifest: cloud-dev project ID, service roles,
   tested revision, non-secret settings, startup order, and rollback state.
4. Deploy both workers, verify health, then deploy unified API and App from
   the recorded revision. Run the deterministic remote matrix and Web checks.
5. Save a bounded receipt under ignored `runs/` and a concise durable validation
   record. Record deployment identity, scenario/session/Thread IDs, pass/fail/
   skipped outcomes, and the explicit Provider exclusion. Include no secrets.
6. Restore normal runtime selection, verify health/catalog, and close only
   test-owned active Attempts/sessions. Preserve completed replay data.

If rollout fails, restore the recorded prior cloud-dev application settings
and verified revisions. Retain the existing database and bucket. Stop claiming
acceptance until the failed check is resolved. Promotion to user trial is a
separate release action.

## Ownership and exclusions

Application code owns runtime selection and public access. Domain Packs own
semantic tools and admission. Registered Authorities own all model and numerical
facts. The Kernel remains neutral. No raw Network/DataFrame crosses the public
boundary and no cross-domain reference grant is added by deployment.

This slice does not add new analyses, unrestricted deterministic agents,
cross-family calculations, model uploads, automatic coordinates, dynamic Pack
discovery, multi-replica Authority state recovery, or a new Thread report API.

## Owning sources

- [Framework architecture](../../architecture/capstone-framework.md)
- [Development lifecycle](../../architecture/capstone-development-lifecycle.md)
- [Railway operations](../../../deploy/railway/README.md)
- [M10 specification](2026-10-04-capstone-m10-pypsa-topology-provider-design.md)
- [M10 implementation plan](../plans/2026-10-04-capstone-m10-pypsa-topology-provider-implementation.md)
