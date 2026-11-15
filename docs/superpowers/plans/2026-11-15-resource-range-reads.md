# Resource range reads implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task, with focused tests and review.

**Goal:** Read bounded ranges of admitted uploaded resources without full-file staging, retain exact durable receipts, and show them as partial input sources in the existing workspace.

**Architecture:** Application-owned ResourceRangeReads persists bytes and metadata under Thread/Attempt/task identities. A callable selected-resource reader adds a read_range method. Existing worker/native control transport carries range requests and bounded receipts; the native tool creates a private read-only fragment. Existing whole-file open stays compatible. The App reads bounded receipt projections beside current product sources.

**Tech Stack:** Python, PostgreSQL, existing private ObjectStore, native JavaScript SDK tools, TypeScript/React, pytest/Vitest. No new dependency.

## Global constraints

- Approved design: [resource range reads](../specs/2026-11-15-resource-range-read-design.md). Owner capstone-agent/capstone-app; branch feat/resource-range-reads-20261115; destination dev. Dependency: reviewed design d4814039 from dev51fc1cc1.
- No Kernel, Domain Pack, Authority permission, default tool sequencing or business-topic routing change. Only frozen uploaded resources are range-readable in this slice. Historical native products retain their existing whole-file path; adding range support for them needs a retained range-capable source contract.
- Every returned byte has exact resource identity, offset/length and SHA-256. A read receipt means bytes returned, not processing/understanding complete. No silent clipping or invented row/page semantics.
- Request/attempt/preview/I/O budgets are configurable application capacities, independent from upload quotas. Same request ID with changed arguments rejects. Exact retries reuse the committed result and accounting, including after source loss.
- Current local checks and real model calls are authorized. No CI/push/PR until separate explicit approval. Rebuild via make capstone-local-rebuild before runtime acceptance; preserve volumes/auth and clean only proven project build cache.

## Shared interfaces

```python
# Application backend; raw bytes remain on protected control transport only.
request = {'schema':'capstone-resource-range-request/1', 'request_id':'a'*64,
           'resource_id':'resource_'+'b'*32, 'offset':0, 'length':4096}
# manifest is the complete frozen capstone-resource/1 descriptor.
result = reads.read(thread_id, attempt_id, task_id, manifest, request,
                    checkpoint=control.checkpoint)
# result == {'receipt': public_receipt, 'content': bytes}
# selected callable reader gains .read_range(manifest, request, control).
```

Public receipt schema capstone-resource-read/1 includes read_id, thread_id, attempt_id, task_id, request_id, resource (complete descriptor), offset, length, sha256 and bounded preview. No object keys, credentials, raw private references or host paths enter public API. Preview declares bytes_read, truncated and text/binary/invalid-UTF8 status. Private persisted record includes fragment object identity. Transport/native may add only bounded content_base64 and generated task-private path.

```text
GET /api/v1/threads/{thread_id}/resource-reads?attempt_id=...&limit=...&cursor=...
 -> {schema:'capstone-resource-read-page/1', items:[receipt], next_cursor:null|string}
GET /api/v1/threads/{thread_id}/resource-reads/{read_id}
 -> public receipt (authorization and Thread ownership checked)
```

Pagination is stable and bounded; unknown/cross-Thread IDs fail. Producer Attempt comes from the selected public ProductRef, not a model assertion.

### Task 1: Durable range admission and storage

**Files:** Create resource_range_reads.py, tests/test_resource_range_reads.py. Modify continuation_resources.py, thread_resource_http.py, thread_service.py, configs/runtime/application-capacity.json and mirrored resources/application-capacity.json; focused existing resource/HTTP tests. Backend worker owns these files.

- [x] Write failing tests using real ResourceUploads and counting ObjectStore: crossing an upload-part boundary returns exactly the selected bytes, reads only intersecting parts, never calls full-file iterator.

```python
reply = reads.read(tid, attempt, 'task', resource,
    {**request, 'offset':chunk_bytes-2, 'length':4}, checkpoint=lambda: None)
assert reply['content'] == original[chunk_bytes-2:chunk_bytes+2]
assert reply['receipt']['sha256'] == sha256(reply['content']).hexdigest()
```

- [x] Run the new test with uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_resource_range_reads.py -q; confirm missing range admission is the failure.
- [x] Implement strict schemas, source/grant checks and range budgets. Persist private fragment before atomic receipt/accounting acceptance. PostgreSQL locks scope concurrent reads and retries; no storage I/O under a Thread transaction. A losing object write stays unreferenced, never visible as accepted.
- [x] Add tests for bool/float/negative/overflow/empty bounds, forged resource versions, mismatched request ID, cross-Thread/Attempt identity, cancellation, I/O deadline and byte/digest mutation. Deadline checks must bound slow I/O, not merely check after it returns.
- [x] Test memory and real PostgreSQL service recreation, concurrent retries, aggregate quota, missing source after accepted retry, failed persistence and unavailable retained fragment. List/read endpoints never expose private content paths or unbounded lists.
- [x] Add callable read_range to the existing frozen upload reader; reject historical-artifact ranges without falling back to full-file reading. Preserve __call__ whole-file compatibility.
- [x] Run affected resource/continuation/HTTP/capacity tests, commit only owned paths and report measured checks.

