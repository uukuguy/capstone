# Common intent-to-execution projection

## Problem and change

The user's news trial completed recognition and ordinary execution, but the answer
repeated unrelated Domain Pack names. The private execution context had empty
object/capability projections and no domain tools. The information reached the
answer through free-text descriptions and missing-requirement explanations in the
full `IntentDecision`. This was a common data boundary problem, not a news routing
problem. The user rejected question-specific prompt tuning; those patches were
reverted before deployment.

Both ordinary and business builders now use `execution_plan_for` and
`capstone-execution-plan/1`. It projects operations, identities, task excerpts,
dependencies, readiness and application-generated blocker kinds. It does not
forward model-written descriptions, requirement explanations or clarification
questions. The original user instruction and shared source-labelled history remain
available. Intent receipts remain separate for diagnosis.

Native recognition supplies `instruction_excerpt` as exact user text. The
application validates source membership; it does not paraphrase, search keywords
or infer intent from the excerpt. Older injected decisions default to the original
whole instruction. Native recognition also supplies the boolean
`clarification_required`, so prose such as a string `"null"` cannot determine
readiness. Existing legacy injected contracts retain their prior fallback semantics.

The projection describes readiness only. Capability selection, active-model
checks, prepared tools, result retrieval and current-run evidence admission remain
under their existing owners. Its implementation and contract participate in the
Pi configuration identity. No answer postprocessor, package-name blacklist,
topic-specific policy or connector installation is added.

## General evaluation

| Dimension | Contract check |
| --- | --- |
| Daily operation | Original task text is retained without business diagnostics. |
| Text rewrite / follow-up | Historical message identities and native user/assistant history survive. |
| Professional concept | Concept discussion can be ready without calculation resources. |
| Catalog request | Requested catalog metadata remains available; it does not enable tools. |
| Business read / calculation | The same execution plan is used with prepared bindings and existing admission. |
| Missing external information | A structural unresolved requirement blocks execution without forwarding catalog comparisons. |
| Dependent mixed task | A blocked predecessor blocks dependent work; a separate independent task stays ready. |
| Ambiguous reference | Typed clarification state blocks execution; diagnostic question wording does not control it. |
| Model comparison | Historical object references are retained without granting cross-model execution or admitting evidence. |
| Non-interference | Changing only diagnostic wording produces exactly the same execution plan. Changing task/dependencies changes it. |

## Verification

- Red tests reproduced the missing projection and prose-based clarification state
  before implementation.
- Focused contracts, projection, native Pi, business builder and profile checks:
  190 passed. Pyright: 0 errors. Package boundaries and doctor pass.
- Managed Pi loopback captures actual preparation/execution requests through the
  worker with tools on/off and with/without shared history. Deliberately injected
  diagnostic text remains absent from every execution request. The source-bound
  task excerpt remains present. Existing no-domain-role/tool and empty-evidence
  assertions still pass.
- Full Capstone regression: 761 passed, 46 optional infrastructure tests skipped.
  The runtime suite also passes an added authorization check: diagnostic
  clarification text cannot let a ready business goal bypass capability grants
  (11 runtime tests passed).
- Source-distribution-to-wheel build passes; the new projection and contract
  modules and four native configuration files exactly match canonical source.
  Markdown relative links, the relative `CLAUDE.md` symlink and diff checks pass.
- The first local rebuild failed during pinned Pi npm installation with
  `ECONNRESET`, before replacing running services. The retry passed. API and both
  workers are healthy and share image
  `sha256:3167c7eb86054b38176064e73ce3934960666ffbdaeb5bc82ef96dda83132e96`;
  the local App is reachable. The shared projection and native configuration
  import successfully inside both worker environments.

## Acceptance boundary

The scenario matrix tests supplied semantic decisions and execution contracts.
Loopback uses local response fixtures. Neither proves real model recognition
accuracy or reader-facing response quality. No new external/billed Provider call
or remote deployment was performed. Actual Capstone acceptance must assess this
whole matrix, including contextual minimal pairs, instead of tuning one observed
answer at a time. Pure Pi comparison and skills/MCP configuration stay deferred.
