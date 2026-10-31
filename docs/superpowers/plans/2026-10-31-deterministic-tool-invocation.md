# Deterministic Tool Invocation Implementation Plan

**Goal:** Raise configurable tool capacity, execute returned actions without rewriting identifiers, and expose useful safe diagnostics.

**Architecture:** Keep application capacity in its canonical profile, tool identities in the shared resolver, and business constraints in gateway contracts. Extract error summaries before truncation. Reuse recorded observations for returned actions and failed saves.

**Tech Stack:** Python, Node.js workers, TypeScript/React.

## Global Constraints

- No CI, push, PR or release gates. Run focused local checks only.
- No fixed business tool, provider, table or field names in runtime code.
- Preserve original observations, frozen task grants and existing user data.
- Use the existing browser tab and canonical local rebuild once source checks pass.
- Execute inline; no worker delegation required.

## Task 1: Configurable discovery capacity

- [ ] Add failing discovery tests for default256, override1024, large contracts and explicit capacity diagnostics.
- [ ] Add application profile fields and wire the frozen runtime limits into discovery.
- [ ] Keep request/model input budget separate from publication output size; expose load capacity and configurable search page sizes.
- [ ] Run discovery and application-capacity local tests.

Files: configs/runtime/application-capacity.json; resources/general-tool-discovery.mjs; resources/general-sdk.mjs; tests/fixtures/tool-discovery.test.mjs; tests/test_application_capacity.py.

## Task 2: Exact actions and source validation

- [ ] Add failing tests for copying returned action arguments, unknown/failed observation references, admission boundaries and save errors after successful reads.
- [ ] Implement tools.follow(ref,pointer) through the existing identity/admission/call execution path; never accept replacement arguments.
- [ ] Validate dataset call/pointer and retain successful call references on composition failure.
- [ ] Run semantic-context and composition fixture tests.

Files: resources/semantic-data-context.mjs; resources/tool-composition.mjs; resources/tool-composition-worker.mjs; their fixture tests.

## Task 3: Safe and readable error diagnostics

- [ ] Add failing tests using nested MCP errors, long gaps, request IDs, protected values and unchanged original responses.
- [ ] Extract error fields before bounding output and update frontend structured-content parsing and legacy fallback.
- [ ] Run progress and frontend feedback tests plus affected type checking.

Files: progress.py; tests/test_progress.py; capstone-app/src/threadFeedback.ts and test.

## Task 4: Verify and record

- [ ] Inspect diff and task ownership; commit verified task changes without push.
- [ ] Rebuild local source through make capstone-local-rebuild, verify readiness/source identity and scoped cleanup.
- [ ] Reuse existing browser tab for smoke verification; do not replay failed business reads implicitly.
- [ ] Update reports, recovery state and control register with implemented/verified limits and pending gateway coordination.

## User-requested trace display restoration

- [x] Reproduce missing tool purpose in collapsed summaries and missing child-response first-line intent.
- [x] Reuse one first-line-comment parser for streamed parent responses and recorded response text.
- [x] Show recorded operation in every tool summary, preserving tool identity in details/secondary text.
- [x] Place purpose directly after LLM label; restore red slow-duration styling with scoped selectors.
- [x] Run46 affected App checks and TypeScript checking; browser verification pending rebuild.