### Task 2: Native tool and bounded transport

**Files:** Create native_resource_ranges.py if needed. Modify native_resource_references.py, general_pi_server.py, pi_delegation.py, resources/resource-reference-tools.mjs and direct tests/fixtures. Transport worker owns these files; coordinate shared interface changes with backend worker.

- [x] Write a failing real native-port round trip and worker polling test: range request yields a typed pending request, is matched against the frozen catalog, calls reader.read_range, and sends bounded bytes/receipt over the existing protected control channel. Whole-file staging is not invoked.

```python
assert staged_whole_files == []
assert range_calls == [(resource, request)]
assert accepted_receipt['offset'] == request['offset']
```

- [x] Add agent_resource_read alongside existing agent_resource_open. Model parameters are admitted resource_id, offset and length only; call/request identity is generated mechanically from tool execution. Description explains partial coverage and optional whole-file processing without imposing first action.
- [x] Native port validates all response identities/length/digest, retains only the selected read-only fragment under generated task-private path, and returns bounded preview/source receipt. Reject symlinks, other task paths, forged receipts, oversized data and changed repeated IDs.
- [x] Preserve legacy resource_requests exactly; use a separate typed range request collection so older paths cannot silently interpret new fields as whole-file requests. Bound per-poll requests and each control document. Cancellation, I/O failure and unknown completion retain accurate status; do not retry another request identity.
- [x] Run existing resource JS fixtures plus focused native/transport tests. Confirm failures before fixes; commit independently and provide final transport interface to backend/frontend.

### Task 3: Existing workspace read-source display

**Files:** Create ResourceReadSources.tsx, resourceReads.ts and corresponding tests. Modify ThreadProductsWorkspace.tsx, threadClient.ts, threadHttpTransport.ts and focused tests. App worker owns these files.

- [x] Write failing parser/render tests for exact resource/version/hash/range, invalid page identity, producer Attempt selection, cancellation and session switch. Inject a typed client response, not invented Authority values.
- [x] Add bounded authenticated client read/list methods for the shared endpoints. Parse strict schemas, source ownership and cursors. Resource reads remain separate from ContextProductRef; do not loosen paragraph/row reference parsers.
- [x] Mount source list beside existing product sources for selected producer Attempt. Show name/version, bytes returned and partial-coverage label; open bounded preview on explicit action. Do not add another composer, message list or file manager.
- [x] Test refresh, late-response discard, changing selected product, no inputs vs failed source lookup, keyboard action and existing row/paragraph source regression.
- [x] Run focused Vitest, TypeScript check/build; commit App-owned files and report result. Parent performs actual Vivaldi acceptance against the existing workspace.

### Task 4: Compose and review

**Files:** Parent owns deploy runtime input allowlist, focused development gate/config/tool tests and docs/status worklist/control records. No worker edits them.

- [x] Run setup/install-pi/doctor in the fresh worktree before runtime tests. Run smallest existing resource baseline; setup failure is not product failure.
- [x] Review Task 1 and Task 2 transaction, security and recovery contracts together; correct mismatched field names at their owning boundary. Review Task 3 source provenance and bounded rendering. Retain actual task/producer IDs.
- [x] Add new runtime files to existing Docker COPY groups, not extra per-file layers. Create a focused macOS development route for this change and direct consumers, with classification tests rejecting unrelated solver changes. Do not run CI.
- [x] Run integrated focused real PostgreSQL + native fixtures + App tests/type/build. Independent whole-branch review; fix important findings with reproductions. Commit verified units and checkpoint frequently.

### Task 5: Current real large-resource acceptance

**Files:** Ignored runs/resource-range-validation-20261115/ receipts, checked-in measured review report, canonical worklist and control graph.

- [x] Canonical local rebuild uses protected root configuration mounts, exact candidate source, separate App candidate port and existing preserved volumes. Verify readiness and API/worker image identity; complete scoped cache maintenance.
- [x] Use >1GB actually transferred persisted data; record bytes, hash and upload/resume history. Hold fixture expectations outside model inputs. Read head/middle/tail and a cross-part interval; compare byte-for-byte, record actual object/control/disk bytes and peak memory.
- [x] Restart service/reader and perform precise accepted retry; compare receipt identity/accounting and source-loss recovery. Preserve all unrelated resources and data. No sparse-size shortcut or old performance number substitutes for current evidence.
- [x] Submit a real model task whose question needs bounded samples. Verify actual agent_resource_read calls and saved limited report. If model selects whole-file work, record it honestly and do not count it as range-read acceptance.
- [x] In existing Vivaldi Capstone tab inspect read sources, preview, refresh and session switch restoration. Original resource and old product digests remain unchanged. Capture screenshots in ignored evidence.
- [ ] Update plan/spec/worklist/register, regenerate actual dev control graph and inspect source/ancestry edges. Prepare exact PR and request one explicit focused macOS CI only after local acceptance is concrete. Merge to dev and verify its actual entry only after approved gate passes. No cloud/demo promotion.
