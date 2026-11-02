# Tool activation recovery

The model-visible tool menu and the SDK execution registry used to be the same
list. Replacing a menu removed SDK dispatch definitions. A later call to a
previously loaded tool therefore returned `Tool ... not found` before Capstone's
activation guard could run.

The session now keeps task-granted guarded definitions in the SDK dispatch
registry while projecting only the bounded active menu into the model request.
The projection runs before the SDK's canonical request capture. The capture and
the actual model request therefore contain the same selected tool schemas.
This uses the pinned SDK's public agent state and stream-function interfaces;
no managed SDK source is modified.

The common guard can restore a previously loaded frozen contract when it still
fits the existing count and schema budgets. Application admission and exact
argument validation still run before gateway execution. The requested call
executes once; this is not replay of a previous remote operation. First-time
unloaded tools return structured `tool_not_active` with a loading action.
Capacity failures return `tool_activation_capacity` with `executed=false` and
a bounded replacement-load action. Unknown and ungranted tools stay excluded.
Closing the discovery scope disables its guarded tools and restores the stream
boundary for the next execution mode.

There is no SQL-specific name, prefix mapping, or business routing rule in this
change. It does not refresh changed gateway contracts or relax drift checks.

## Local verification

- 44 focused JavaScript checks passed in about one second, including actual
  pinned SDK parent and managed-child sessions, real isolated composition
  workers, receipt preservation, cancellation and task admission.
- The SDK regression loads a tool, replaces/unloads it, rejects an invalid
  argument call, then restores a valid call. There is no `not found` result for
  the admitted tool and no duplicate remote execution.
- Count and schema budgets each reject over-capacity restoration before any
  remote call. Canonical request capture matches the actual bounded model menu.
- 22 relevant native-host checks passed; 32 environment-specific checks skipped.
- No CI, push, PR or cloud deployment was started.

The independent contract-reload/new-session prototype is preserved in stash
`5a205ae7f7a1ad4d21943e0dd99657d090dd6d1f`. It is not part of this change or its
deployment. Its lightweight timestamp/check contract still needs gateway input.

## Rebuilt runtime and visible trial

Source `9bba7449` passed the canonical local rebuild, readiness and scoped cache
maintenance. API and workers share image
`21dc558dc9098428b0aa684b750f67d57be1cfb063aa7957cac28d3fe6b35730`.

The visible browser submitted the unchanged five-substation CSV question in
`thr_ccc50b5efbdde3f64fc6` / `attempt_04ed87db65489b45`. It completed in43.6s,
with20model responses and29tool calls. No `Tool ... not found` result occurred.
The download has exactly five rows; SHA-256:
`09844baf004b0dd084724ec097027587a6660f373db02cf84902f8532e878a66`.
The runtime chose a source-backed relationship lookup route; no fixed expected
object list or tool sequence was introduced by this repair.

Three other errors occurred and recovered: contract lookup incorrectly passed a
tool name as `operation`; one shell command inspected a missing private-input
directory; one temporary jq expression had a syntax error. These are not marked
fixed or hidden by this change. The exact unload/restore case is proven by the
deterministic parent/child SDK checks above; this browser task checks the normal
real model, gateway and saved-product path.

Evidence: `runs/gateway-activation-recovery-20261031/browser-records.json`,
`browser-completed.png` and `downloaded.csv`. No CI was started.
