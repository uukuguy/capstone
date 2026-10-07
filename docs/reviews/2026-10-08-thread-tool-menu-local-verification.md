# Registered Tools and History Menu — Local Verification

The user's screenshot exposed two missed requirements: PyPSA was hidden by
family filtering, and history actions still had redundant heading and hint rows.
The correction follows [Web §5.4](../superpowers/specs/2026-10-01-capstone-thread-web-ui-main-contract.md#54-对话设置的用途).

Settings now shows every registered catalog tool group. A pandapower model
shows both pandapower and PyPSA; the incompatible PyPSA checkbox is disabled
with “需 PyPSA 模型” on the same row. Future registered groups use the same
catalog path. Compatible selection retains exact Profile references and the
existing command contract. This does not enable cross-family execution.

History controls show only “折叠历史回答” and “展开历史回答”. The “历史回答”
heading and scope explanation are removed. Their loaded-history-only behavior,
new-answer full display, stable answer toggle and focus behavior are unchanged.

## Evidence

- Two revised interaction tests failed before implementation for the hidden
  tool and redundant history rows.
- Full App suite: 24 files, 298 tests passed. TypeScript/Vite build passed with
  the existing bundle-size warning. Doctor and package boundaries passed.
- Current-source rebuild passed readiness, App reachability and shared
  API/worker image identity: `sha256:d3c9b3e501f19400410fbd12aa2b8ed761ae9076933a4adca7bdbcd175f231f4`.
- Headless Playwright checks real App components with an isolated catalog
  fixture. Both tools are visible, incompatible selection is disabled and
  described, and neither redundant history row is present.
- Save appears only for changes. Unsupported all-off submission is blocked;
  unsaved choices are discarded on close. Escape returns focus and drafts
  survive. Compatible multi-group selection is covered by App tests.
- Desktop, 375px mobile and 812×375 landscape screenshots were inspected.
  Popovers stay in view; the mobile tool-row target is 44px and menu height is
  about 217px. Artifacts: `output/playwright/tool-menu-20261008/`.
- Logs: `/tmp/capstone-tool-menu-{tests,build,rebuild,doctor}.log`.
- Links, relative CLAUDE.md symlink and diff checks passed.

No Provider requests, cross-family conversion, remote deployment or new tag.
Zero-tool runtime and independent review remain pending. Prior menu receipts
describe the earlier filtered list; this report owns the visible registered list.
