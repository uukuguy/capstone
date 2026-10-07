# Thread System Notices — Local Verification

## Scope

The user approved moving conversation errors and operation outcomes into the
message area. The owning contract is [Web §7](../superpowers/specs/2026-10-01-capstone-thread-web-ui-main-contract.md#7-状态层级).

Command rejection and uncertain submission now show quiet system rows with
related instructions and recovery actions. Rejected drafts remain in the
Composer. Connection interruption and recovery update one row. Failed,
cancelled and interrupted Attempts keep partial answer text and render their
terminal explanation once. Model and tool-selection outcomes use existing
public events. Local model-view feedback stays beside the model.

The presentation adapter does not add commands, model prompts, answer artifacts
or evidence. Normal accepted conversational receipts remain hidden. Existing
retry, diagnostics, evidence and model compatibility contracts are preserved.

## Evidence

- Revised tests first failed for inline notice placement, resync recovery and
  terminal-error deduplication. A later diagnostic-only cursor test failed
  before its fix; recovery must remain available beyond the last public event.
- Full App suite: 23 files, 296 tests passed. TypeScript/Vite build passed.
- Doctor, package boundaries, document links, relative CLAUDE.md symlink and
  diff checks passed. Existing bundle-size warning remains.
- Current-source local rebuild passed readiness, App reachability and shared
  API/worker image identity: `sha256:b65a956a24d0e3dfa8ef8624a5163d437e82dcf1b6fbfa4c9479573d2dfb7833`.
- Headless Playwright used real App/Thread components with an isolated rejected
  transport and 20 synthetic instruction/answer pairs. No Provider requests or
  business-data writes occurred.
- Rejection appears once in the message area, preserves the draft and creates
  no accepted user message. Removed top banners do not appear.
- A notice added while reading history moved the instruction by 0px and kept
  keyboard focus. Recovery replaced the same row and preserved the draft.
- 375px mobile has no horizontal overflow; the recovery button is 44px high.
  Keyboard Enter activates recovery. Desktop/mobile screenshots were inspected.
- Ignored browser scripts, receipts and images:
  `output/playwright/system-notices-20261007/`.
- Local command logs: `/tmp/capstone-system-notices-{tests,build,doctor,rebuild}.log`.

## Limits

Local notices are bounded to 100 entries in the mounted Thread workspace.
They do not provide reload or cross-device persistence. Existing durable
model/selection events remain replayable. Older history pages exclude later
local outcomes. The initial load-error shell remains when no workspace exists.

This records local verification and inline review. Independent reviewer
dispatch failed because platform default model `gpt-6.1-luna` is unavailable.
No independent approval, cloud deployment, promotion or new tag is claimed.
