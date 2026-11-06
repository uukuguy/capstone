# Thinking model capability correction

Source: `3a8eaf7601db03bc690835233bf32cc4b825d549`.
Recovery: `refs/capstone/fixes/thinking-capability-20261105`.
Parent: `bfb16344242658ffeeaf8ee8c1f5dcfdcf7bd82c`.

## Cause and change

The latest two63 dsv4 sessions saved no Thinking events. Recognition generated
a model entry without reasoning capability. Native execution set that capability
to false. The SDK therefore did not request the existing thinking effort.
A bounded direct18804 comparison returned no reasoning with effort omitted,
and113 reasoning characters with effort low. This identifies a model request
configuration fault in addition to the earlier display transport faults.

The admitted dsv4 profile now declares reasoning capability. Recognition and
native execution pass it to their private model configuration. Profile identity
checks, exact boolean validation and private workspace ownership checks prevent
the capability from changing unrelated providers or shared configuration.
The existing low/medium effort policy and preview/database buffer sizes remain.

## Verification

470 focused checks passed,38 skipped in42.59s. These include actual managed SDK
low/medium/off requests, both reasoning SSE forms, profile identity and private
configuration ownership. No CI was started.

On63, the original question was submitted without an explicit model override.
Attempt `attempt_afa1dde6c77bb62d` completed with dsv4. It supplied76 preview
batches and12 durable Thinking events. All preview IDs have durable acknowledgments.
The browser recorded visible text growth during execution. First preview preceded
the first durable event by1.3011s. Refresh and expansion restored976 characters.
Screenshot: `output/playwright/thinking-63-running.png` (ignored runtime evidence).

Local attempt `attempt_382ae46607642c66` used dsv4 explicitly, executed Python,
and completed with answer63. Browser observation confirmed live recognition and
native Thinking. Seven durable events include four native events. Refresh restored
two visible Thinking blocks of225 and364 characters. The bounded SSE probe timed
out at240s; the task later completed at267.421s. Its completion and persistence
were checked from the event API. The probe timeout is not reported as a pass.

Raw receipts are under `.capstone-agent/thinking-missing-20261105/`.
They contain stage identity, focused checks, browser observation lengths and events.

## Limits and remaining work

This accepts Thinking display and restoration. It does not accept performance:
the local simple computation was abnormally slow. No repeated benchmark calls
were started. The63 answer listed registered models rather than gateway tools;
that semantic routing fault remains separate and is not accepted as correct.
Old completed sessions without reasoning cannot acquire historical Thinking.

Both intranet defaults remain dsv4 on18804. The local default is unchanged.
Each stage keeps its own gateway, credentials and ledger. Exact deployed image
identities and stage acceptance are recorded in `../status/VERSION-CONTROL.md`.
