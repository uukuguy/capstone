# Task 2 — Work-owned research identity slice

Source:055a335f. Implemented and locally checked; integration acceptance pending.
This is the first Task 2 slice, not the complete protocol/Profile/frontend milestone.

## Change

Application-owned immutable WorkBinding and TaskContext records identify the Thread,
Work, research, goal revision, execution snapshot and selected resource references.
An empty model list is valid. These records describe context; they grant no authority
or tool permissions and contain no business indicators or workflows.

AttemptResearch can now restore its existing Kernel research store by Thread and
Work identity. It retains research across attempts, run changes, goal revisions and
model selection changes. Distinct Works/Threads have separate storage. A persisted
research identity mismatch is rejected before creating an attempt record. Existing
terminal-state proof and active-attempt checks still govern interrupted recovery.

Legacy callers retain their original model-owned storage keys, binding schema and
history. No files are migrated or deleted. New Work research and old model research
can coexist. Harness normalization preserves the Work context and checks research
identity without inventing a selected model or changing Authority evidence semantics.

## Verification

- Red tests demonstrated missing Work context support and model-required event
  normalization; both now pass.
- Identity/research suites:44 passed, including model A to model B across runs,
  no-model persistence, goal revisions, isolation, interrupted recovery, unchanged
  legacy history and malformed/mixed context rejection.
- Related protocol/Harness/worker/application suites:118 passed before the additional
  review tests. Full backend suite with all added tests:1332 passed,65 skipped.
- Three changed source modules:pyright zero errors/warnings.
- Independent review found no blockers; its requested negative and cross-run tests
  were added and passed.

The first full run had five failures in existing local HTTP relay/server tests.
Python detected macOS system proxies despite absent proxy environment variables.
Setting NO_PROXY/no_proxy for127.0.0.1 and localhost made the23 relay/server tests
and the full backend suite pass. No product code was changed for that environment issue.

## Remaining Task 2 work

Production AttemptClaim construction does not yet select TaskContext. No new public
Thread protocol or frontend workflow is enabled by this slice. The existing
conversation/professional entry remains the running application.

Task 2 still requires explicit legacy-to-Work association records, host allocation
and persistence of Work identity, Profile/native-vs-authority assembly, Thread v2
negotiation and object CAS, PostgreSQL changes, and the minimum frontend entry.
The current Work context is not an authorization grant or a substitute for lease
and goal checks. Production continuous execution remains Task 3.

The two application lines remain preparation-only until their required shared
capabilities run. The next user-visible milestone needs a running URL, source,
input prerequisites, saved output/source display and refresh/reconnect verification.

## Local runtime and integration

Canonical local-dev rebuild at055a335f passed. API and both workers share image
`sha256:4a4c6fb7199d3df92516dcbaa1a02024504e10b3e9f2ea69ffdd5c4da0647d7f`.
All1145 shipped Git objects per role match the source commit (regular file bytes
and symbolic-link targets checked separately). Receipt:
`runs/work-research-identity/local-identity.json` (ignored operator evidence).
Readiness passed; App reports055a335f/dirty=false. An existing Thread loads in the
real browser. No new task or external Provider call was submitted.

`make check-integration` passed, including39 E2E cases, registered workers,
offline/scripted validation, application instantiation and24/24 capability coverage.
The first identity-check script compared symlink contents to dereferenced file
bytes; after checking link targets explicitly, all objects matched. This was a
verification-script issue, not a source or runtime change.
