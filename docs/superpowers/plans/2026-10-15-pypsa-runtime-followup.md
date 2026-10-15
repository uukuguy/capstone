# PyPSA residual fixes and dev integration

> Execute with subagent-driven-development. Review each bounded change before integration.

**Goal:** Fix the two observed PyPSA defects, verify the original regional workflow,
and merge the existing fix branch into `dev` through its normal required checks.

**Architecture:** Applications resolve model identity and verified lineage. Domain
Packs retain exact result/context checks. The Authority applies saved schedules
to simulator inputs and owns all numerical results. No PyPSA semantics enter the
framework Kernel. Existing admission, evidence and handoff checks remain required.

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

- [ ] Reproduce mixed baseline/growth dispatch and AC results falling back as one batch.
- [ ] Add an optional application-owned model-revision resolver to the existing
  neutral model binding; admit only verified related model references.
- [ ] Resolve each admitted result's context and revision before projection and
  normalization. Keep the Pack's exact result/context equality check.
- [ ] Preserve the baseline catalog revision and use the verified derived model
  revision for growth results. Reuse the host-only verified-context envelope.
- [ ] Reject foreign references, invalid revisions, wrong evidence and stale identity.
- [ ] Run focused model-binding, admission and multi-result projection tests; review.

## Task 2: Apply saved dispatch to AC power-flow inputs

Owners: `pypsa_model_authority/power_operations.py` and its operation tests.

- [ ] Reproduce the three-snapshot regional mismatch using real Authority artifacts.
- [ ] Apply the saved generator schedule through `generators_t.p_set`, the actual
  PyPSA power-flow input, instead of writing the computed `generators_t.p` output.
- [ ] Check non-slack generator schedules and the final-snapshot southern-backup
  increment; account for slack loss balancing without calling convergence proof
  of schedule consistency.
- [ ] Keep stored model identity, signatures, evidence and handoff validation intact.
- [ ] Run focused Authority regressions and review the supported AC scope.

## Task 3: Verify and integrate

- [ ] Review both diffs independently and commit only owned paths.
- [ ] Verify the original three-turn regional workflow on an isolated candidate:
  baseline dispatch, immutable demand growth, growth dispatch/comparison and AC.
- [ ] Check actual Authority results plus completed projections with correct lineage.
- [ ] Update verification records, canonical worklist, recovery checkpoint and graph;
  preserve the independent delivered e2 node and put interim commits in history.
- [ ] Create a normal PR targeting dev; wait for its required Linux/macOS checks.
- [ ] Merge without bypass, preserve the main checkout's pending control copies,
  fast-forward its dev source, and use `make capstone-local-rebuild` to verify the
  canonical local entry point with existing data retained.
- [ ] Record the exact merged and local runtime sources. Cloud/demo and19173 remain
  unchanged. Do not rebuild or replace an offline archive as part of this task.
