# Service-bus execution-record closeout

This is the bounded follow-up to the accepted
[tool lifecycle design](../specs/2026-11-08-tool-execution-lifecycle-design.md).
The user requires service-bus totals in the execution-process title bar and
per-tool details, then deployment to local-dev and dky3-dev. The existing PPT
template-library candidate is included. No other deployment is selected.

## Contract and implementation

- The gateway MCP adapter reads only `structuredContent.provenance.service_bus_calls`
  with `scope=current_tool_call`. It ignores `data.service_bus_calls` job totals.
- The host issues the bounded projection in its immutable observation receipt.
  Public tool-end events use this projection only after receipt verification,
  including business-error returns and child tools. No Kernel or second ledger.
- Preserve the total attempt count independently of the last ten detail rows.
  Missing or invalid counters remain unknown. Bridge attempts, received responses
  and declared errors are distinct. Summed source durations are not wall time or
  database execution time. No SQL, filters, credentials or business rows are copied.
- Existing event persistence restores the same statistics after refresh. UI
  aggregation deduplicates tool IDs and excludes host-marked historical reuse.
  Reuse existing title metadata and expandable tool-detail components.
- Live catalog preparation confirms 14 business and 5 platform tools on 三区研发.
  Use the current published descriptions, schemas and continuation responses.
  Do not add fixed service selection or business-name routing. Only change
  execution guidance if a bounded real trial proves a contract violation.

## Acceptance sequence

1. Focused adapter/relay/host and UI parser, graph, title-bar and replay checks.
2. Commit the verified unit. Canonical local rebuild of the exact candidate.
3. Bounded real gateway trial: match source counters to persisted events and
   visible title/detail totals; reload and check reuse and zero/unknown cases.
4. Check PPT template operations on the same source. Existing detailed PPT
   receipts remain valid where relevant contracts are unchanged.
5. Deploy the exact tested source to dky3-dev, preserve data, configuration,
   prior images and backups; verify role identity, App, real task and reload.
6. Update canonical report/register/graph and branch copies. Prepare a joint
   focused macOS PR gate. CI requires separate explicit approval before a PR
   update or other action that starts it. No release-sized or Linux gate.

Independent review and browser availability must be reported truthfully. A
failed or incomplete remote trial receives no deployment acceptance tag.
