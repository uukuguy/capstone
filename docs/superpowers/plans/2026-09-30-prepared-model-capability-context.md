# Prepared Model Capability Context

Implements the approved adapter and context-lifetime sections of
[the interaction design](../specs/2026-09-29-agent-interaction-discussion.md).

## Boundary and rationale

The neutral SPI resolves closeable handles. A trusted Capstone adapter prepares
each handle against the immutable model context. Its contribution remains
process-local; Thread persistence stores only exact identities. This step adds
the lifecycle seam, without inventing tool or Authority implementations. The
application's session builder consumes the prepared contributions and supplies
the execution/admission bindings; a legacy `ApplicationProfile` is not the
public contribution contract.

Context resources belong to the Run, not its Attempt lease. A process-local
owner reuses an exact context and rejects identity drift. Preparation is atomic;
failure closes all newly prepared contributions and handles in reverse order,
preserving cleanup errors. Explicit owner shutdown releases all contexts.
Production deployment stays disabled until concrete adapters and their public
tool/admission contracts are verified.

## Task 1 — trusted preparation and context ownership

Files: `capstone_agent/model_capability_context.py` and its focused test module.

1. Write failing tests for immutable-context preparation, empty selection,
   exact trusted adapter lookup, context reuse, drift rejection, and rollback.
2. Implement adapter registration tied to the catalog's exact identities, sealed
   before runtime preparation. Do not import Domain Packs or Authorities.
3. Implement context close/owner close that attempts every resource release,
   is idempotent, and preserves cleanup failures.
4. Run focused tests and package boundary checks.

## Task 2 — prepared Pi session factory

Files: `thread_application.py` and `test_thread_application.py`.

1. Write failing tests proving sessions receive the claimed immutable prepared
   context, preparation failure prevents session creation, and session stop
   does not close Run-owned resources.
2. Add a factory borrowing prepared contexts; clean up session-construction
   failures through the owning context preparation lifecycle.
3. Keep the existing injection path available for runtime comparison. Explicit
   shutdown closes the context owner; no hidden Context changes on retries.
4. Verify the worker/HTTP/SSE regression and catalog tests.

## Task 3 — record and verify

Run the Capstone Python suite, SPI tests, and package boundary checker. Record
the tested seam and remaining concrete Domain Pack adapter work in the live
checkpoint. Stage only task-owned paths; preserve the user's `.gitignore` edit.
