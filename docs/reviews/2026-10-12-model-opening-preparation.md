# Model-opening preparation

## Delivery scope

The user requires complete model-opening preparation, including new-model
activation, restoration, capability changes, first-instruction reuse and
recovery. Creation and workspace opening are distinct user entry points;
both use the application's capability catalog and the same worker-owned
preparation and bounded context cache. No question-specific system policy,
keyword routing, automatic object substitution or Authority calculation was added.

Sourcea634257 removes separate initialization implementations. Thread creation,
new workspace opening and legacy switches call `initialize_model_context`.
New opening resolves the model catalog once and uses that pinned descriptor
for binding. Legacy entries without a context must still match the requested
revision and family. Restoring a context bypasses new initialization.
An actual regression failed before this fix when a second catalog resolution
changed; the corrected opening resolves once. Two legacy revision tests also pass.
111 focused checks passed, then68 creation/workspace/real-PostgreSQL checks
passed after the extra revision tests; types, boundaries and review passed.

Source55174b1 adds durable preparation requests, generation/lease fencing,
pending-context identity freezing and automatic retry. Actual switching found
that a new workspace model omitted the application's default selection.
Source9843b04 binds that default when opening a new model and preserves an
existing model's selection, including an explicit empty selection.

Source8ec1e1a places the frozen-route invariant inside the existing two-call
compilation correction budget. The outer admission check remains in place.
It does not change routing, business selection or evidence admission.

## Verified source checks

- 99 focused checks passed, including34 real PostgreSQL checks. Workspace and
  PostgreSQL checks then passed58 tests for application defaults and restoration.
- 64 routing/compilation tests passed for bounded route correction.
- Pyright, package boundaries, doctor and independent source review passed.
- PostgreSQL checks cover pending model/selection identity reuse, concurrent
  selection updates, restart, expired leases, old acknowledgements, more than
  one batch without another wake, failed preparation retry and query recovery.
- The owner preserves exact model/run/selection identity, capacity, idle expiry
  and cleanup. Simultaneous first execution waits for the same preparation.
- Acceptance covers the current one-worker-per-family deployment. A process
  restart has a new cache; caches are not shared between replicas.

## Actual9843b04 lifecycle verification

Canonical rebuild passed. API, both workers and clean App match the source;
513 source files per backend role match imageb905b6e0. Private receipts are
`runs/task-answer-closure/source-9843b04.json` and
`runs/task-answer-closure/model-preparation-9843b04.json`.

Before any instruction, IEEE-39 prepared one nonempty default profile. New
case14 prepared one additional profile. Restoring IEEE-39 preserved the exact
context and added no workspace; its first instruction added no workspace.
Workspace counts were0→1→2→2. Sending an instruction immediately after opening
also created exactly one workspace.

First post-preparation overview took5879ms; routing1225ms and compilation1789ms.
Immediate first instruction took6941ms, including2288ms of preparation queue
waiting; routing968ms and compilation1212ms. There were no task attempts before
opening-time preparation. Fresh case14 preparation waited2241ms; cached restore
waited48ms. Cold initial creation3561ms and preparation wait4331ms are separate
from instruction understanding; these are measured observations, not guarantees.

## Actuala634257 unified-entry verification

Canonical rebuild and exact-source proof passed: API and both workers match
514 files and image8d64370f; App is cleana634257/local-dev. Actual lifecycle
verification passed opening before instruction (no task attempts), new case14
binding, exact IEEE-39 restoration, first-instruction reuse and early submission.
Workspace counts remain0→1→2→2; early submission created exactly one workspace.
First post-preparation overview5869ms (routing1320ms, compilation1840ms);
early instruction6903ms (preparation queue1926ms, routing991ms,
compilation1563ms). Neither instruction repeated model initialization.
Receipts: `runs/task-answer-closure/source-a634257.json` and
`runs/task-answer-closure/model-preparation-a634257.json`.
Whole business acceptance below belongs to8ec1e1a; a634257 changes only shared
model initialization and is covered by focused checks and actual lifecycle,
not a claim that another complete business suite was run.

The generated project control graph passed desktop/mobile layout, both spacing
limits, four source bindings, no overlap, no independent edge crossing and no
edge through another card. Doctor and diff checks passed. The model preparation
is delivered to local-dev; dev/main and cloud/demo are separate acceptance lanes.
Actual browser restoration showeda634257, the completed overview and an enabled
instruction composer. Receipts: `unified-opening-app-browser.log` and
`unified-opening-control-browser.log` under `runs/task-answer-closure/`.

## Overall regression remains a separate gate

Actual9843b04 receipt115711f64191415d failed2/10 turns. Keep that receipt,
matching semantic facts and latency. Do not replace it with a later pass.

One ordinary overview compiled general goals after a frozen professional route.
The mismatch was checked outside the correction loop; source8ec1e1a fixes that
generic admission placement. Actual8ec1e1a receipt371209e3d9b14d97 passed all10
automated turns; matching semantic facts and latency remain archived. The
preparation repeat also passed, with first overview4786ms (routing916ms,
compilation1142ms) and early instruction6422ms (queue2106ms, routing475ms,
compilation1147ms). Exact three-role source/image and clean App checks passed.

The load-change turn selected internal index31 for the user's bus label31 and
compiled a powerflow/impact goal without the requested limit-check conclusion.
The Authority correctly found no load at that index. Two semantic review calls
did not repair the proposal. This is a business-compilation identity/coverage
risk, not a preparation failure. Changing the object automatically after
resolution would rewrite frozen semantics and is not an accepted repair.
Reliable closure needs explicit identity-selection grounds and conclusion
coverage contracts. Keep this risk open; do not claim that preparation closes it.

Independent raw goal/tool/Authority review of8ec1e1a passed9 business turns and
1 routing-only turn. The load turn used name31, P/Q×1.3 and a limits goal;
the changed load19 result was11.96MW/5.98Mvar. Explicit index7 outage results
matched line11 loading103.329% and bus35 voltage1.0636p.u. Three overview
turns used frozen information without prior-goal or calculation pollution.
Routing was454–660ms; overview turns3739–5559ms. Performance remains open:
load105589ms total,95422ms execution; ordinary AC23626ms, outage39676ms.
These are downstream execution measurements, not a routing delay.

No dev/main integration, baseline promotion, cloud/demo deployment or Research
R1 completion is included. PR13 remains draft; relevant Issues remain open.
