# Mission conversation: local verification

Owner: capstone-control with capstone-agent application adapters and capstone-app.
Destination: dev. Cloud and demo are outside this verification.

## Current boundary

The accepted main-conversation baseline is PR140/dev38a9e77f. Mission source941afaee
adds intent-only creation, progressive planning, registered equipment, durable
Task-boundary organizer reviews and criterion-backed delivery. Local acceptance
passed corrected real model acceptance locally. Scoped CI and actual-dev integration
remain separate until their final receipts are recorded.

## Focused checks

The Mission development gate passed91 Control,485 backend,200 scope and94 App checks,
plus TypeScript and Node/SDK checks.32 backend and3 scope cases retain their existing
platform or environment skips. Tests use a dedicated disposable PostgreSQL database,
not application data. The new SDK checks register actual tools with the pinned SDK;
their model runtime explicitly refuses model calls.

Cross-review found no source-grant or acceptance bypass. Safe conflict hints now
cover both revisions and exact saved-result references. Raw exceptions remain
excluded from model receipts. Model equipment preflight runs after exact operation
replay and before plan mutation; invalid equipment cannot strand a saved Task plan.

## Real failures retained as evidence

The first rough-intent trial asked for source clarification and created no Tasks.
It is not recorded as automatic delivery acceptance.

The next single-submission trial on347c1ee8/image4ee535cf proved initial one-Task
planning, two automatic organizer reviews and later addition of a second Task.
Its original file is36 bytes, SHA-256
`19b133e493ff2770ce3970512403b962fec570eef8a00d8afe9b577b060fd84e`.
The report was saved but explicitly said no source bytes were read. The application
had removed the required resource reader and had renamed the same source for the
child. The final model summary disclosed an unmet criterion and respected the
two-Task budget. An opaque conclusion nevertheless allowed delivered state.
This trial failed semantic acceptance; saved bytes alone did not complete the goal.

Corrections retain registered resource-read protocol helpers only for frozen inputs,
give immutable sources stable IDs while preserving destination grants and old frozen
identities, and require per-criterion verdicts with exact current saved evidence.
Unmet or unknown criteria now wait for user direction. Only all-met results may
deliver; final user acceptance remains a separate checked operation.

The next trial exposed a second admission gap: the model schema advertised resource
equipment that the adapter did not implement. Its Task plan was saved but could not
be readied. The model schema now publishes only implemented capability/profile kinds;
dependency inputs remain separate automatic grants. This trial is also retained as
a failure, not counted as acceptance.

## Corrected real acceptance

The exact same literal input, without changes or human phase advancement, completed
on941afaee/imageca3c0409. Thread `thr_3fb584f41c9959759e5a`, Mission
`goal_baf35e7432e9d5b59235fab854a512ff`:

- One user submission; one Task in the initial plan.
- Two real Task delegations and two typed automatic organizer reviews; no Task retry.
- The original file is36 bytes with the expected SHA-256 above.
- Source `resource_c5be855bcfe2b736c3290b523cb0f492` is identical across review and
  child grants. Actual resource-open and input-delivery receipts bind its saved bytes.
- The3644-byte report records real SHA-256, byte-count and binary-content checks.
  Report SHA-256: `2ffc9338202ba94b6efb65bf9368549ebeab4751bcef3278abd2898d17a9e7a5`.
- All three current criteria have typed met verdicts with admitted saved evidence.
  Mission revision25 is delivered; user acceptance is still null.

## Evidence and integration checks

Ignored operator evidence: `runs/mission-conversation-20261118/`, including
`progressive-browser-validation.json`, original/report downloads, frozen grants,
typed review events and screenshots. No Provider credentials are in these records.

Run scoped macOS CI and verify the real dev5173 entry after integration. Final
merge/source/image and browser receipts belong in the ignored closeout record;
the committed report is the acceptance snapshot, not a claim of cloud deployment.
