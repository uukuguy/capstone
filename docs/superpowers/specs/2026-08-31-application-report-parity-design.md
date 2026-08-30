# Formal Application Report Parity Design

**Date:** 2026-08-31

**Status:** Approved design; implementation planning pending review.

## Problem

The formal `make application` path reuses the pandapower Domain Pack and its
simulator authority, but it does not yet reuse the v1.0.1 application's
operator reporting behavior. The v1.0.1 `AnalysisRunner` writes an atomically
replaced `report.md` checkpoint after each turn and exposes accepted answers
throughout a long run. The generic `AgentApplication` currently invokes its
minimal `GenericReportShell` only after all questions finish. Its output lacks
the v1.0.1 report's business, evidence, trajectory, and audit detail.

This is a product regression. A formal pandapower application must not be less
observable or less informative than the compatibility application.

## Goals

1. Make `runs/<run_id>/output/report.md` available from application startup and
   refresh it atomically while the application runs.
2. Give the formal pandapower report at least v1.0.1's reader-facing richness:
   run status and progress, every question and accepted full answer, tool
   trajectory, pandapower business results, current-run result/evidence lineage,
   failures, and final replay/audit status.
3. Print human-readable progress to stderr for every question lifecycle and
   semantic tool event; preserve exactly one final composite JSON object on
   stdout.
4. Reuse and extract the proven v1.0.1 report/checkpoint logic rather than
   creating another unrelated, reduced report format.
5. Register only the final completed `output/report.md` as the immutable report
   artifact. Intermediate checkpoint versions are operator views, not final
   evidence references.

## Non-goals

- Do not change `make analysis` or `make report` v1.0.1 stdout behavior.
- Do not expose raw pandapower objects, DataFrames, files, shell access, or
  unadmitted simulator facts to the model or report.
- Do not make optional progress/report observation failures invalidate a
  simulator-backed answer that is otherwise valid.
- Do not add a second live-report filename or a separate dashboard as a
  substitute for `output/report.md`.

## Design

### One report file, two lifecycle phases

`output/report.md` is created when a formal application workspace is prepared
and is atomically replaced after state changes. During execution it labels
itself `running`, reports `completed/total`, and includes every answer already
accepted for the current run. After all required turns, report/audit/replay
completion produces the final version at the same path; only that version is
admitted into the immutable artifact registry.

The write sequence is:

1. application initialized: create the `0/N` checkpoint;
2. question starts: refresh question status and stderr progress;
3. each semantic Pi event: project it, refresh tool/trajectory state, and
   refresh stderr progress;
4. accepted answer or failed question: refresh the complete answer/failure
   section and progress counter;
5. application completion: add final audit/replay summary, atomically write,
   then admit the file as the final report artifact.

Checkpoint rendering is best-effort observation. Its failure is recorded as a
diagnostic but does not replace simulator truth or invalidate an otherwise
accepted primary answer. Final report creation/admission remains required for a
completed application outcome.

### Reuse boundary

The existing v1.0.1 report implementation is the source of report semantics,
not merely a visual inspiration. Refactor it into a shared, pure report
projection over a report snapshot:

- existing v1.0.1 adapters build that snapshot from `AnalysisContext` and
  `AnalysisWorkspace`;
- the formal pandapower application builds the same snapshot from
  `ApplicationContextStore`, `ApplicationWorkspace`, admitted turn records,
  trace records, and the domain presentation provider;
- the domain provider continues to own pandapower labels, results, constraints,
  risks, and business summaries;
- the generic Kernel remains domain-neutral and retains its generic fallback
  shell for other applications.

This keeps report detail reusable without coupling the Kernel to grid-specific
types or duplicating a second pandapower report renderer.

### Stderr progress contract

The product-level formal application entry installs a progress observer in
addition to the existing semantic projector. It emits compact, redacted stderr
lines for application start, `question i/N` start/completion/failure, Pi
heartbeat, tool start/result, and report checkpoint path. It may include the
accepted answer summary but not unbounded raw payloads or credentials. Full
accepted answer text belongs in the immediately refreshed report.

The observer is a fan-out: the internal projector continues to receive every
semantic event before the progress/report observer reads its projection. No
event may be lost from the stored trace or context because of presentation.

### Report content parity

The formal pandapower report retains the v1.0.1 reading order, adapted only for
the application vocabulary:

1. run/application identity, status, provider/model, progress, and timing;
2. reader summary and per-question complete accepted answers;
3. tool trajectory and bounded diagnostics;
4. pandapower model/context, power-flow, ranking, contingency, constraint, and
   risk summaries sourced from current-run results;
5. result/evidence lineage and artifact paths;
6. context/replay/audit status, including explicit failure explanations.

Framework `core` and `domains.grid` records remain available as supplemental
structured sections; they do not replace the operational report.

## Acceptance criteria

- A scripted formal application run exposes `output/report.md` before its first
  answer and the file changes after every finalized question.
- A running report shows the completed/total count, the complete accepted
  answers so far, and the latest tool/diagnostic state.
- A completed pandapower report includes every v1.0.1 baseline section above,
  current-run lineage, and final audit/replay information.
- The final report is admitted once, after application completion; checkpoints
  never become stale immutable report references.
- stderr shows question and tool progress while stdout remains exactly one
  `capability-agent-output/1.0` object.
- Failure of a checkpoint observer records a diagnostic without suppressing a
  valid primary answer; failure to create/admit the final report fails the
  application outcome.
- Existing v1.0.1 compatibility report behavior and stdout envelope remain
  regression-tested and unchanged.

## Verification plan

Tests must first demonstrate the current absence of a running report, then
verify checkpoint creation, update sequencing, answer visibility, tool progress
fan-out, final immutable report admission, and stdout/stderr separation. The
existing v1.0.1 report fixtures become structural content comparators for the
formal pandapower report. Provider-free scripted runs cover the full lifecycle;
one authorized provider run verifies the operator experience end-to-end.
