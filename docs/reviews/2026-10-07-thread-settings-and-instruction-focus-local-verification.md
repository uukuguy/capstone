# Thread Settings and Instruction Focus — Local Verification

## Scope

The user requested subtle folded-message states, top/bottom answer controls,
instruction-based reading focus, and useful settings. The owning contract is
[Web §5.3–5.4](../superpowers/specs/2026-10-01-capstone-thread-web-ui-main-contract.md#53-历史回答整理与单条折叠).

Folded answers have a faint surface, fine status line, chevron and “已折叠” label.
Full answers have top and bottom close controls. Each answer uses its accepted
Attempt/Turn instruction reference, rather than a nearby guessed question, for
scroll and keyboard focus. Loaded instructions outside the current message
window are made visible. A missing instruction falls back to the answer itself.
Automatic bottom following pauses while the reading layout settles.

History actions share the existing Settings entry. Fixed routing information
and the duplicate global trace control are removed; per-answer runtime actions
remain. Profile selection stays behind Advanced as “专业功能配置”, with an
explanation and no internal IDs/versions. Unchanged selection cannot submit.
Its backend dispatch, family compatibility and availability guards are intact.

## Evidence

- Before implementation, 10 revised interaction tests failed on the old source.
- The missing-instruction focus regression also failed before its fix.
- Full App suite: 23 files, 293 tests passed after the final focus fixes.
- TypeScript/Vite build, doctor, package boundaries and diff checks passed.
- The local rebuild receipt is `/tmp/capstone-settings-focus-rebuild.log`.
- Headless Playwright checked the real App Settings and real Thread/Controls
  components with isolated synthetic instruction/answer pairs. No Provider
  requests or business-data writes occurred.
- Browser checks passed top close, bottom close, expand and bulk history
  actions. The correct instruction retained keyboard focus and remained about
  12px below the viewport top on desktop and mobile.
- New answers remain full. Folded copy retains the full answer. Drafts survive.
- 375px mobile targets are 44px with no horizontal overflow. Reduced motion
  and 812×375 landscape checks passed. The Settings popover remains within
  visible bounds and scrolls when vertical space is limited.
- Script, receipt and inspected desktop/mobile images:
  `output/playwright/settings-focus-20261007/` (ignored).

## Limits

This is local verification and inline review, not independent review approval.
Independent reviewer dispatch failed on unavailable platform default model
`gpt-6.1-luna`. No cloud deployment, promotion or new acceptance tag occurred.
The earlier history-folding report records the preceding implementation; this
report owns the refined Settings and instruction-focus behavior.
