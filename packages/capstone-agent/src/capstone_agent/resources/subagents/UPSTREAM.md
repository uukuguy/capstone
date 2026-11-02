# Managed Pi subagent execution subset

This directory vendors an adapted execution subset of `@tintinweb/pi-subagents`
**0.19.0**, under its MIT license. It does not load the full extension.

- Repository: https://github.com/tintinweb/pi-subagents
- npm source commit: `4f572eaa04c09d3dbc16e4a5f13a16b295e84e14`
- Source: https://github.com/tintinweb/pi-subagents/blob/4f572eaa04c09d3dbc16e4a5f13a16b295e84e14/src/agent-runner.ts
- Tarball: https://registry.npmjs.org/@tintinweb/pi-subagents/-/pi-subagents-0.19.0.tgz
- Verified npm integrity: `sha512-DZsU33Urfb9dhEsJmsmpx0dayIHMYUbxng6AA7B6+bIgspNcTckcSnQRsbrv+QCS7jVKYJTzHIT/j1SU2B/nVQ==`
- Original `src/agent-runner.ts` SHA256: `88e61481fd627254ff3ac0a27e1991136c41e103fac847dd06444c8ac3d3eab1`
- Original `dist/agent-runner.js` SHA256: `7cd0408c22207b574c67fc08d8013e4d628483429857ae062e19755e72493b1d`
- Original `dist/context.js` SHA256: `b7756963913d42d5c6f53ceb6d5d22712ba45c2fd226955fa6d8695a49171740`

The upstream package declares Pi peers `>=0.84.0`; its development pins are
0.84.2. This seam is tested with the application's pinned Pi 0.84.4. Upstream
HEAD `ca93a5247e72e7053fcd10bea7125d6c4205f949` is version 0.22.0 and needs Pi
`>=1.1.0`. It is not the source used here.

## Retained upstream behavior

`managed-runner.mjs` retains the upstream response collector, current-invocation
history fallback, final stop-reason failure classification, turn-limit steering
and abort, tool/text/usage/compaction callbacks, and `runAgent` prompt execution.
The source regions in npm `dist/agent-runner.js` are lines 339–403 and 816–913;
`extractText` comes from `dist/context.js` lines 5–10. Formatting differs.

## Required local patch

The stock `runAgent` has no session-factory injection. It constructs a fresh
disk-backed SettingsManager, resource loader, tool set and session. Its
`onSessionCreated` hook runs after resource discovery and binding; it cannot
replace that construction boundary. This adapter instead accepts the host's
already bound AgentSession. The host supplies the fixed ModelRuntime, guarded
tools, selected resources and private settings. It supplies `close` to shut down
extensions and dispose the session. The adapter owns prompt/abort/close lifetime.

Local changes also check cancellation before allocation and before prompting
(upstream 0.19 misses pre-aborted signals), await abort/close, retain tool call
IDs/error state, report missing usage/pricing as null, and return turns and the
actual per-message usage without exposing the live session. There is no implicit
history copy, structured-output retry, disk discovery, memory tool, worktree,
agent configuration lookup, model choice or nested delegation in this subset.

This is not the upstream AgentManager, fleet/workflow system or a new scheduler.
The application retains parent identity, concurrency, cancellation, receipt
admission and durable Thread state. Children remain inside the existing private
native task sandbox. A child session adds no OS boundary or Authority grants.

## Host interface

`createManagedSubagents({createChildSession,maxTurns?,graceTurns?})` returns
`run({prompt,signal?,onToolActivity?,onTextDelta?,onAssistantUsage?,onTurnEnd?,onCompaction?,onResult?})`.
The factory receives `{signal}` and returns `{session,close}`; it must clean up
partial construction if it throws. Each run gets a fresh session. `onResult`
runs after successful cleanup; a thrown factory/prompt/cleanup error rejects.
An SDK final assistant error remains a result with `failure` and any partial
text, as upstream does. The host must sanitize failures before public output.

No public tool or deployment wiring is enabled merely by importing this module.
The application must select and bound the delegated task explicitly. Do not
claim upstream workflow, resume, schema-output or nested-agent support.
