# Harness reference continuity

Scope includes a later instruction in one Work, automatic Goal iterations,
and Mission task handoffs. Acceptance requires the consumer to resolve and
read the exact prior product or result under its current grant. A successful
producer, a matching reference string and a persisted conversation are
separate checks.

| Path | Observed behavior | Status |
| --- | --- | --- |
| Native Domain Pack result to a later instruction | IEEE 39 tool execution produced a result. The first Attempt ended with empty admitted result and evidence arrays. The later Attempt received the reference in history text, then the Authority returned `unknown_result` in its task workspace. | The host freezes an isolated Thread, Run and Work scope for model-free native execution. The Domain Pack verifies result and evidence content. The native host forwards the verified receipt to Harness, which stores it in the completed Attempt. The next native instruction reads receipts in its frozen history and model scope. Older Attempt workspace migration remains open. |
| Native Domain Pack result across worker replacement | The hosted pandapower worker used the tool service's temporary directory. The confirmed result was outside the mounted run volume. | Hosted registration uses the existing run directory for the tool workspace unless an explicit path is configured. The local source directories were saved and copied to the existing run volume. |
| Previously admitted result to native main-chain context | The plan used an empty prior-result list even when the claim carried admitted results. Structural context also used a different visibility filter from the frozen list. | The plan now uses one visible set for both paths. Covered by a regression test. |
| Goal product to the next iteration | Settlement checked the proposal's products, then the continuation saved the next instruction and dropped the checked references. Input preparation could select other historical files in the Work. | Newly persisted continuations retain product references. Admission freezes completed files from the exact predecessor and checks their manifests. Historical continuations keep their existing read path. |
| Goal result to the next iteration | A real automatic continuation carried the admitted result and evidence but received no Application catalog from the native worker. The model could only find gateway and general tools. | When current publication is unavailable, continuation uses the exact completed predecessor catalog from the same Work and model selection. Memory, PostgreSQL and real automatic continuation checks pass. |
| Mission files to a child or review | The existing grant freezes producer, artifact descriptor and digest, checks the destination Work, and verifies bytes on read. | This is the established file path. The audit found no equivalent in that grant for a Domain Pack result or evidence handle. |
| Native final reply | A separate failure receipt pointed to the answer-envelope marker count after the tool succeeded. A later live attempt produced complete answer JSON followed by tool protocol closing markers. | Formal/core answer parsing accepts the single valid two-field JSON object with redundant envelope markers or the exact observed tool trailer. Ambiguous replies still fail validation. |

The general continuation path must preserve the producing Attempt, Work,
workspace, owner, product kind and immutable version. It must authorize the
consumer before resolving content. Reuse the existing Harness admission and
the owning reader for each kind. Domain Packs and registered Authorities
retain result and evidence resolution. Product storage retains file
resolution. Text from an earlier answer supplies context and does not grant
access to a referenced object.

## Local checks

- 259 focused agent tests passed. A separate disposable PostgreSQL run
  passed 155 Goal, Mission continuation and Work tests. Ten hosted and
  Domain Pack lifecycle tests passed.
- A real Goal published `draft.md` and `decoy.md` in its first Attempt.
  The next Attempt had a single historical input receipt for `draft.md`
  and read its exact bytes. The original and final downloads matched their
  recorded digests. The final file contained the marker that appeared
  only in the original file.
- A regression check covers pausing an active Goal iteration without
  discarding its prior input references. Resume uses the same frozen
  predecessor as automatic continuation.
- After a local worker rebuild, a registered `gridctl` read of the
  original result returned the same line ranking from the mounted run
  volume. This was an operator read. The original Thread's native
  continuation still lacks the admitted read grant.
- A new model-free enterprise Thread completed two real Attempts in a
  single Work. The first ran AC power flow once. The second returned the
  same result reference after a successful branch ranking and made zero
  replacement power-flow calls. A different Work could not read that
  result in a registered tool check. Both terminal records still have
  empty typed result and evidence arrays. The reply also added a limit
  assessment without executing the limit check. This validates stored
  result access and sorting only.
- Focused regression checks cover the missing-content case and the full
  Harness route with a synthetic Authority owner in memory and PostgreSQL.
  The first Attempt commits both references. The next Attempt receives them
  in structured context. A different reference in the answer text receives
  no admission. The Domain Pack excludes missing or mismatched evidence.
- The local Compose candidate with backend image `9f89bd44…` verified
  both native model modes with real model calls. Model-free Thread
  `thr_5b6d275e17f982c14df3` and open-model Thread
  `thr_c145277b0ea73df2c25a` each committed the exact same result and
  evidence references in both Attempts. Each second Attempt ran the branch
  ranking tool and made zero replacement power-flow calls. The top line
  indices were 21, 11 and 26, with 73.37%, 67.15% and 65.73% loading.
  The replies added a limit conclusion without reading the model's limits.
  A fresh canonical rebuild with backend image `44a06b36…` retained
  the open-model Thread. Attempt `attempt_409a574337a87466` read the same
  result and evidence after worker replacement and made zero replacement
  calculations. Its formal answer and core summary both withheld a limit
  assessment and explained that the relevant limits were unavailable.
- After rebuilding `a43f2819` with backend image `aa0b05ce…`, real Goal
  `thr_90578a87fde437ac5c86` reached completed through two Attempts.
  The producer `attempt_b7af5889e9007cdc` omitted result references from
  both its answer and its next instruction. The consumer
  `attempt_091a986f1bfa3093` had two structured handles and the saved
  domain catalog in its frozen input. It read and committed the exact
  result and evidence with zero replacement power-flow calls. The local
  memory and disposable PostgreSQL verification suite passed 33 checks.

## Remaining acceptance

Recover older Attempt-scoped references by verifying the recorded
execution identity and rechecking the content with the owner. For Goal
continuity, verify a named result or evidence selection and the same
grant after a worker restart and after pause and resume. For Mission continuity,
bind each typed reference to the verified producer and the specific
consumer. Exercise the same handoff to a child and then to review. Check
wrong owner, missing content and changed version. Each result-only
continuation must make zero replacement calculation calls.

The initial relay covers verified result and evidence handles. Model
selection has its existing frozen management record. Domain tool context
handles, gateway handles and other owner-issued references still need
their own versioned readers and admission contracts before they can be
transferred. The registered issuer establishes ownership, and the grant
establishes permission.

The Mission file grant in `delegation_resources.py` verifies a completed
producer record, then binds the saved artifact version to a specific
consumer Work. Apply the same checks to the Authority receipt before
dispatching a dependent task or final review. The receiving pack must read
the exact granted reference through its registered authority. Keep the
producer workspace private and deny reads outside the receipt.
