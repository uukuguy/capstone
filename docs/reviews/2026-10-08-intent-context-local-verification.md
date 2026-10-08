# Semantic intent and shared conversation: local verification

## Scope

Implements the approved [conversation context design](../superpowers/specs/2026-10-08-capstone-conversation-context-design.md)
and [execution plan](../superpowers/plans/2026-10-08-capstone-intent-context.md).
This supersedes the earlier interpretation that entering Pi proves ordinary-answer
support. Classification, context preparation and actual response quality are
separate acceptance concerns.

## Implemented behavior

- Hosted pandapower and PyPSA use an independent, replaceable intent recognizer
  before runtime resource preparation. Pi is the initial model adapter.
- Keyword routing and keyword fallback are removed. Catalog answer projection
  no longer infers intent or scope from sentence patterns.
- Ordinary and business messages share bounded Thread history. Model changes
  retain historical object identities from ledger records. Failed partial answers
  are not admitted as completed history. Both stages receive truncation metadata.
- The validated decision selects goals, references, capability needs and explicit
  dependencies. Unavailable weather can block a dependent calculation while an
  independent goal remains executable. Unknown or disabled resources grant nothing.
- Pi loads application configuration from versioned files via supported native
  mechanisms. A trusted extension supplies native user/assistant history and
  bounded request data. Ordinary execution omits the domain role and domain tools.
- Intent preparation has one terminating structured tool and no native session
  persistence. Startup installs/checks are disabled without disabling Provider calls.
- Input, engine identity, result retrieval candidates and catalog are frozen for
  retry. Later results cannot enter an older Attempt through the execution stage.
  Pi settings, protected transport configuration, runtime identity and policy
  participate in the configuration digest; drift fails explicitly.
- Business execution prepares only the required enabled profile subset. Selection,
  model identity and current-run Authority evidence rules remain application-owned.

## Verification evidence

- Independent review found rollback forwarding, global settings binding, native
  intent-session persistence, retry result drift and historical object gaps.
  These were fixed. A follow-up truncation metadata issue was also fixed.
- Isolated PostgreSQL checks passed: 78 tests covering history, Attempts, SQL
  persistence and model workspaces. The test database was removed after use.
- Managed Pi tests passed: 17 tests, including loopback SSE and actual worker/ledger
  execution with calculation tools enabled and disabled. Exactly one preparation
  request and one ordinary execution request were captured. No domain preparation
  occurred; result/evidence references stayed empty. Historical messages retained
  native roles and did not enter the system prompt.
- Focused integration tests verify recognition failures, cancel, configuration
  drift, fixed result/catalog resources and rollback forwarding.
- `make doctor`, changed Markdown relative links, the relative `CLAUDE.md`
  symlink and `git diff --check` pass.
- `make capstone-local-rebuild` passed. The API is ready and the Vite App returns
  HTTP 200. API and both workers use image
  `sha256:6cbdd252aac1cf7913f23f60894a05319c77c6373fe6d8c4cd84ce525addc09b`.
  Direct factory checks inside both running worker containers return
  `IntentRuntimeFactory` with an available `plan_intent` node.
- Release checks passed types (0 errors), the backend and App suites, 39 E2E
  tests, 3 registered-worker tests, offline/scripted/application validation and
  the capability matrix (24/24). The general Capstone suite reports 735 passed
  and 46 skipped; separate PostgreSQL/native Pi checks above cover the relevant
  optional infrastructure.
- The release command then exposed a source-distribution packaging fault:
  wheel-only forced inclusion referenced configuration outside the unpacked
  package. It is replaced by a relative resource-directory symlink to the
  canonical `configs/runtime/capstone-pi` files. Hatch includes the actual files
  in both artifacts. A fresh source-distribution-to-wheel build passes; installed
  configuration assertions were added to the package gate. Both archives contain
  four regular configuration files that exactly match the canonical source. The
  final local rebuild and `make test-packages test-source-setup` pass. All
  `check-release` subgates are therefore verified across the initial run and the
  focused packaging rerun; the initial aggregate command itself exited at the
  packaging failure. Unchanged functional suites were not repeated.

## Remaining real-model scenarios

Evaluate each scenario through the local App, with calculation tools both enabled
and disabled where applicable. These are acceptance cases, not completed results.

| User request and context | Expected behavior |
| --- | --- |
| Grid discussion → unrelated greeting or writing request | Answer naturally, without pushing the user back to grid analysis. |
| Grid answer → “Translate that answer” | Use the shared answer text; do not rerun the calculation. |
| “Today's international news” | Explain the unavailable live source briefly; do not invent news or append an unsolicited grid task menu. |
| Grid discussion → weather for an unrelated trip | Treat it as an independent task and preserve the grid conversation. |
| “Check tomorrow's weather, then use it to assess this grid” | Identify the dependency and missing source; do not fabricate weather or silently run the dependent calculation. |
| “Explain N−1, and also check tomorrow's weather” | Explain the independent concept and state the missing weather capability. |
| Model switch → “Compare with the previous model” | Identify both historical objects; clarify or request the needed business transition instead of inventing current evidence. |

Record the decision, selected resources, answer, preparation/execution duration
and usage for both stages. A correct scripted decision is not evidence that the
configured model recognizes these minimal pairs.

## Acceptance limits

No external/billed Provider validation or remote deployment was performed.
Loopback responses validate transport, configuration and execution contracts;
they do not prove real model intent accuracy or answer quality. User evaluation
of ordinary Capstone answers remains open. Pure Pi comparison stays deferred.

Weather/news connectors and skills/MCP installation are not added. Requests that
need an unavailable live source must explain the missing capability. Historical
model identity helps references and clarification; it does not authorize executing
against a different active model or admit historical results as current evidence.

The first implementation uses bounded recent history with explicit truncation.
It does not add an automatic long-term summarizer or arbitrary history retrieval.
