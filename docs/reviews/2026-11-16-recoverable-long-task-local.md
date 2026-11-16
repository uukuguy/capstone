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

## First real worker-loss trial on candidate bd1a16bc

Canonical root rebuild passed with seven exact candidate runtime files over
dev44abf3c5; source-identity.json records their hashes. API/three workers were
healthy on image3f589fafc08b4deeda5f0e188eb7d338b14f5e59e824e54f39e4c3841b850e13.
Scoped build-cache maintenance completed. A preliminary synthetic task finished
before the fault boundary; its guard prevented any worker kill. It remains a
separate observation, not a worker-loss pass.

Fresh real Thread thr_5259a6db7acb55b4d2ba saved draft.md and entered its long
tool. A ledger guard proved it was the only active attempt. The operator killed
and restarted only capstone-worker-native-1. Native task
pi-4fb6d05ca190d77b316e0275a715a6867c71dbf55e0a5a8c3fdde0b215548f4c
automatically reachedcancelled at29.3426seconds after observer start near the
kill. No cancellation request or manual cleanup was issued. UID12370 had three
processes before the fault and no processes after automatic cancellation.

The trial also exposed a remaining defect: the idle restarted worker did not
reap the expired attempt until a normal Thread snapshot read. The old-claim
observer timed out, so this trial does not claim its stale-write assertions
passed. No fault was repeated because of that observation timeout. Snapshot
read then sealed the28-byte draft incomplete and recorded attempt_interrupted.
New attempt attempt_9faa1ad498f9e187 read that exact historical source through
the protected reader, emitted historical_input_delivered and completed with
recovery-check.md2059bytes. Independent downloads matched both descriptors;
draft hash84b1d27e8b614ee4ddb67697d4345252320d4e7ce7ffce14e18b5a3e5d5596b6,
report hashc14b50270969af38a4db03cca30f7bf27836ced582a97fb4acd823b76b31ae6d.
No final.md was admitted. Receipts: root ignored
runs/recoverable-long-task-worker-loss-20261116/.

Two red-first scheduling regressions reproduced missing idle reaping for both
single and multiple execution slots. The fix adds lease maintenance every
max(1,min(10,lease_seconds/3))seconds while keeping admission wake-driven.
This intentionally replaces the former zero-ledger-reads idle policy with
bounded recovery reads. The worker/recovery/wake direct consumers passed52
cases in11.48seconds. This fix still needs a rebuilt real trial without any
snapshot read before ledger interruption.

## Remaining whole-capability acceptance

The idle recovery correction needs canonical rebuild and real validation. Also
pending: actual executor/API restart, ambiguous admission/completion, short
transport loss, safe uncertain-effect handling, exact historical continuation,
long-context/resource bounds and existing conversation restoration. The
isolated process result does not close any of those requirements. No new CI,
cloud or demo deployment was started. Full goal stays active.
