# Compact Grid Settings — Local Verification

## Scope

The user's screenshot showed that the rejected nested Settings design still
existed. The previous completion statement overstated the delivered scope.
This change applies [Web §5.4](../superpowers/specs/2026-10-01-capstone-thread-web-ui-main-contract.md#54-对话设置的用途).

Settings now shows history actions and compatible grid-analysis tool groups
directly. The Advanced and professional-configuration layers, long explanation,
bordered option cards and permanent large apply button are removed. Known
registered groups use `pandapower 静态分析` and `PyPSA 电网分析`; future groups
retain their registered display names. Only family-compatible groups appear.

Save appears only when selection changes. It sends exact Profile references
through the existing replace-selection command. Closing Settings discards
unsaved choices. Pending model switches prevent tool changes.

## Evidence

- Four revised tests failed on the previous source for nested controls, old
  names and scope copy. The fixture for the all-off check explicitly carries
  its initially enabled tool selection.
- Full App suite: 24 files, 298 tests passed. TypeScript/Vite build passed with
  the existing bundle-size warning. Doctor and package boundaries passed.
- Current-source local rebuild passed readiness, App reachability and shared
  API/worker identity: `sha256:d3c9b3e501f19400410fbd12aa2b8ed761ae9076933a4adca7bdbcd175f231f4`.
- Headless Playwright checks the real App with an isolated registered fixture.
  Settings has no nested details, and unchanged selection has no Save button.
- Empty selection cannot submit and shows a reason. Escape restores trigger
  focus; reopening restores the saved selection. Composer draft remains.
- At 375px, the normal popover is about 220px high and within the viewport.
  Tool-row touch target is 44px. The 812×375 landscape panel stays in bounds.
  Desktop, mobile and landscape screenshots were inspected.
- Browser scripts, receipt and images: `output/playwright/compact-settings-20261007/`.
- Command logs: `/tmp/capstone-compact-settings-{tests,build,doctor,rebuild}.log`.
- Document links, relative CLAUDE.md symlink and diff checks passed.

## Limits

This fixes the compact interface. The runtime does not yet support all tools
disabled; Web now blocks that unsupported submission with a short reason.
Model access without analysis tools remains a tracked implementation gap.
No unified grid-model system, cross-family conversion, Provider call or remote
deployment is included. Independent review remains pending because the
platform reviewer model is unavailable.
