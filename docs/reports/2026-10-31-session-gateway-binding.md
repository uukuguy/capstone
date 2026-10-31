# One gateway instance per conversation

Implemented source: `d3c69284e52e55fa1beb88d3d0b993261a52525d`.
Accepted design: [session gateway binding](../superpowers/specs/2026-10-31-session-gateway-binding.md).

The Thread ledger stores its selected connection, instance ID, public display
identity and lock. First accepted instruction admission locks that identity in
the same transaction. Empty conversations can select another registered source.
Rejected instructions leave them unlocked. The backend rejects attempts to
change a locked conversation, even when the App is bypassed.

The sidebar reads the current conversation's instance and permission. It never
uses the workspace default as the current conversation's identity. Inspection of
other instances remains available; the switch button is disabled after locking.
Model displays, resource metadata, execution and receipt validation use the same
source. Each execution retains its accepted catalog revision. Same-instance
contract refresh remains available. No business tool or provider name was added
to the execution policy.

Focused verification:

- Backend source/admission/HTTP checks: 213 passed, 34 skipped in 7.84 seconds.
  The skipped cases require Linux root profile execution.
- App checks: 34 passed in 2.27 seconds; TypeScript checks passed.
- Real PostgreSQL checks cover restart recovery and concurrent selection versus
  first instruction. They used a new isolated schema and removed only that schema.
- The final runtime configuration regression checks passed with 28 tests and
  3 skips in 0.32 seconds. Executor identity and non-source capability drift
  remain rejected.

Real browser validation reused the existing Vivaldi tab:

1. Original conversation `thr_5bd702a75df2e3de832e` remained bound to local
   integration instance `3db5bb96-2c27-4d97-8584-346bc4a18656`. The switch button
   was disabled. Direct selection returned HTTP 409 `gateway_session_locked`.
2. Existing empty test conversation `thr_57a1254e28950cdd0877` in
   `空间-b239d9bf` could select the development instance
   `9afa2e62-3914-47a9-aa71-c6e13be743d9`. The default and original conversation
   did not change.
3. Its real CSV task completed in 50.8 seconds, with 17 model responses and
   34 tool records. Attempt `attempt_f9537dca11df2156` retained connection
   `development` and catalog revision
   `00e0a0bc98f8714fbfffdca978998e76e5fe20b039c93d1c0ce80c2aeb73cc1e`.
4. Downloaded final CSV contains 5 rows. SHA-256:
   `2a27e4a7735dcfbb51b5d5bc8be5ba74d5708ee1ca57eaeb76d81f8907adee3f`.
   One model-generated nested scope argument failed local schema validation;
   the composed parent reported the same error. The model corrected it. This
   result does not claim zero tool errors or performance acceptance.
5. After completion, the B conversation also prohibited switching. Returning
   to the original conversation restored the A instance in the sidebar.

Two integration failures were retained and fixed before completion: display-only
address metadata entered the protected native binding, and a legacy runtime
check compared the bound source against the global default. The first failed
before transaction commit. The second produced a 299 ms preparation failure,
`attempt_4d9ffa6bf1774e44`, before model or tool execution. Neither issued a
business query. Their records were preserved; successful execution used a new
instruction after the fixes.

Final canonical rebuild passed. API and all three workers use image
`507734c3db946f25b4e187c3c05a8e73704693e2fb2cc715659034a40e363dc7`.
Log: `/tmp/capstone-session-gateway-runtime-rebuild.log`. Scoped cache cleanup
receipt: `.capstone-agent/cache-maintenance-20261031-150516-65148.log`.
Evidence: `runs/session-gateway-binding-20261031/`.

No CI, push, PR, cloud deployment or release was started.
