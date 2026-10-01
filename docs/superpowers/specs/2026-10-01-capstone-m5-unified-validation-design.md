# Capstone M5 Unified Validation Design

**Status:** Approved for implementation on 2026-10-01.

## Goal

Prove that the Capstone Thread contract works across the real registered pandapower and PyPSA application assemblies, Web and Textual clients, ordinary and professional turns, controls, evidence admission, and recovery states.

## Boundary

M5 is an acceptance and integration milestone with only the smallest fixes required to preserve the approved contracts. It does not add multi-run Threads, new UI features, new Domain Packs, or provider credentials.

`capstone-agent` remains the application-level Thread/Harness contract. Each registered Authority/Domain Pack assembly remains behind its application adapter. Because pandapower and PyPSA have incompatible pinned environments, M5 validates them through separate real application processes using the same `/api/v1` and `CapstoneThreadClient` protocol. It must not fake a composite process by importing both simulator environments into one Python runtime.

## Acceptance matrix

| Area | Real path | Required evidence |
|---|---|---|
| Pandapower | new local Thread with `pandapower-scripted-task` instructions | model catalog, tool provenance, answer duration, admitted result/evidence, public event replay |
| PyPSA | new local Thread with a registered PyPSA business model and the same protocol client | PyPSA model/Profile catalog, authority-backed answer, model page projection, no pandapower-only assumptions |
| Ordinary conversation | automatic route for an informational question | answer is returned without simulator result/evidence artifacts |
| Professional analysis | automatic/professional route for潮流 or registered business analysis | route event plus current-run admission; missing admission remains fatal |
| Controls | model/Profile selection while idle and while an Attempt runs | pending event, next-Turn activation, exact command receipt |
| Attempt lifecycle | cancel, terminal failure/interruption, retry | new Attempt identity, old events unchanged, bounded duration/activity |
| Recovery | SSE transient reconnect and cursor gap | reconnect preserves projection; gap freezes commands and requires verified resync |
| Clients | Web and Textual TUI over typed Thread projection | equivalent snapshot/event/receipt state, no direct runtime imports |

## Test architecture

1. A provider-free acceptance runner creates unique Threads through the authenticated local API or an injected real application assembly.
2. The runner stores only bounded JSON summaries and references under ignored `runs/`/`output/` paths. It never stores operator/provider secrets.
3. Web checks use `CapstoneThreadClient` and the existing projection store. Browser checks cover the visible control states only after protocol assertions pass.
4. TUI checks construct `ThreadTuiApp` from verified `ThreadSnapshot` and `EventPage`, submit through the same typed command factory, and compare public state with the Web projection.
5. Every failure class is asserted by protocol event and receipt, not by text-only UI appearance.
6. A cross-family model switch is not claimed unless a real application process exposes both compatible bindings. Separate pandapower and PyPSA Threads are sufficient for M5; any missing composite host is recorded as an explicit successor item rather than simulated.

## Failure policy

- A missing snapshot/event/cursor, unadmitted professional answer, stale model context, or evidence persistence error fails the acceptance run.
- Provider availability is not a prerequisite; provider-backed checks remain opt-in and are not part of the default M5 gate.
- Recovery never continues from a partial projection. A verified cursor gap requires snapshot replacement and contiguous catch-up before commands are enabled.
- Test cleanup removes only M5-owned Thread IDs and ignored artifacts.

## Deliverables

- Reproducible M5 acceptance runner and focused protocol tests.
- Web/TUI parity assertions and browser/TUI evidence summaries.
- Versioned M5 verification report with exact commands, counts, image/process identities, and known gaps.
- Updated recovery baton pointing to the next architectural milestone.
