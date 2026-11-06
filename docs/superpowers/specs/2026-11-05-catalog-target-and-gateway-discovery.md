# Catalog target and gateway discovery correction

Status: approved revised direction by user “继续”.

## Revised default execution direction

The user rejects an expensive independent intent planner for each instruction.
The default native conversation must not invoke a recognition or context-selection
LLM before execution. Reuse the existing native conversation path, freeze admitted
context and capability publications, and let the execution model answer or select
authorized tools/skills directly. Complex planning is on demand in that execution,
not a mandatory preflight. Explicit professional entry points and recovery of
already-frozen decisions retain their existing contracts. Code checks permissions,
schemas, ownership and evidence at tool boundaries. Do not add a replacement
classification model or keyword router.

The catalog target changes proposed below are no longer the primary implementation:
the new default path must not enter the catalog_lookup static model shortcut.
Keep old accepted decisions recoverable. Confirm current capability/skill discovery
is visible in the execution model and preserve real domain tool access.

## Evidence

63 attempt_afa1dde6c77bb62d asked which data gateway tools were available.
Its persisted decision described that task correctly but selected catalog_lookup
with general-pi. delegated_runtime.py then called complete_catalog_answer with
full_catalog_requested=True. That function projects application registered
models. No gateway discovery ran. The user screenshot confirms the wrong output.

The recognition projection also drops the admitted general executor data_gateway
publication. Its generic description names business model packs but gives no
bounded description of the selected gateway. This weakens service selection.

## Options

1. Change only prompt wording. Small change, but the ambiguous operation still
   permits the same deterministic substitution. This is insufficient.
2. Bind deterministic catalog output to an explicit admitted catalog target and
   preserve generic discovery through the executor. Also publish bounded service
   metadata to recognition. Recommended.
3. Remove deterministic model catalog output entirely. Simpler routing but loses
   the existing bounded completeness guarantee for explicit model listings.

## Proposed contract

Recognition selects the relevant resource semantically. An application model
catalog projection requires an explicit typed target bound to the current
admitted application catalog. A generic catalog_lookup alone cannot grant that
target. Missing or other targets must never be converted into a model list.
Existing persisted decisions remain readable; no new target is inferred from
their descriptions or the user's words. Generic service discovery uses the
authorized general executor. An unknown reference fails validation.

Use the existing published gateway contract for a bounded recognition summary:
selected service identity, availability, purpose and discovery entry points.
Keep credentials, endpoints, full schemas and full tool catalogs out of this
projection. Use only admitted metadata; describe unavailability accurately.
Actual tool descriptions and schemas remain owned by the gateway adapter and
are discovered on demand through existing authorized execution mechanisms.

No keyword routing, provider-name special cases, fixed first tool call, copied
gateway credentials, invented tool names or automatic business queries.
Discovery follows the service selected for the current instruction.

## Acceptance

Regression: a gateway catalog goal must not call the model-table projection.
An explicitly selected admitted model catalog retains complete bounded output.
Test missing, invalid and historical targets; preserve mixed-goal dependencies.
Verify recognition metadata reflects selected/disabled/unavailable gateways and
does not contain protected values. Check affected intent schemas, execution
paths and direct consumers locally.

Real63 acceptance repeats the user's question and paraphrases, demonstrates
actual authorized gateway discovery and tool descriptions, and preserves visible
Thinking plus refresh recovery. A separate model-list request must still work.
No full solver suite or CI. After local canonical rebuild and focused acceptance,
align63,66 andlocal to the same source with idle guards and protected backups.
Record source identity separately from dev integration and performance results.
