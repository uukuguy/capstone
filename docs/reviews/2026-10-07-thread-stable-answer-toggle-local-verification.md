# Stable Answer Toggle — Local Verification

## Scope

The user requests collapse and expand in the same position, minimal screen
movement and retained focus. This supersedes automatic top/bottom navigation
to the user instruction in [Web §5.3](../superpowers/specs/2026-10-01-capstone-thread-web-ui-main-contract.md#53-历史回答整理与单条折叠).

A completed long answer keeps one fixed-width button in both states. It sticks
lightly within the answer while reading. The same DOM control retains keyboard
focus, and scroll compensation preserves its viewport position. Individual
toggles no longer change the message window or force focus to the instruction.
Instruction references still identify the answer. Bulk actions preserve the
visible message and let the closing menu return focus to Settings.

Collapsing the final long reply can remove the scroll range needed for a stable
control. The view adds only the missing bottom reading space. A later toggle,
bulk action or Thread change clears or recalculates it. Full answer content,
copy, evidence, completed-message scope and draft behavior remain intact.

## Evidence

- Three revised focus/identity tests failed before implementation. They cover
  one persistent button, an instruction outside the message window and an
  unloaded instruction without navigation to another question.
- App suite: 24 files, 298 tests passed. TypeScript/Vite build, doctor and package
  boundaries passed. Existing bundle-size warning remains.
- Headless Playwright used the real Thread with 20 synthetic instruction/answer
  pairs and long Markdown. No Provider requests or business-data writes.
- Nine cases cover answer start/middle/end at 1200×900, 375×812 and 812×375.
  Control displacement after collapse is 0–0.4375px; expansion stays within 2px.
  Each case keeps the identical DOM button, keyboard focus and Composer draft.
- The final reply first moved 464.6875px when collapsed from its middle,
  despite retained focus. After the fix, the same case moves 0px; keyboard expansion
  also preserves position and clears the extra space.
- Bulk folding leaves focus on Settings. Desktop/mobile and boundary screenshots
  were inspected. Browser artifacts: `output/playwright/stable-toggle-20261007/`.
- Current-source local rebuild passed readiness, App reachability and shared
  API/worker image checks. Receipt: `/tmp/capstone-stable-toggle-rebuild.log`.
- Other local logs: `/tmp/capstone-stable-toggle-{tests,build,doctor}.log`.
- Document links, relative CLAUDE.md symlink and diff checks passed.

## Limits

Measurements cover the listed real-browser fixtures; arbitrary viewport sizes
and external layout changes can still limit exact positioning. Focus remains
on the same control. Earlier history/settings reports describe the superseded
top/bottom instruction-navigation interaction.

This is local verification and inline review. Independent review remains
pending because the platform reviewer model is unavailable. No remote release
or new tag is claimed. Unsupported zero-tool runtime remains a separate gap.
