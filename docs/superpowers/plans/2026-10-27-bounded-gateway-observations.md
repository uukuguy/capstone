# Bounded gateway observations

**Goal:** Prevent successful data discovery and time-series queries from filling the model context while keeping exact source receipts and complete data available.

**Evidence:** User session `thr_d6a5d364641c974aea45`, attempt `attempt_4abd327e421a84db`, made40 parent model requests and no research children. Context grew above100k tokens repeatedly. Final three requests failed with no retained specific provider reason. Gateway responses and loaded output schemas were repeatedly injected in full. No PPT was delivered. Another user attempt was running during diagnosis; do not restart services until active attempts settle.

**Architecture:** Application-owned native tools retain large gateway/discovery results as JSON under their private task directory. The model gets an explicit incomplete preview, byte/hash metadata and a file reference. A host-only runtime projection restores the exact original result for observation admission; this never changes Authority truth or grants extra tools. Child paths use the child's private cwd. Existing small-result behavior stays compatible.

- [x] Reproduce bounded-context and exact-source restoration requirements in tests, including the actual pinned SDK.
- [x] Add shared projection/storage helper. Wire gateway results and discovery output contracts for parent and child sessions.
- [x] Verify original source receipt bytes, retained full files, preview size, task isolation and next-turn activation semantics. Model-visible result content is bounded to6000 characters; original JSON is retained privately and restored for host admission.
- [x] Record specific safe model-error classification during request completion when available; do not invent a cause for existing unclassified errors. Error type/status propagate through neutral runtime metadata into the App; raw provider text is omitted.
- [ ] Rebuild when no user task is active. Verify in Vivaldi using the reported business task and retain any missing data as limitations. Preserve prior observations and files.

Verification:21 JavaScript/actual-SDK tests,115 backend/transport/packaging tests,148 App tests and TypeScript pass. Regressions failed before the relevant implementation. Reported attempt remains failed; no claim of full business recovery before the real trial.
