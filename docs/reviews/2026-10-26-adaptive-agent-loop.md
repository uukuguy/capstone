# Adaptive loop and Deep Research verification

Status: local candidate; PR67 targets dev. Cloud and demo are unchanged.

The default instruction path uses a lightweight reasoning/tool loop. Deep Research
is inactive until the agent chooses task organization. App1.19 selects Pack1.16
and shared policy1.6. Historical policy publications remain unchanged. The new
session button creates one conversation without a type picker.

## Measured real execution

Both cases used the real Provider and registered data gateway in the existing
Vivaldi tab at localhost5173. Backend candidate6f61185f ran image
`98482c8e0ac449c132cc20acdaa5a85a115af37fc30b66814923cf76f3eaa660`.

| Case | Receipt | Result |
| --- | --- | --- |
| Model inventory | attempt36e273a93479fde7 | 12.542486s; one gateway call, seven scopes, no graph or children |
| Previous same-query baseline | attempt2399e56e3202d7aa | 91.583562s; mandatory organization despite202ms inventory call |
| Query then Deep Research | attempt4f3af7f303878605 | 98.652914s; one gateway query, three tasks, saved Markdown |

The second case explicitly asked to query first, then activate Deep Research.
It verifies delayed activation and source reuse, not autonomous selection quality
across arbitrary requests. Children read selected frozen observations as raw
sources; those sources did not become Authority results or accepted graph results.
The UI showed task steps and the saved4538-byte
`b808554812adaebf-grid_model_scope_notes.md`. Downloaded bytes matched SHA256
`9dfcfa8c2c79891084a8b78bdba96e104907d28a22644b4e639c3f4006f924fc`.
Delivery was explicitly limited: one node's proposed observation association
was not admitted; its findings remained unverified text. This did not cause a
whole-task repeat. Thinking remained available in a
compact collapsed record. Root ignored evidence is in
`outputs/adaptive-loop-20261026/`.

One record call needed a local reference correction; no whole task repeated.
The planner also attempted one native call after activation, which the execution
guard rejected. Commit20ae9445 narrows the subsequent model tool menu after an
accepted plan. Its21 focused SDK checks pass; final runtime verification follows
the canonical rebuild. No claim is made that heavy research now takes only seconds.

## Focused checks and review

- Python190 checks passed in7.81s; App41 checks passed in4.11s; TypeScript passed.
- Graph/runtime/SDK133 checks passed; the added direct-source receipt client check passed.
- Kernel request tests20 passed; broader scoped Kernel tests60 passed during implementation.
- Synthetic81-checkpoint ledger median fell333.6ms to176.9ms by avoiding duplicate
  historical replay inside one locked request. This is not a measured claim about
  every live checkpoint.
- Independent review identified source restoration and pre-admitted source issues.
  Both were fixed; follow-up review found no remaining Critical or Important blocker.
- CI initially failed an optional-policy type check;1321831d fixes it and local
  pyright reports zero errors. Required PR validation and actual dev integration
  are separate from these local results.

Visible interruption check: attempt0e6afeba93767b94 was cancelled while its tool
was waiting. The next unrelated instruction, attemptcbef9effac145242, returned
only `5`, with no tool calls or resumed write. An earlier30-second probe completed
before cancellation; it is not counted as an interruption success.

Role-specific safeguard ce185a14 retains ordinary tools for Deep Research
execution roles; only the organizer menu changes after an accepted plan.
All22 focused SDK checks pass.

Remaining closeout: final rebuild and narrow runtime handoff check, refresh
recovery, required dev PR gate, actual dev entry point,
and canonical control graph inspection. No old Work goal is authorization to
resume a stopped instruction.
