# Control workspace perspectives

User-approved direction, 2026-11-17. Product implementation is incremental.

| Perspective | Audience | Primary view |
| --- | --- | --- |
| Task execution | The person who requested the work | Task board: requirements, dependencies, progress, decisions and deliverables |
| Runtime observation | Operations and runtime management | Control/Agent lanes: activity, waiting, handoff and abnormal observations |
| Development diagnosis | Developers | Linked execution trace and recorded context, for investigation and reproduction |

All views share task identity, execution identity and an observation boundary.
Navigation from an observation node must locate its source event. Returning must
preserve the original reading position. Absence of an observation does not mean
execution has stopped. A stop request and its acknowledgement remain distinct.

Task cards represent persistent tasks, not Agent instances. Show a stable order,
clear dependency/blocked status and version-bound products. A visual board does
not enable parallel scheduling. Current Control allows one active delegation.
Task verified state and final Goal acceptance are separate.
Cancelled work is terminal history, never successful completion.
Card selection updates details without rebuilding unchanged cards.

The first implementation reuses the existing Control entry, command recovery,
Thread/Work navigation and product readers. It does not replace the enterprise
conversation layout or create another composer. Full workspace navigation and the
other two perspectives remain unimplemented. The accepted prototype lives in
ignored runs/control-workspace-design-20261117 in the development checkout.

Control owns its persistent state and future state-change events. Agent owns
execution and Thread events. App owns bounded projections and navigation.
Existing Agent event_id/event_seq are useful source identities; Control observation
sequence is not a Thread event sequence. Polling differences are not real events.
Historical/current states must be labelled separately until as-of reconstruction
exists. Cross-source time ordering alone does not establish causality.

LoopX source references used for this design:
goal-channel-frontstage.ts (status/waiting/next action and user/agent work),
goal-work-map.ts (current focus and explicit prerequisite lineage), and
delivery-review.ts (delivery-centred views, coverage and source references),
under 3th-party/loopx/apps/presentation/dashboard/src/data/.

First delivery and focused acceptance:
[task-board plan](../plans/2026-11-17-control-task-board.md).

## Incremental implementation, 2026-11-17

Task board PR135 and Control-event PR136 are accepted in actual local-dev.
The next App candidate implements three perspective controls in the existing
sheet. Runtime lanes combine current task observations with a fixed prefix of
Control events; they do not combine Agent Thread events or claim as-of state.
Diagnosis locates the exact Control event and the bindings recorded in that event.
Current Goal revisions can advance while the reading boundary remains fixed.
Refresh is explicit; pages use the server's fixed through-sequence. At most500
events are held in one reading window; arbitrary historical-window navigation is
not yet available. Empty legacy coverage is not treated as stopped execution.

The task board remains mounted while perspectives change. Runtime scroll, selected
event and return focus remain attached to their source node. Workspace/Goal changes
reset isolated reading state; late requests cannot populate the new Goal.
Actions that change the task remain in the task perspective. Original conversation
components own execution/products. Full workspace shell, Agent trace correlation
and reproduction execution remain unimplemented.
[Current plan](../plans/2026-11-17-control-runtime-views.md).
