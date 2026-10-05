# Thread client recovery design

Approved scope: the user accepted client recovery work on 2026-10-05 and requires
cloud-dev verification plus manual acceptance before any cloud demo deployment.

## Ownership and approach

Keep recovery in the App presentation and projection store. Reuse the existing
idempotent command contract and typed Context-bound topology history. The Kernel,
Authorities, compatibility stdout, evidence admission and historical Attempts
retain their owning contracts.

Keeping only the draft would still permit duplicate Turns after a lost receipt.
A new offline queue would add persistence and ordering policy that this repair
does not need. Use the existing pending command ledger instead: reconnect with
the exact command ID, idempotency key, payload, Run and original cursor.

## Send recovery

- Keep the mounted Composer and its draft during same-Thread reconnects.
- An unresolved command blocks a new command until its exact receipt is checked.
- A user-requested reconnect checks unresolved commands under their original
  identity. Accepted receipts clear only a matching submitted draft. Rejected
  receipts keep the draft and show the existing actionable rejection.
- Do not replay acknowledged commands or issue a new command identity when the
  previous outcome is unknown. A failed event refresh after an accepted receipt
  does not turn the accepted command into an unsent instruction.
- New draft text remains intact. Changing Threads resets projection state.

## Model rollback

First run the existing live/reload rollback regressions. Extend them to a failed
reopened Context that emits its own diagram and layer. The restored view must
match the previous Context, model revision, diagram and admitted layer; the failed
Context must not overwrite it. Fix only a reproduced gap. History remains read-only.

## Acceptance and release

Run failing client regressions, App tests/build, relevant backend contract checks,
offline integration gates and the current-source local rebuild. Use fresh isolated
Threads for browser acceptance; preserve user sessions and var/ data.

Deploy the fixed source only to capstone-cloud-dev. Verify readiness, both model
families, registered scripted cases, reports, evidence replay, browser recovery
and API/worker source identity. Provider calls require separate explicit approval.
Record the failed concurrent PyPSA case and diagnose with scripted sessions if the
failure can be reproduced. Do not claim concurrency recovery from serial success.

Present the verified revision, test receipts, cloud-dev URL and remaining limits
for manual acceptance. Do not deploy capstone-demo before that acceptance.
