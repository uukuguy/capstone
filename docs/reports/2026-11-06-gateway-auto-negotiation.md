# Automatic gateway negotiation

Runtime source: df4ddf61d928f5e39f52358621bf8135afbccc4a.

Gateway identity/catalog negotiation belongs to the backend adapter. Initializing,
selecting or refreshing a gateway automatically obtains its current publication.
The UI no longer exposes a manual contract update button or lifetime session lock.
A conversation may select another instance for subsequent work; admitted task
snapshots and historical source references remain unchanged. Failed selection keeps
the previous preference. Admission checks the selected instance and frozen catalog,
not the deployment default gateway. Public failures retain their actionable message.

The live gateway added publication metadata. Exact-key validation incorrectly
rejected it; minimum required metadata is now validated while additive metadata is
preserved. Changed publication metadata triggers catalog refresh, with no per-field
adapter patch. This changes no caller permissions or allowed service endpoints.

## Validation

- Backend selection/admission/control checks:166passed,32platform skips, including
  isolated PostgreSQL selection and concurrency checks. Additional boundary subset:
  127passed/32skips. These overlap and are not summed.
- MCP publication/HTTP checks:69passed. A new additive-field regression failed first,
  then passed. Prior admitted publication snapshots remain unchanged.
- Client37focused checks, TypeScript and production build passed.
- Live local conversation: first turn10.44s; switch to三区研发, refresh, then same-work
  service query completed26.02s.
- Intranet63: first10.50s; switch to三区研发, refresh, same-work query69.75s.
- Dky3-66: first6.97s; switch to内网联调, refresh, same-work query58.84s.
- Original failed session refresh now succeeds and selection is enabled.
- Actual gateway publication with added metadata was accepted and57tools loaded.

## Deployment

All three dev installations run the same production source above. Each API/worker
pair uses one image. App bundles contain the exact revision. Defaults, credentials,
gateway choices, databases, object storage and task products were retained.
Only test-owned temporary PostgreSQL storage was removed. No CI was started.

Local canonical rebuild attempts exposed startup warmup, an image-layer limit and
build cache ownership failures; these were not counted as passing rebuild receipts.
The native image was flattened with its public OCI configuration preserved. Cache
ownership was corrected, then actual readiness and image parity were checked after
recovery. Authority inputs/locks stayed unchanged; their existing catalog was
schema-validated and rebound to the installed source identity. Remote images used
installed dependency layers and the same source patch. No business record query was
needed for this verification.

Private receipts, model event logs and deployment/cleanup logs are retained under
.capstone-agent/gateway-auto-20261106/. Main and the existing snapshot tag are not
promoted by this development repair. Local-only focused verification and the user's
lightweight development closeout authorization are used for integration; any
administrator bypass is recorded separately in the journal.
