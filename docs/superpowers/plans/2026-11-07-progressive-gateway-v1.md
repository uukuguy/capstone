# Progressive gateway v1 implementation

Goal: Use the published resources/read extension without full tools/list, preserve
exact admission and version-bound dispatch, and load only selected tool schemas.

1. Add adapter tests for negotiated handshake, bounded resource responses, exact
   fingerprints, output declared/absent, pagination drift and zero-list dispatch.
   Keep protocol names and upstream URI construction in data_gateway_mcp.py.
2. Represent unresolved tools as metadata, never as permissive fake schemas.
   Add a task-granted relay operation that resolves selected exact contracts.
   Preserve frozen catalogs, grants, receipts and asynchronous reference checks.
3. Update SDK discovery and composition to resolve selected contracts before menu
   activation, preflight or execution. Retain standard adapter fallback once.
4. Run focused local Python/Node/type checks; commit coherent owned changes and
   checkpoint. Rebuild through the canonical entrypoint, with scoped cache cleanup.
5. Verify local real HTTP and model paths, count tools/list through first execution,
   measure startup/contract/model phases separately, verify source failure metadata
   and existing execution record. No 63/66 access, no CI or CI-triggering push.

Protocol: sibling data-gateway/docs/integration/Capstone渐进契约发现协议-v1.md.
Backend starts from54555fa9; current local backend1f26fd30. Source and runtime
must remain distinct in reports. Integration into dev remains pending required
PR/CI authorization. Preserve root unrelated work and all runtime data.
