# Thread History Folding — Local Verification

## Approved behavior

The user approved the revised [Web contract §5.3](../superpowers/specs/2026-10-01-capstone-thread-web-ui-main-contract.md#53-历史回答整理与单条折叠).
History folding is a one-time action over loaded, completed answer IDs. New
answers stay full. Each completed long answer has a bidirectional toggle.
Short, running and unsuccessful answers stay visible. The history action menu
is in the Composer footer. Copy uses the full committed answer.

The former global selector, stored reading preference and task-owned backend
summary projection were removed. Backend Harness source and tests match HEAD.
No runtime, Authority, admission, or API contract changed.

## Local evidence

- Test-first regression: the previous implementation failed six revised tests.
- Full App suite: 23 files, 290 tests passed after the scroll fix.
- TypeScript and Vite production build passed. The existing bundle-size warning remains.
- `make doctor`, package boundary checks and `git diff --check` passed.
- Local Compose rebuild passed readiness and API/worker image identity checks.
  The rebuild receipt is `/tmp/capstone-history-fold-rebuild.log`.
- Headless Playwright used the real Thread component with isolated synthetic
  events. No Provider request or business-data write occurred.
  Script, receipt and desktop/mobile screenshots are in the ignored directory
  `output/playwright/history-fold-20261007/`.

Browser checks passed default full display, footer placement, history-only
folding, pending-to-completed and later full answers, repeated individual
toggles, full clipboard content, retained drafts, refresh reset, Escape focus,
hidden-link inertness, and mobile 44px targets without horizontal overflow.
Bulk folding kept a visible answer's top within 0.5px. Folding from inside a
long answer kept that answer's header at the viewport top.
App tests also cover loaded answers outside the 50-message window, preservation
of individual overrides when returning to latest messages, and Thread reset.

## Review and release limits

This document records local verification and an inline source review. It is
not an independent review approval. Reviewer dispatch failed because the
platform selected unavailable model `gpt-6.1-luna`.

No cloud-dev or demo deployment was performed for this change. No acceptance
tag was created. Existing deployed versions and their tags remain the baseline.
Remote release requires its own gates, stage verification and acceptance tag.
