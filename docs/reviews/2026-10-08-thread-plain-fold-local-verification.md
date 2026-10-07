# Plain folded answers and visible instructions

Local verification only. No remote deployment or Provider requests.

The folded answer has a transparent background and one “展开” control.
The same control retains keyboard focus after both toggle directions. The
associated user instruction is brought fully into view when it fits the
viewport. An instruction taller than the viewport is aligned at its start.
Missing instructions do not select an unrelated question.

## Evidence

- App: 24 files, 298 tests passed; TypeScript and Vite build passed.
- Focused red run: two failures before the fix, then all tests passed.
- Current checkout rebuild: API ready; API and worker share digest
  `sha256:b65a956a24d0e3dfa8ef8624a5163d437e82dcf1b6fbfa4c9479573d2dfb7833`.
- Headless real-component fixtures: 1200×900, 375×812 and 812×375;
  long wrapped instructions, very long answers, start/middle/end positions,
  collapse and expand, draft retention and last-answer boundary.
- All nine position cases show the complete instruction after both actions;
  toggle focus is retained. Bringing hidden instructions into view moves the
  control by 50–137px in these fixtures. This is required context restoration,
  and supersedes the earlier strict stationary-control receipt.
- Folded background computes to transparent; “已折叠” is absent.

Browser artifacts: `output/playwright/plain-fold-20261008/`. Test/build/rebuild
logs: `/tmp/capstone-plain-fold-{tests,build,rebuild}.log`.
Doctor, package boundaries and `git diff --check` passed. Independent agent
review remains pending because its configured platform model is unavailable.
