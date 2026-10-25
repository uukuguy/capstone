# Large grid view and source gateway implementation

Status: authorized implementation. Owning design:
[scale-aware topology](../specs/2026-10-25-grid-topology-view-requirements.md).

## Scope and contracts

Preserve the existing conversation and formal model pane. Add source topology
to its resource views, not a new application or composer. Source station groups
are not electrical buses. Source topology is not a calculation model. Keep all
gateway credentials and upstream selection in the backend. No arbitrary MCP
tool names or endpoints may enter browser requests.

Each instruction determines its own resource scope. Explicit references win;
clear continuations may reuse accepted context; unrelated instructions do not
resume old tasks. Do not add a conversation-wide business goal.

## Execution slices

1. Finish the instruction resource-scope policy and focused context regression
   checks. Commit independently. Preserve stopped history and stored resources.
2. Implement an application-owned, typed, bounded source-topology API. Fixed
   discovery/scope/page operations only. Validate separate node/edge cursors,
   stable view references, source quality and explicit incomplete boundaries.
   Use the protected registered gateway connection; never expose credentials.
3. Implement a shared large-scene renderer and worker. Evaluate Sigma/Graphology
   against the needed electrical symbols and bounded viewport processing before
   selecting a dependency. Keep scene contracts independent. Use stable IDs,
   worker layout/index construction, indexed picking, sparse labels, cancellable
   loads and bounded visible geometry. Keep parallel circuits and source kinds.
   Route large formal diagrams before the legacy synchronous layout path.
4. Integrate source topology in the existing workspace. Provide scope selection,
   region/station/equipment drill-down, paging, search, source quality/details,
   fit/zoom/focus and revision-safe loading. Keep formal model selection intact.
   A source question freezes bounded source material. If a formal model is bound,
   create an explicit independent model-free enterprise session for that question.
5. Verify actual North China overview and expansions through the protected
   gateway. Test one source-backed grid question through a real task. Do not run
   power-flow from unverified source fields. Measure a 120k-node stress scene,
   actual edge count, layout/load time, frames, memory and picking latency on a
   named browser/device. Synthetic scale does not replace real source checks.
6. Run affected tests and types; canonical local rebuild when runtime source
   changes, readiness/image identity and scoped cache cleanup. Review changes,
   integrate via dev PR, verify the actual dev entry and refresh project control.

## Ownership and verification

Backend source contract/routes/protected provider and focused Python tests form
one unit. Renderer/worker/scene types and focused TypeScript tests form a second.
The coordinator owns workspace integration, real gateway/browser verification,
source-question handoff and canonical project records. Workers must preserve
each other's changes and unrelated user work. Review each unit and the integrated
branch. Do not use full release or unrelated solver suites for these slices.

Acceptance records distinguish implemented, locally verified, merged and
deployed states. Cloud/demo/main remain unchanged unless separately authorized.
