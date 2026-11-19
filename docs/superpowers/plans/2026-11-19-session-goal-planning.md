# Session Goal planning and execution

Owner: capstone-agent, with capstone-app projection. Destination: dev.
Implementation branch: feat/session-goal-planning-20261119.
Baseline: PR #152 merge 4df0217a.

## Accepted boundary

Harness completes one instruction. The session's main Agent plans and pursues a
Goal across instructions in the same Thread and Work. Mission can organize
multiple Agents across Threads for broader objectives. Goal uses the existing
session, grants, model selection and admitted references.

## Implementation order

1. In the Goal command and ledger paths, persist planning intent before admitting
   execution. Bind the intent and each accepted plan revision to the current
   Thread, Work, objective revision and generation. Use a bounded structured
   planner response with acceptance criteria and a concrete first instruction.
   Keep the old Goal schema readable. Reject stale or duplicate planning results.
   Test that a new Goal cannot queue the raw objective as its first instruction.
2. Run each planned instruction with the normal Harness delivery contract. Store
   the exact plan step and Attempt association. Once the terminal record and
   products are durable, queue a typed review for the same main Agent. Admit one
   review per applicable boundary. Review can verify a step, revise the plan,
   block for input or propose completion. Bind completion to all current
   acceptance criteria and exact admitted results. Continue through the existing
   versioned command path. Pause, deadline, budget and restart apply at each
   boundary. Test same-Thread continuation and lost-wake recovery.
3. Give planning, execution and review separate status and safe error codes.
   Persist stage, Attempt or review identity, error class and correlation ID.
   Keep raw model input, credentials and exception text out of public records.
   Fault-inject a terminal write failure after artifact publication. Verify the
   files remain available and the cause or failed stage is visible after refresh.
4. Present criteria, current step, next step, evidence and failure state in the
   existing conversation and execution views. Reuse current controls. Run a real
   Goal that needs at least two distinct instructions. Inspect initial planning,
   second-step evidence, restart or refresh, and final acceptance. Check real
   terminal settlement when products were published before a failure.

## First test

Submit start_goal with a valid objective. Assert the Work exposes pending Goal
planning and no work Attempt contains that objective as its instruction. Admit a
valid first plan revision, then assert one Attempt exists with its exact first
step instruction. Exercise both memory and PostgreSQL service entry points.


## Local verification

- The first live test stopped at planner admission because the Provider echoed the
  objective. A later test saved both deliveries and stopped at final review.
  The Provider adapter now discards the echoed objective. Final review accepts
  prior admitted references and retries a failed review from the saved delivery.
- Local backend source `ef7c3af6`, image `sha256:3b14ae1c13e8f43db9b53eb5e35e1dacb41e3504e76dfd795f0c89d10ba59159`.
  API and all three workers used the same image and passed readiness.
- Real Thread `thr_38b08d60160509262c51` completed two instructions. Attempt
  `attempt_6625351ef31ec970` saved the source. Attempt `attempt_c5ca7c378ecf26b2`
  read the saved source and published the report with total 71. All four criteria
  were met. Receipt: `runs/session-goal-planning/live.json` in the feature checkout.
- The scoped local gate passed 263 backend and 209 App tests and the App type check.
  After the review retry change, 107 focused tests passed with disposable PostgreSQL.
  Fault injection verifies the stage and error code survive lease expiry.

- The existing Vivaldi Capstone tab restored the saved completed Goal after a
  refresh. The plan showed step 2 of 2 and the right pane restored the report.
  Plan expansion has a scroll limit to keep the report and transcript visible.
