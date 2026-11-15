# Worker loss: lease fencing and retained-file recovery

Status: baseline defect reproduced; candidatef0976baf passed focused checks,
canonical rebuild, a new real worker-loss recovery and Vivaldi refresh.
Not merged; no CI approval. Overall worker-loss acceptance remains partial.
Owner capstone-agent. Branch fix/worker-interruption-products-20261115 targets dev.
Base: actual devfffc881e; baseline local runtime source5798dad6.

## Real baseline and scope

Thread `thr_1f5fe57105d8c6667941`, attempt `attempt_1759f3983b73d252`.
The model saved draft.md and entered a separate60-second tool operation. A
read-only ledger guard checked that this was the only active Thread task before
SIGKILL of capstone-worker-native-1. The container was restarted immediately;
no other worker, authority, database or storage was stopped.

An API-container monitor held the original lease only in RAM. It observed the
attempt transition to interrupted/lease_expired, then verified rejection of
renewal, runtime-event insertion and successful completion under that old claim.
No lease token was printed or saved. The isolated native executor nevertheless
completed its task and produced private final.md/draft.md. The late final file
was not admitted to Thread products. When checked it was already terminal, so
no further native model work remained to cancel.

The public draft remained source_statusrunning. A real follow-up instruction
explicitly requested original bytes and forbade reconstruction from chat; it
reported that it could not read the historical draft. The report itself is not
proof of source absence: the ledger's running descriptor and the deterministic
history selection filters establish the missing admission.

## Root cause and bounded repair

Normal finish_attempt seals open captures through the existing
incomplete_capture_seals helper. Expired-lease reaping did not call that helper.
Separately, _process_files admitted only completed/failed/cancelled attempt
phases. Thus even an explicitly interrupted attempt with a valid incomplete
receipt could not supply the next instruction's historical input.

Candidatef0976baf reuses the same sealing helper inside the existing memory
critical section/PostgreSQL transaction, before publishing attempt_interrupted.
It adds interrupted to the finished-attempt selection in both stores. Original
capture events and bytes remain immutable. Normal finishing still uses the same
helper. No late native result is imported, no unavailable bytes are reconstructed
and no Authority evidence is created. This preserves the previously accepted
file-restoration contract rather than creating automatic task resumption.

## Focused evidence

Four memory/PostgreSQL cases first failed for the two distinct causes above.
They now verify expiry and explicit interruption, unchanged bytes/digest,
incomplete sealing before the terminal event, stale-write rejection, idempotent
reaping, a distinct new attempt, exact frozen historical reference and actual
protected reading of the saved bytes. PostgreSQL also verifies rollback of
sealing when terminal event insertion fails.

Python3.12 direct-consumer checks:115 passed; focused worker-interruption gate
including its scope check:116 passed in21.96s. After strengthening exact read
assertions, the four new cases passed again. Scope classifier checks:123 passed
in3.58s. An existing Starlette deprecation warning remains. No frontend source,
Kernel, Authority or Dockerfile change. No CI has run for this candidate.

Ignored receipts: runs/harness-worker-loss-validation-20261115/, including
start/follow-up commands, loss.json, before/after/settled snapshots, native status,
fence-result.json and the operator-only monitor script. Initial missing-psycopg
probe used the wrong container interpreter; the owning capstone-agent venv fixed
setup without a product change.

## Fresh candidate verification

Root temporarily applies the exact three package/test paths fromf0976baf on
basefffc881e; `source-identity.json` records their verified hashes. Canonical
`make capstone-local-rebuild` passed. API/three workers share image
`sha256:8952043d0e6a2268237c93c3a8a2f1c78ecfb0059bcda1bc6866c948e4bf9987`.
Readiness and scoped cache cleanup modeapply passed. No Dockerfile layer added.

Fresh Thread `thr_20784dcce6ac2fe4156a`, interrupted attempt
`attempt_5c7c2a5eb2f62c10`. After a sole-active-task guard, only the native worker
was killed/restarted. Original lease renewal, event insertion and completion
were rejected. Public file events now order running capture, identical
incomplete seal, then attempt_interrupted. File bytes and artifact ID did not
change. The independent native task was stillrunning after interruption;
the operator explicitly cancelled only this test task. The receipt records
manual_operator_cleanup=true. This cleanup is not an automatic product fix.

Distinct follow-up attempt `attempt_38138f9991b21f68` read the admitted historical
draft through the protected resource tool. Its host delivery receipt binds the
original incomplete source. Downloaded draft.md is28bytes, SHA256
`84b1d27e8b614ee4ddb67697d4345252320d4e7ce7ffce14e18b5a3e5d5596b6`.
The recovery-check.md report is1588bytes, SHA256
`000140e31ca0680001aaf1d4424ae3dd5e3dd0b5fef86c1ebd92291d4b7bbf70`;
independent checks found the exact original digest and interrupted-state note.
No final.md entered Thread products. The old attempt remained interrupted;
only the new instruction completed.

The existing Vivaldi tab previewed the original draft as“结束时未完成”. Reload
preserved that preview, the interrupted attempt and completed recovery report.
No extra tab or replacement conversation UI was introduced. Fixed receipts:
`runs/harness-worker-loss-fixed-20261115/`, including source/runtime identities,
fence-result.json, native-operator-cleanup.json, all-events.json,
download-verification.json and browser-refreshed.json. Test PostgreSQL stopped.

## Outstanding acceptance

Existing already-interrupted records are not retroactively rewritten;
the original failed probe remains a recovery reference. A bounded historical
repair policy is separate work if those old records need automated repair.

The independent native executor's continuation after parent-worker loss is a
verified, separate lifecycle gap. This candidate does not fix it. A safe stop
protocol must distinguish worker death from temporary transport loss, preserve
ownership and avoid cancelling valid work. Worker-loss acceptance remains
partial until that protocol is designed and verified. Do not report this file
repair or stale-ledger fencing as proof that the whole execution chain stopped.
