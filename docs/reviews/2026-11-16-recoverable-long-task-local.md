# Recoverable long-task execution: local evidence

Status: implementation in progress; whole capability not accepted.
Owner capstone-agent/capstone-harness; branch
feat/recoverable-long-tasks-20261116 targets dev. Design approved2026-11-16.

## Execution ownership

70beeab3 introduced expiring execution authority. 6abb3aa9 connected protected
owned admission and independent HTTP renewal, and added a conservative local
host lease deadline. Lost renewal acknowledgements retry the exact sequence;
status reads and duplicate admission never extend authority. Accepted task
receipts remain the existing durable protection against repeating unknown work.
The native image adds the two modules to its existing source COPY group.

Focused local Python3.12 checks passed288, skipped32 existing conditional cases
in40.58seconds. These include localhost HTTP admission, renewal, expiry and
host guard loss, and transport/server/worker consumers. Managed Pi setup needed
repair: an unowned stale shallow.lock was preserved, not deleted; process-scoped
proxy installation and doctor passed. No credentials were copied.

## Process termination independent from output

A new regression blocked the output callback while a real child remained live.
Before the fix, cancellation could not stop that process until the callback
returned. The process now has an independent watchdog for cancellation and its
deadline. Stop is serialized; a failed cleanup retains its process handle for
retry. A queue wake-up race initially misclassified cancellation as premature
EOF; the reader now checks revocation/deadline again after waiting for a frame.

The process suite passed85 cases in15.46seconds. It covers cancellation and
timeout during blocked output, cleanup retry, existing process/runtime consumers.
macOS uses the existing single-child fixture for process cleanup; it does not
establish Linux process-group or UID isolation acceptance.

An isolated Linux container separately exercised the candidate process module
against a real task UID10000 and a child in a new process session. With the
output callback still blocked, cancellation stopped both processes in observed
0.0468seconds. The worker thread remained blocked until the test released its
callback, then returned InterruptedError. The test had no network, credentials,
business data or persistent volume. The source module was mounted read-only on
the prior backend image0381ea6b; this is a focused process test, not a candidate
image build or deployed-runtime acceptance. Initial test setup used an image's
non-root default user and failed privilege setup; the isolated test was rerun
as root with a task-specific unprivileged UID, matching native-runner ownership.

Receipts/scripts: ignored worktree runs/recoverable-long-task-20261116/,
linux-process-guard.py and linux-process-guard.json.

## Remaining acceptance

Canonical candidate rebuild and real worker loss still need validation. Also
pending: actual executor/API restart, ambiguous admission/completion, short
transport loss, safe uncertain-effect handling, exact historical continuation,
long-context/resource bounds and existing conversation restoration. The
isolated process result does not close any of those requirements. No new CI,
cloud or demo deployment was started. Full goal stays active.
