# System notices and global history anchors

Local acceptance for the user's 07:32 screenshot feedback. No remote deployment
or Provider requests. This does not close the entire conversation worklist.

System notices now use an inset neutral row, a small label and icon, and a thin
horizontal separator. They have no answer-like left rail or full green surface.
Errors use restrained amber text and a small label. Status/alert roles and
recovery actions remain intact; the mobile recovery target is at least 44px.

Global history actions retain a visible user instruction as the reading subject,
rather than the preceding long answer. Consecutive actions reuse its screen
position. Deliberate scrolling selects a new subject. Repeating an action when
its answer states are already set does not change the view. The browser's actual
landing position is retained after scroll-boundary rounding. Closing the menu
returns keyboard focus to Settings and preserves the draft.

When only the middle of a long answer is visible, folding hides that text. The
first action restores that answer's own instruction; later actions hold its
position. A loaded instruction outside the 50-message window is revealed.
This is context restoration, not a promise to keep hidden text in view. Individual
toggles retain their existing complete-instruction visibility and button focus.

## Evidence

- Two red runs reproduce preceding-answer anchoring and unwanted no-op
  navigation. The focused regression then passes, including intentional scrolling.
- App: 25 files, 307 tests passed. TypeScript and Vite build passed.
- Headless real-component fixtures: 1200×900, 375×812 and 812×375.
  The original instruction displacement reached 2,201px.
- 72 repeated or consecutive main actions at start/middle/end retain the
  instruction within 0.391px; Settings focus and drafts survive.
- 30 edge actions cover deliberate scrolling, hidden instructions and the last
  reply. After restoring the instruction, subsequent displacement is at most
  0.438px. Individual mouse/Enter toggles retain focus and complete instructions.
- 72 animation-frame samples from 12 last-reply actions move at most 0.391px,
  including the first painted frame after each action.
- Eight desktop/mobile window-boundary actions reveal the exact loaded
  instruction, retain Settings focus and show 0px subsequent displacement.
- Normal/error notice screenshots and computed styles confirm transparent
  surfaces, no left border, distinct horizontal separators and preserved roles.
- Final current-checkout rebuild passes readiness and App checks. API and worker
  use the same digest:
  `sha256:3d27bee8750e0a9ec1ea2ae17255ac4a5b714d33b3237b07263243818c036931`.
- Doctor, package boundaries, changed document links, the relative `CLAUDE.md`
  symlink and `git diff --check` pass.

Artifacts: `output/playwright/bulk-stability-20261008/`, including scripts,
before/after receipts, edge/window/frame receipts and screenshots. Logs:
`/tmp/capstone-bulk-{tests,focused,build,doctor,rebuild}.log`.

Source review was performed inline. Independent review and cloud acceptance
remain pending. No backend behavior, answer/evidence contract, tool preference
semantics or model conversion was changed. The separate zero-tool runtime and
configuration persistence gaps remain on the owning worklist.
