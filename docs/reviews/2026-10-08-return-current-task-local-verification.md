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
