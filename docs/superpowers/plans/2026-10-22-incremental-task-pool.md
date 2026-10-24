# Incremental Task Pool Implementation Plan

**Goal:** Make the organization engine plan incrementally and execute all work
through isolated task contexts using the existing graph ledger and scheduler.

**Architecture:** Publish shared planning1.1 and a new application profile with
isolated execution selected by trusted registration. Preserve legacy graph paths.
The engine owns goal completion and explicit acceptance, not native execution.

**Tech Stack:** Python publication and host configuration; existing Pi JavaScript
runtime, controller and subagent dispatcher.

## Constraints

Implementation checkout is model-decision. No Git index/ref, cloud/demo or auth
changes. No domain stages/counts, second ledger or invented checks. This plan is
executed sequentially in the active session; no worker delegation is needed.

## Tasks

### Follow-up: decision-bounded discovery

- [x] Add failing exact publication checks for shared1.2/App1.15 using unchanged
  Pack1.12; preserve hashes for all earlier catalog entries and policy resources.
  Test actual worker selection and new/old isolated flags.
- [x] Add `resources/task-planning-policy-1.2.md` with a decision stop condition,
  evidence-scoped claims and task-local quality ownership. Register it in
  `task_planning_policy.py` and `native_task_context.py`, append the catalog and
  application registration, extend exact graph/worker admission sets without
  replacing old profile IDs. Keep Pack resources and graph protocol unchanged.
- [ ] Run focused publication/consumer/SDK checks and doctor/diff. Freeze all
  changed production resources, rebuild with `make capstone-local-rebuild`, check
  API/worker identity and deployed policy bytes. Run one original-input trial
  using `run_trial.py --graph --autonomous`; stop abnormal loops and record actual
  scope, overlap, final products, tokens and wall time. Update control/recovery.
 Offline checks/rebuild/runtime67checks passed. Original133622 ran176.031660s,
 only one126.852047s profiling task, no report or overlap. This acceptance gate
 remains open. The new policy reached the planner but its committed contract
 still required full source profiling. Verify scope selection in a bounded
 planner-only check before another whole-report run; do not repeat prompt-only
 full trials. No additional semantic planning gate is implemented yet.

- [x] Add failing publication tests for exact new shared policy, old-byte retention
  and new selected application profile. Add runtime tests rejecting parent nodes
  and preserving discovery -> results -> added independent tasks -> synthesis.
- [x] Publish incremental planning guidance and adapter. Update trusted profile
  selection/configuration with an isolated-task execution flag.
- [x] Restrict new planner tools/schema and execution nodes; keep legacy behavior.
  Ensure explicitly assigned synthesis can produce the final deliverable.
- [x] Run focused publication/runtime and actual SDK-host chain checks. Review
  compatibility, immutable inputs, cancellation and unsupported sandbox claims.
 144JavaScript/154Python checks and5image checks pass. New role-specific process
 inventory replaces the old blanket native-tool requirement only for the planner.
- [ ] Freeze sources, canonical rebuild and verify actual runtime identity. Run
  one bounded original-input verification; measure graph expansion, task overlap,
  accepted products, usage and wall time. Stop abnormal loops.
 Source/rebuild/runtime65checks passed. Original043956 failed full goal after a
 successful first discovery and rejected full-set expansion. Incremental append
 was then repaired and real small045408 passed discovery/accept/append/synthesis
 and3-line saved delivery. Full business/parallel/performance acceptance remains
 open; no small-check time is compared with146seconds.
- [x] Update canonical dev control register/overview and recovery records with
  implemented, verified and unaccepted boundaries kept distinct.
