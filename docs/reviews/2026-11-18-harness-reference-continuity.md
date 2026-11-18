# Harness reference continuity

Scope includes a later instruction in one Work, automatic Goal iterations,
and Mission task handoffs. Acceptance requires the consumer to resolve and
read the exact prior product or result under its current grant. A successful
producer, a matching reference string and a persisted conversation are
separate checks.

| Path | Observed behavior | Status |
| --- | --- | --- |
| Native Domain Pack result to a later instruction | IEEE 39 tool execution produced a result. The first Attempt ended with empty admitted result and evidence arrays. The later Attempt received the reference in history text, then the Authority returned `unknown_result` in its task workspace. | The host now freezes an isolated Thread, Run and Work scope for model-free native execution. The registered Pack reads the same stored result from a later Attempt and rejects a different Work. Typed producer admission and older Attempt workspace migration remain open. |
| Native Domain Pack result across worker replacement | The hosted pandapower worker used the tool service's temporary directory. The confirmed result was outside the mounted run volume. | Hosted registration uses the existing run directory for the tool workspace unless an explicit path is configured. The local source directories were saved and copied to the existing run volume. |
| Previously admitted result to native main-chain context | The plan used an empty prior-result list even when the claim carried admitted results. Structural context also used a different visibility filter from the frozen list. | The plan now uses one visible set for both paths. Covered by a regression test. |
| Goal product to the next iteration | Settlement checked the proposal's products, then the continuation saved the next instruction and dropped the checked references. Input preparation could select other historical files in the Work. | Newly persisted continuations retain product references. Admission freezes completed files from the exact predecessor and checks their manifests. Historical continuations keep their existing read path. |
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

## Remaining acceptance

Validate typed producer admission, source selection and granted reads of
the exact prior result in both native model modes. Validate that the
answer keeps a ranking separate from an actual limit check. Test old
Attempt-scoped references through a verified migration. Run a Goal that reads an
exact file version after a worker restart. Run a Mission that passes both
a file and a typed result to a child and then to review. Check wrong owner,
missing object, and changed version. The result-only continuation must
make zero replacement calculation calls.
