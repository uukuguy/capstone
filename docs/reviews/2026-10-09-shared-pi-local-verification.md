# Shared general Pi local verification

Date: 2026-10-09. Source: `7f0f174`. Status: local engineering checks complete.

## Delivery contract

The approved [design](../superpowers/specs/2026-10-09-capstone-pi-delegation-design.md)
uses one native general Pi executor. Capstone delegates general goals to this
executor. The App's **Pi 通用** mode calls the same executor directly. Both
paths use bounded shared conversation history and the same native configuration.
Professional goals retain Domain Pack execution and Authority admission.

General observations do not become simulator results or evidence. Accepted
intent decisions, executor identity, entry point, and child task identity stay
fixed on retry. Saved child receipts prevent silent repeated execution.

## Completed checks

- Contracts, executor, storage, and relay: 70 focused tests pass. Checks cover
  deadlines, cancellation, bounded DNS and write work, concurrency, saved
  products, replay, retention, and invalid result admission.
- App: 358 tests pass. Retry uses the accepted entry point after a mode switch.
- Final committed backend: 900 Capstone tests pass with 49 optional skips.
  Full types, workbench types, and package boundaries pass.
- Isolated PostgreSQL: 29 checks pass. No existing database was used.
- Real pinned native Pi in Docker: the local loopback Provider invokes built-in
  bash through both hosted worker paths. Checks cover shared history, native
  tool inventory, saved product retrieval, absent business assets, protected
  host environment, and termination of detached tool descendants. The latest
  run also asserts public streamed text through the real HTTP adapter in both
  modes. The final rebuilt-image run passes in 7.36 seconds.
- Documentation links, the relative `CLAUDE.md` symlink, diff whitespace, and
  `make doctor` pass.
- Remaining functional and integration gates exit successfully. These include
  39 end-to-end tests, three registered worker tests, offline/scripted/application
  validation, and the capability matrix check.
- Final committed-source packaging and source-setup gates exit successfully,
  including the added business dependency contract.

The initial `make check-release` passed types, boundaries, 928 grid tests,
189 simulator tests, and 866 Capstone tests with 49 optional skips. It stopped
at one App test timeout. The independent App rerun passed all 358 tests. The
aggregate command did not exit successfully. The successful App rerun and
remaining gates are recorded separately above.

## Final fix verification

Commit `7f0f174` fixes admitted business dependency handoff, professional network
projection, service text-event adaptation, and encoded parent answer bounds.
It also removes exact duplicate projections and rejects conflicting contents.
Dependencies stay within the current Attempt, model, and selected capability
scope. Professional references are retained. Metadata that cannot fit fails
safely. Full professional answers are saved before visible shortening; full
general results remain in native receipts.

The committed patch passes 153 focused tests, with one optional PostgreSQL
skip, and changed-source types. Task 3 re-review and the
[whole-delivery review](2026-10-09-shared-pi-code-review.md) approve the patch.
The independent reviewer reran 23 regressions successfully. All local gates
needed for this scope are complete. Real Provider acceptance remains separate.

## Rebuilt local entry points

`make capstone-local-rebuild` exits successfully. API and both workers share
backend image `sha256:d8e9344b13148a37e684c44bfc25f45218384ab1e0cab6da9a7412912cc0e8cf`.
The API is ready at `http://127.0.0.1:8767`; App health passes at port 5173.
Both workers discover the same general executor identity and actual
bash/edit/read/write inventory. The retained local smoke Thread still reads
its saved Capstone mode after rebuild. These probes issue no Provider task.

Logs: `/tmp/capstone-delegation-accepted-capstone.log`,
`/tmp/capstone-delegation-app-retry.log`,
`/tmp/capstone-delegation-remaining-gates.log`,
`/tmp/capstone-delegation-final-packaging.log`,
`/tmp/capstone-delegation-final-rebuild.log`, and
`/tmp/capstone-general-pi-accepted-native.log`.

## Practical limits

All agent-run task checks use a local fake Provider. They prove the execution
path and isolation, not actual news, weather, model intent quality, external
source quality, latency, or cost. Real Provider behavior needs separate
authorized validation or user-operated App trials.

The relay supports API-key chat-completions transport. Anthropic and OAuth
configuration are rejected at startup. Native cost is unknown. Product bytes
are saved behind the private executor API; the App has no download control.
Storage has finite retention and replay tombstones. Full capacity requires
operator action. Skills/MCP installation management remains a later package.

No remote deployment, push, release tag, or billed Provider validation was
performed for this delivery. Existing user data and previous stage releases
remain outside these local checks.
