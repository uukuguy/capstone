# Retire the grid CLI and reduce iteration gates

Accepted scope: the user does not require `grid-agent` CLI compatibility.
`capstone-agent` is the supported application entry. This supersedes the earlier
compatibility requirement. Do not replace the old CLI with forwarding aliases.

## Current implementation

The old package is not only a CLI. `capstone_agent.registry` starts
`grid_agent.worker` and `grid_agent.case_preview`. The hosted application exports
its catalog through `grid_agent.thread_catalog_export`. The worker imports runtime
environment helpers from `grid_agent.cli.app`. Removing this package immediately
would break the formal application.

## Ordered work

1. Split local affected checks, PR checks and explicit baseline/release checks.
   Keep shared runtime, Authority and registered-worker tests. Remove dedicated
   old CLI and compatibility tests from the PR aggregate. Keep existing baseline
   PR #9 acceptance intact; do not change its tested source to make CI green.
2. Move application-owned pandapower worker, previews, model projections and
   assembly into a clearly named pandapower application package. Keep Domain Pack
   semantics out of `capstone-agent` and the Kernel. Move neutral runtime setup
   to its owning runtime module; remove worker imports from CLI files.
3. Switch registered application commands, deployment source manifests,
   installations, validation runners and package artifact checks to those owners.
   Preserve current-run evidence and API/worker identity.
4. Remove the `grid-agent` console script, old `run`/`analysis`/`report` entry
   contracts, CLI and compatibility implementations, and their dedicated tests.
   Keep tests for shared behavior by moving them with their owner. Update both
   READMEs, runbook, architecture and agent contract together.
5. Verify the real `capstone-agent` path, registered cases, reports, evidence
   replay and installed packages. Rebuild local-dev from the accepted source.
   Do not update local-demo or cloud stages with ordinary iteration changes.

Completion means the formal runtime neither launches nor imports `grid_agent`,
and the installed product has no `grid-agent` CLI. A changed gate alone is not
completion of the migration.

## Measured CI cause

Historical run 38074539207 took about 42 minutes. Linux grid tests took 880.38s,
simulator tests 292.26s, grid E2E 263.30s, registered workers 104.26s, artifact
installation about 179s. The workflow ran full release gates for both PR and
feature push events on Linux and macOS. These are suite totals, not evidence that
all grid tests belong to the obsolete CLI.
