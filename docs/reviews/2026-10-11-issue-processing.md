# Manual Issue processing — 2026-10-11

This is the earlier processing snapshot, not the latest acceptance state.
Later formal-answer and local-dev verification is recorded in the
[local acceptance report](2026-10-11-task-answer-local-dev.md) and the
[current version register](../status/VERSION-CONTROL.md).

Trusted policy/source: main `c3b78bc17aed1cc49f41c89b25069a2545ac7a3d`.
The user requested Issue processing. The independent publisher was verified as
`capstone-xiaoshi[bot]`, limited to `uukuguy/capstone`. No separate model call,
scheduled task, cloud deployment or Issue closure was made.

| Issue | Current workflow state | Evidence and remaining acceptance |
| --- | --- | --- |
| [#1 History](https://github.com/uukuguy/capstone/issues/1) | `ai:release-pending` | PR #6 merged to c3b78bc; local-dev history and reading-position checks pass. Original local-demo scope remains on ed2524f. A short verified integration reply was published. |
| [#2 Formal answer](https://github.com/uukuguy/capstone/issues/2) | `ai:working` | Shared `answers` package on feat/task-answer-closure. Initial Pack/application tests pass, but independent review found transport and semantic-obligation admission defects. The fix wave must pass review and actual local-dev acceptance before a PR. No completion reply was published. |
| [#3 Answer scale](https://github.com/uukuguy/capstone/issues/3) | `ai:working` | Same approved answers package. Language, scale and mixed ordinary/professional responses are under correction. User-observed 74-second latency is not a confirmed Provider or startup cause. No completion reply was published. |
| [#4 Recovery](https://github.com/uukuguy/capstone/issues/4) | `ai:needs-info` | Screenshot and controlled lifecycle checks identify a possible recovery path, but not the original cloud cause. One question asks whether the page was backgrounded or the phone locked before recovery. No sleep setting changed. |
| [#5 CI](https://github.com/uukuguy/capstone/issues/5) | `ai:release-pending` | PR #6 candidate cfd6ad6 passed exact Linux/macOS CI run38074539207 and merged to c3b78bc. Local-dev acceptance exists; demo scope is still pending. A short verified integration reply was published. |

## Issue #4 diagnosis

The screenshot shows an active attempt, ready workspace/history and PyPSA
tools, and pandapower still preparing. Its exact deployed source is unknown.
The current deployment must not be assigned to that earlier screenshot.

On c3b78bc, the activity hook releases hidden pages even during active work.
When visible again, it waits for workbench preparation. The separate Thread
subscription also stops when hidden. Four focused checks pass: the existing
three lifecycle checks and a controlled hidden → visible busy-page probe.
The latter enters `idle`, then `preparing`, and waits for preparation to finish.
This matches the accepted hidden-page policy. It is not proof of an unintended
pause, a stopped server task, or the original cloud latency cause.

Three current local-dev warm preparation reads finish in 0.0237, 0.0079 and
0.0087 seconds. All projected components become ready. These are warm local
measurements, not cloud cold-start measurements. Historical cloud-dev timing
on another revision does not establish the cause or acceptance of this Issue.

The diagnostic workspace is `.worktrees/issue-4-recovery`, branch
`improve/issue-4-active-recovery`, source c3b78bc. Setup, install-pi and doctor
pass. It contains only a diagnostic test; no product source change or PR.
The next step is to match the actual trigger with the attempt and component
timeline before proposing a recovery-policy change.

## Additional manual feedback

The user's local-dev screenshots show source22acf1b. They expose English
process prefaces joined to Chinese final text and excessive activity density.
The second UI source c6093de passes380App checks, TypeScript, independent
review and controlled browser checks, but is not deployed yet.

Backend re-review approves structural process/final-message separation,
scope checks and intent-preserving unsupported results. The broad final review
still rejects object/measure substitution and missing composite resolution
forwarding. Existing hosted tests also expose preparation-error and recognition
fixture regressions. These are still under correction; full test/e2e acceptance
is not complete. Full capability validation passes25scripted scenarios.

Registered model revision patches already expose element service-state changes;
the dedicated N-1 workflow covers branches. Missing generator N-1 workflow
coverage must not be described as the absence of every outage/calculation
primitive. Updatable domain guidance and strict execution/evidence contracts
serve different purposes. Unsupported typed coverage must not erase existing
published tool execution; compatibility must explicitly withhold coverage
certification and preserve existing admission.

## Receipts

Ignored receipts are in `runs/issue-processing-20261011/`: per-Issue intake,
workflow writes, publisher identity, exact CI/source checks and local warm
timing. GitHub remains the feedback ledger. The private receipts do not replace
Issue state or grant execution, merge, deployment or Provider authority.
