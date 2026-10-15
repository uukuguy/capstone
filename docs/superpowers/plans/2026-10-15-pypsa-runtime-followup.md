# PyPSA residual fixes and dev integration

> Execute with subagent-driven-development. Review each bounded change before integration.

**Goal:** Fix the two observed PyPSA defects, verify the original regional workflow,
and merge the existing fix branch into `dev` through its normal required checks.

**Architecture:** Applications resolve model identity and verified lineage. Domain
Packs retain exact result/context checks. The Authority applies saved schedules
to simulator inputs and owns all numerical results. No PyPSA semantics enter the
framework Kernel. Existing admission, evidence and handoff checks remain required.

## Candidate verification checkpoint

Both fixes are implemented and independently approved. AC Authority checks12+1
passed; projection checks141 plus61 after the final guard passed. Candidate source
c638e0992e49d300e760e89d07aff63ef6eca1c5 used one AMD64 backend for API/dual workers
and reused App source e2, with no same-source claim covering the App. The original
three turns passed; a generic AC-only fourth turn used saved results without new
dispatch. All five operations projections completed with correct revision/evidence.
Third-period southern-backup delta was9.999984503 MW; maximum AC residual was
approximately 0.00004649 MW (<0.01 MW). The isolated candidate stopped with data preserved.

PR #28 passed both required Linux/macOS jobs in CI38723131332 and merged normally
as f300d1f375ef20af005840a60af47b5e33ea62e8 at11:24:55Z. Root dev fast-forwarded;
its packages match tested c638. Canonical local-dev rebuild passed, exit0 and readiness true. API/dual workers
share image6c616058e643; each matches1060 tracked backend SHA256 files from clean
f300. The Docker source label remains development. App5173 reports f300, dirty=false.
Receipt: root .capstone-agent/pr28-local-dev-identity.json. No exact-label claim is made. Do not add documentation commits
to the product PR. Control/governance receipts will use a separate docs PR after
integration. The delivered e2 artifact does not contain these runtime changes.

The final answer has an arithmetic error (+5 instead of+7.5); retain this answer
quality finding. Source-modeling projections remain unimplemented; do not claim all
answers, projections or Packs passed. See [verification report](../../reviews/2026-10-15-pypsa-runtime-followup-verification.md).

## Constraints

- Work in `.worktrees/dev-trial-deployment`, branch `fix/user-local-network-view`.
- Preserve all existing data and the user's installation on port19173.
- Keep delivered source e2eaee2 and its archive/checksum unchanged.
- Keep withdrawn7c evidence; never distribute it.
- No VM, cloud-dev or demo deployment. Do not repeat the offline release suites.
- Use focused deterministic regressions, then one targeted original regional
  conversation with the already authorized OpenAI-compatible Provider.
- Normal dev PR and Linux/macOS checks are required; no administrator bypass.

## Task 1: Project each result with its verified model identity

Owners: application capability preparation/session modules and PyPSA model binding.

- [x] Reproduce mixed baseline/growth dispatch and AC results falling back as one batch.
- [x] Add an optional application-owned model-revision resolver to the existing
  neutral model binding; admit only verified related model references.
- [x] Resolve each admitted result's context and revision before projection and
  normalization. Keep the Pack's exact result/context equality check.
- [x] Preserve the baseline catalog revision and use the verified derived model
  revision for growth results. Reuse the host-only verified-context envelope.
- [x] Reject foreign references, invalid revisions, wrong evidence and stale identity.
- [x] Run focused model-binding, admission and multi-result projection tests; review.

## Task 2: Apply saved dispatch to AC power-flow inputs

Owners: `pypsa_model_authority/power_operations.py` and its operation tests.

- [x] Reproduce the three-snapshot regional mismatch using real Authority artifacts.
- [x] Apply the saved generator schedule through `generators_t.p_set`, the actual
  PyPSA power-flow input, instead of writing the computed `generators_t.p` output.
- [x] Check non-slack generator schedules and the final-snapshot southern-backup
  increment; account for slack loss balancing without calling convergence proof
  of schedule consistency.
- [x] Keep stored model identity, signatures, evidence and handoff validation intact.
- [x] Run focused Authority regressions and review the supported AC scope.

## Task 3: Verify and integrate

- [x] Review both diffs independently and commit only owned paths.
- [x] Verify the original three-turn regional workflow on an isolated candidate:
  baseline dispatch, immutable demand growth, growth dispatch/comparison, then
  the separately authorized AC-only fourth turn without redispatch.
- [x] Check actual Authority results plus completed projections with correct lineage.
- [ ] Update verification records, canonical worklist, recovery checkpoint and graph;
  preserve the independent delivered e2 node and put interim commits in history.
- [x] Create PR #28 targeting dev and mark ready.
- [x] Pass required Linux/macOS CI38723131332; no bypass.
- [x] Merge normally as f300d1f, preserve pending control copies and fast-forward
  root dev; packages match tested c638.
- [x] Complete `make capstone-local-rebuild`, exit0; verify readiness, same image,
 1060 tracked backend SHA256 files in each role and f300 App identity; data retained.
- [x] Record exact merged/local source f300 using file-based backend and App identity. Cloud/demo and19173 remain
  unchanged. Do not rebuild or replace an offline archive as part of this task.
