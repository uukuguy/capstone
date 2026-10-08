# Instruction model label — local verification

User-requested change: show the model short name beside the accepted instruction time. The label uses the instruction's exact Context, not the current model at rendering time. Retained activation documents recover historical bindings. No prefix, full display name or extra background block is added.

- App: 328 tests passed; TypeScript and Vite build passed. Regression verifies IEEE-39 remains attached to its instruction after switching to case57 and removing the old model from the supplied current contexts.
- Actual local Vite entry: read-only checks of an existing conversation at 1600x900, 375x812 and 812x375 show three case57 instructions and the later IEEE-39 instruction with correct labels and times. All visible instructions have labels; metadata fits each viewport. Background browser recorded zero POST requests. Screenshots were visually checked.
- `make capstone-local-rebuild` passed; API and both workers use image `sha256:3323f05721c690ef706a4c1d6b796d730431fd623729417da10ad896e3dcbde2`. `make doctor`, document links, relative agent symlink and whitespace checks passed.
- Artifacts: ignored `output/playwright/instruction-model-20261008/`. No Provider request or cloud deployment. No release tag.

An old instruction without a retained, verifiable model association does not receive a guessed current-model label. That limitation does not affect the existing conversation checked above.
