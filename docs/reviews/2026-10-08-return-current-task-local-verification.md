# Return to current task — local verification

The user approves restoring the current model's latest task topology and locating its accepted instruction together. Previously the topology crosshair only reset the camera.

The Thread now selects the latest accepted instruction for the active Context, with a scoped cached task fallback for bounded history. It restores the exact task view through the existing public history contract, resets the task camera, and requests location by Attempt identity. No current-model switch or analysis command is sent. A model without tasks uses “回到当前模型” and does not request a message location.

The message pane renders the target if it is outside its fifty-message window. It keeps already-visible instructions in place, scrolls only as needed for a hidden instruction, and adds a brief light outline. For narrow screens it also brings the instruction into the browser viewport. Automatic bottom scrolling is paused during the location update. Draft, focus and answer folding are preserved. Missing instruction history uses at most eight existing pages and reports unavailability rather than selecting a different message. Further model controls, view choices or command submissions cancel pending location work.

## Verification

- App330 passed across 27 files; TypeScript/Vite build passed. Tests cover an already-visible instruction, minimal scroll for an offscreen instruction, input focus/draft, retained folding, an unrelated Attempt, a target outside the render window, historical-to-current topology/result restoration, no command dispatch and the baseline-only label.
- Actual Vite conversation, read without sending commands, at 1600x900, 375x812 and 812x375. The latest instruction becomes fully visible and the answer remains collapsed. Repeated clicks retain the same conversation scrollTop: 5633, 6898 and 5608 respectively. Draft is unchanged. The full server snapshot is unchanged; zero POST/Provider requests.
- Background screenshots were inspected. Artifacts: ignored `output/playwright/return-current-task-20261008/`. The owned headless browser is closed after checks.
- Doctor, current-source local rebuild, document links, relative agent symlink and whitespace checks pass. API and workers share the rebuilt image and Vite serves the current App. Cloud acceptance and release tags remain separate.

The exact target is scoped to the current model Context. Historical viewing and ordinary model selection do not automatically trigger this message navigation.

## Reading position correction (2026-10-08)

The user's screenshot showed that the earlier full-visibility check allowed an instruction at the bottom, with its answer outside the viewport. That check was insufficient for task reading.

An offscreen instruction now lands 16px below the message viewport start. The pane adds only the missing end space when a short folded answer cannot provide enough scroll range. Mobile page scrolling uses the instruction start. Already-visible instructions stay in place, including repeated return clicks.

- App330 and TypeScript/Vite build pass. The focused test covers offscreen instructions above and below the viewport, visible instructions, draft, input focus and retained folding.
- Headless checks pass at 1600x900, 375x812 and 812x375 with both collapsed and expanded answers. Each target lands within 2px of the reading start; the answer begins in view. Repeated clicks retain scrollTop 6104, 7210 and 5950 respectively. The full server snapshot and draft remain unchanged; zero POST requests.
- Current-source local rebuild and doctor pass. API and both workers share image `sha256:f23412884f22bd0d5312a9b5a586cdf5879581d0df4d29e875640d6d8c682d3e`. The App remains the current Vite source. Screenshots and the six-case check are under the ignored artifact directory above.

## Viewed task ownership correction (2026-10-08)

The user clarified that the topology crosshair retains its original camera reset and adds location of the task belonging to the displayed graph. The earlier crosshair implementation incorrectly selected the current model's latest task when a different model's historical graph was open.

The graph toolbar now uses “回到任务”: it restores the displayed graph's task camera and locates that exact Attempt instruction. It does not replace the graph, activate a model or select a different task. A base graph uses “回到模型视角” and resets only the camera. The existing history bar keeps its separate “回到当前任务” action for leaving the historical graph. Both message paths share the bounded instruction loader and cancellation guard.

- App331 passes across 27 files; TypeScript/Vite build, doctor and whitespace checks pass. Same-model and cross-model tests pan and zoom an older task graph, reset its camera, check its original instruction highlight, retain graph values and current model, and assert no commands. The separate history-bar return remains covered.
- Actual old conversation at 1600x900, 375x812 and 812x375: case57 task graph resets from zoom and pan to viewBox `0 0 1000 600`; its original case57 instruction is fully visible at the reading start. Current model remains `ieee39 · pandapower`; displayed graph, draft and full server snapshot remain unchanged. Repeated clicks retain message scrollTop 271, 377 and 254. Zero POST requests.
- Current-source local rebuild passes. API and both workers share image `sha256:3323f05721c690ef706a4c1d6b796d730431fd623729417da10ad896e3dcbde2`. Headless artifacts: `viewed-task-check.js` and `viewed-case57-*.png` under the ignored directory above. No cloud deployment or Provider request.
