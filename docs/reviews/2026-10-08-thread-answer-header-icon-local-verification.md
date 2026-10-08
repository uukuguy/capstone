# Answer icon beside CAPSTONE

Local acceptance only. No remote deployment or Provider requests.

The answer's persistent collapse/expand button is now an icon beside CAPSTONE,
with native hover hints and accessible action names. It shares the label row;
there is no separate button row. The first Markdown block has no extra top
margin. The label and icon remain lightly sticky while reading a long answer.
The same button retains focus after both directions, and the corresponding
instruction remains completely visible when it fits the viewport.

## Evidence

- Updated persistent-control test fails before the change, then passes.
  App: 25 files, 307 tests passed; final TypeScript/Vite build passed.
- Headless real-component checks: 1200×900, 375×812 and 812×375.
  Role/icon alignment, native hints, one label, sticky visibility and keyboard
  activation pass. The icon sits 10px from the label's edge in all three sizes.
- The shared header is 18px on desktop and 28px on mobile, with a 5px body gap
  and 6px first-block inset. Mobile retains a 44×44px interaction target around
  the small glyph. The completed answer has no separate toggle row.
- Nine long/wrapped-instruction cases at start/middle/end pass both directions;
  button focus, drafts and last-reply context remain intact.
- 72 global header-anchor actions move the instruction at most 0.391px.
  Twelve additional actions after the final first-block spacing correction
  move it at most 0.375px, with the complete instruction retained.
- Doctor, package boundaries, changed document links, the relative CLAUDE.md
  symlink and `git diff --check` pass.
- Final local rebuild passes readiness and App health; API and worker use
  `sha256:7a5480e83cfb1c787552d8e4c5da8ee0c89343a5edad01879712d74feff69040`.

Artifacts: `output/playwright/header-icon-20261008/`. Logs:
`/tmp/capstone-header-icon-{tests,build,doctor,rebuild}.log`.
Independent review and cloud acceptance remain pending. System notices retain
the small text and pale neutral background from the preceding user correction.
