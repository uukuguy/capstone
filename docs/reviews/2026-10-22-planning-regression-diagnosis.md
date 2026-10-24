# Planning and early-closure regression diagnosis

Scope: read-only history and source inspection. No model calls, retries, runtime
changes, builds or Git mutations were made for this diagnosis. The user's two
reference sessions are local time2026-10-21 09:20:38 and13:45:06. These are planning
references; the145.914727second record remains the separate timing baseline.

## Recovered actual contracts

The worker's durable research channels retain the graph checkpoints even when
the executor's temporary mirrors are gone. Read-only extraction from those
channels is saved in ignored
`outputs/orchestration-repair-20261020/planning-regression-historical-contracts.json`.

| Local session | Initial declared tasks | Final declared/executed structure |
| --- | --- | --- |
|10-21 09:20:38|profile; price; flow; res; report|Five clear purposes. Three analysis nodes accepted; report awaiting assessment at cancellation.|
|10-21 13:45:06|intake; price; flows; renew; report|Intake accepted; all three children started; report pending when event persistence failed.|
|10-21 17:30:00|analyze|One parent task owns parsing, all three analyses, charts and report; completed. This is the146second timing baseline, not the planning-clarity reference.|
|10-21 23:59:39|profile; price; flows; renewable; report|Five tasks still declared and three children ran. No final report acceptance.|
|10-22 03:00:15|profile; price; flows; renewable; report|Five declared, only profile executed; it was limited, remaining tasks pending at finish. Do not call this a one-task plan.|
|10-22 03:39:28|profile|Later appended analysis_report, combining the three analyses and reporting into one parent task.|
|10-22 04:39:56|discover-sources|Only discovery ever declared; accepted, then finish. Full-set revision attempts failed before the append-only API repair.|
|10-22 13:36:22|profile-sources|Only this task ever declared; accepted, then finish, with no revise attempt.|

The13:45 failure was an actual binary preview containing NUL characters rejected
by PostgreSQL JSONB, SQLSTATE22P05. It did not prove failed task decomposition or
unavailable concurrent dispatch. Its saved audit establishes three starts within
0.477seconds. The09:20 graph also had actual three-way overlap after a revision.
Its execution/handoff costs were high, but its declared problem decomposition
remained clear. Neither run is a completed parallel-performance acceptance.

## Concrete changes and what they establish

1. Pack1.9 added cohesive/shared-preparation guidance. It still produced the
   user's13:45 clear five-task plan. That request also contained explicit parallel
   instructions;09:20 used the same original89-character request as recent trials.
   Thus user wording alone does not explain the regression. Pack1.10/App1.12
   further emphasized the smallest executable contract and shared preparation/
   rendering ownership, and introduced the240second work envelope. The17:30
   checkpoint proves that this publication could collapse the whole goal into
   one task. Timing order alone does not isolate one sentence as the sole cause.
2. Pack1.11/shared1.0 removed the earlier cohesive-planning paragraph and called
   for independent substantial questions.23:59 still declared five tasks. Later
  03:00 also declared five, but only one executed. The visible regression is not
   uniformly loss of declared tasks; failed/limited upstream results and early
   finish can also prevent later tasks from running.03:39 really did coalesce
   the remaining questions and report into one appended task.
3. Shared1.1/App1.14 changed to incremental next-batch planning and all-delegated
   execution. An initial single discovery task is consistent with that accepted
   mechanism. It became an incomplete implementation when later planning did not
   happen and a partial delivery closed the whole execution. Shared1.2 added a
   discovery stop condition, but13:36 proves that this did not repair termination.

## Exact latest stopping chain

All times below are relative to the13:36:22 Attempt start. The accepted work origin
has the same millisecond value. The native request timeout was1800seconds.

-17.763: the sole task starts.
-144.615: the child returns.
-151.266: its result is recorded.
-155.409: its result is assessed success.
-163.778: the model calls finish, outcome limited; product selection is rejected.
-168.333: the model retries finish with corrected references.
-168.759: the host commits limited delivery and closes the graph.
-176.032: the Attempt ends completed. The report and analyses remain unproduced.

There was NO revise call after assessment. The scheduler did not reject a next
batch, and no host deadline forced closure. The application work envelope starts
child wrap-up at165seconds, forbids new child dispatch at180seconds and sets a
soft total deadline at240seconds. First finish was even before the165second
boundary. The model's limitation says the shared work window expired/was
insufficient; it chose early closure rather than submitting later tasks.

The host validates selected references and current node assessments. A limited
finish needs explicit limitation text and admitted files, but has no structured
whole-goal completion/continuation judgment. Once delivery is committed,
continuationState returns null. runSettledPrompt then stops. The outer completed
Attempt is transport/execution completion, not proof of the user's whole goal.
The final response explicitly lists the missing report, so forgetting the goal
is not proved. Compact graph context also omits its goal field, but that omission
alone is not an established cause of this run's early finish.

Owning source: `resources/graph-work-policy-1.12.json`, graph runtime workStatus,
pump/launch, validateDelivery/finish and continuationState; SDK runSettledPrompt.

## Corrected conclusion and repair boundary

Calling this only long preparation was incomplete. Planning coalescence, declared
versus executed tasks, failed incremental expansion and permissive early limited
closure are different failures. Do not optimize elapsed time by accepting fewer
fulfilled requirements or treat a soft performance preference as a user deadline.

Preserve the accepted independent-task and incremental-issuance design. A single
initial task must leave the whole problem structure and unresolved requirements
alive. After result acceptance, the engine must decide overall completion, next
planning or a real blocker. A partial artifact/round closure must not silently
substitute for that decision. Fix these execution/goal lifecycle boundaries before
another paid full report or prompt-only scope experiment. Do not restore a fixed
five-task template or couple the mechanism to the three example research themes.
These are repair requirements from the audit, not implemented behavior.
