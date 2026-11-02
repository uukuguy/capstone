# Enterprise resource upload implementation

Implements approved enterprise-design-final §9. Small-file inputs remain available until resource acquisition reaches the executor. Upload completion never means analysis completion.

1. Add `thread_resources.py`: versioned resource descriptors and resumable upload receipts over the existing Thread event ledger and ObjectStore. Store fixed-size chunks independently; publish an immutable resource only after bounded streaming hash verification. Repeated chunks must match. Reject changed content and scope mismatch. Resume from persisted receipts, not process memory. Bound each request, not total resource size to the model window.
2. Add authenticated routes in `thread_resource_http.py` and register beside material routes in host_api. Begin/status/chunk/complete/cancel are explicit. Return metadata, not storage keys or credentials. Storage quota and upload expiry are configurable. Cancellation/expiry prevent publishing and reclaim staged objects.
3. Adapt the existing upload control to select the published resource protocol, send File.slice chunks, show progress/cancel/retry, and resume selected local files against server receipts. Avoid browser base64 for large files. Distinguish stored from processable.
4. Extend task context with immutable resource references. Authorize bounded acquisition into Pi private workspaces through existing executor transport. Model receives descriptors and coverage; never full-file base64. Preserve resource version, byte-range locations and derived provenance. Uploaded resources remain data.
5. Verify >1GB actual transfer, interrupted/restarted upload, conflicting retries, cancellation, immutable publication and bounded memory; then actual task processing and natural feedback. Existing small report success does not satisfy this gate.

Start with step1+2 focused tests, including PostgreSQL persistence; then UI and task acquisition. No business-specific metrics or file names in the protocol. Do not claim GB task support until step5 passes.

## Upload interaction scope

Keep upload management lightweight. Use the existing conversation controls for file selection or drag-and-drop, progress, retry and removal. Do not add a separate file-management application, folder hierarchy or upload configuration workflow. Keep capacity checks, temporary-file cleanup and bounded resource acquisition inside the runtime. This scope does not reduce the GB-plus upload requirement or the real task-processing acceptance gate.

## 03:32 checkpoint

Steps 1–2 implemented and tested. Step 3 browser transfer, pause/reload/resume and persistent resource directory passed with 1,077,936,128 bytes. Step 4 remains open: scoped resource acquisition into the isolated Pi executor must precede task-processing acceptance in step 5. The UI must retain its unprocessed notice until then.

## Executor acquisition continuation

- Add regression coverage in test_native_resource_staging.py for capacity reservation, cleanup and receipt-quota independence; in test_general_pi_executor.py for explicit disk input directories and immutable resource identity.
- Move staging to inputs/.staging and task input snapshots to inputs/task-ID on a dedicated Compose volume. Keep receipt quotas and writable task tmpfs unchanged. The host owns inputs; only the selected task UID can read its files.
- Bound staging reservations, expire abandoned transfers, and remove task inputs after execution. Stream verification and copying; never load the full resource into memory.
- Rebuild with the checked-in local entrypoint. Validate actual resource reading, then create an enterprise research session through the App, upload source files through its control, request a report in natural language, and submit one ordinary revision request. Preserve the session, source files and outputs as acceptance evidence.
