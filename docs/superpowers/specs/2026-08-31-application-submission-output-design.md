# Formal Application Submission Output Design

**Date:** 2026-08-31

**Status:** Approved design; implementation planning pending review.

## Problem

The formal pandapower application produces an operator-facing `output/report.md`
and preserves per-turn `turns/<turn-id>/answer.json` artifacts, but it does not
publish the compact, standard submission stream that v1.0.1 exposes as
`output/answers.jsonl`. Operators therefore need to extract answers from a
report or internal turn artifacts before submitting a completed or still-running
application run.

The missing file is an application presentation/output concern. It must not
become part of the domain-neutral Kernel protocol.

## Goals

1. Publish `runs/<run-id>/output/answers.jsonl` for the formal pandapower
   application.
2. Match v1.0.1 exactly: one JSON object per line, containing only
   `question_id` and `answer_output`.
3. Atomically refresh the file after every accepted answer so it is useful
   throughout a long-running execution.
4. Preserve accepted answers if a later turn fails or the process is
   interrupted; the file remains a checkpoint and does not claim whole-run
   completion.
5. Keep report rendering and submission-output rendering application-owned,
   with no JSONL filename, schema, or formatting semantics added to the
   Kernel or Domain Pack contract.

## Non-goals

- Do not change the v1.0.1 `run`, `analysis`, or `report` stdout envelopes.
- Do not put reports, evidence references, diagnostics, execution state, or
  Domain Pack data into the submission file.
- Do not make a checkpoint write failure override simulator truth or erase an
  already accepted answer.
- Do not present an incomplete `answers.jsonl` as a successful completed run;
  completion still requires the normal application outcome and admitted final
  report artifact.

## Design

### Application-owned submission projection

The `grid-agent` pandapower application profile registers an application output
writer beside its existing `PandapowerApplicationReportShell`. The writer is
the sole owner of the `answers.jsonl` path, two-field envelope, ordering, and
atomic-refresh behavior. It builds each line from the application's accepted
turn records; it does not parse `report.md` and does not depend on a model-side
submission capability.

The Kernel continues to own only neutral lifecycle facts: question ordering,
accepted answer text, immutable turn records, and application failure/completion
state. It exposes the existing stable application/workspace boundary that
application output adapters already consume. It gains no knowledge of
`answers.jsonl`, v1.0.1 envelopes, or pandapower naming.

### Checkpoint lifecycle

1. When the pandapower application workspace is prepared, create an empty
   `output/answers.jsonl` checkpoint atomically.
2. After the controller accepts a turn, collect all accepted answers in input
   order and atomically replace the file with their JSONL envelopes.
3. If a later turn fails or execution is interrupted, retain the last complete
   checkpoint, containing only accepted answers.
4. The regular live `output/report.md` projection may refresh independently at
   the same lifecycle points. Neither file is derived from the other.
5. At normal completion, preserve the final `answers.jsonl` checkpoint and
   admit only the final `output/report.md` through the existing report-artifact
   lifecycle. The JSONL submission file is a standard operator submission
   artifact, not a report/evidence reference.

Atomic replacement ensures readers observe either the previous valid JSONL
document or a complete later version, never a partially written line.

### Failure handling

The writer is best-effort observation. A refresh failure is surfaced as a
bounded diagnostic and must not invalidate an otherwise accepted
simulator-backed answer. Its failure must not leave a misleading partial write:
the prior atomically written checkpoint remains intact. Creation of the initial
empty checkpoint follows the same diagnostic rule.

## Acceptance criteria

- A scripted formal pandapower application creates an empty
  `output/answers.jsonl` at workspace setup.
- After each accepted turn, the file changes atomically and contains all
  accepted answers, in original question order.
- Each non-empty line decodes to exactly `question_id` and `answer_output`;
  its values equal the corresponding accepted turn answer.
- A later failure leaves previously accepted entries readable and unchanged;
  it does not fabricate an entry for the failed turn.
- `output/report.md` remains available and independently refreshed with its
  existing reader-facing/audit semantics.
- Generic Kernel contracts and a non-pandapower application profile do not
  acquire the path, JSONL schema, or pandapower output writer.
- Existing v1.0.1 submission behavior remains regression-tested and unchanged.

## Verification plan

Use test-first development. First add focused application-profile tests that
fail because no JSONL checkpoint exists or refreshes. Then verify setup,
per-turn atomic refresh, strict two-field JSONL shape, original-order output,
and retention after a later failure. Run the focused package tests, then the
repository's supported `make doctor`, `make test`, `make test-e2e`, and
`make validate` gates. Provider-backed validation remains optional and is not
run without explicit credential/billing authorization.
