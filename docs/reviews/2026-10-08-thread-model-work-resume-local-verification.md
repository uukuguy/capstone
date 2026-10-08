# Thread model work resume — local verification

Date: 2026-10-08. Scope: the approved [model work resume design](../superpowers/specs/2026-10-08-thread-model-work-resume-design.md).

## Result

The opened model collection, current model pointer, saved working Context and historical Context/Attempt views have separate roles. A -> B -> A restores A's saved Context instead of creating another model or resetting its work. Close then reopen creates a fresh Context. Closing a model retains its exact historical topology.

The next Attempt receives the latest instruction and bounded answer excerpt for its exact saved Context, plus the existing scoped prior-result candidates. Historical reader text is not current evidence. Calculation claims still require admitted Authority results. This does not restore a previous live Pi process or its private scratchpad.

The App derives model navigation from authoritative membership. Context history no longer creates model tabs. A restored analysis view names its original instruction result; a baseline names itself “基础拓扑”. Camera storage uses the exact model/revision/Context/source view and is bounded to the browser session. Switching models retains the composer draft.

## Automated checks

- Backend: `make test-capstone-agent`: 564 passed, 45 skipped.
- Isolated PostgreSQL workspace, persistence and Pi policy checks: 50 passed. They cover restart, saved Context/selection, exact-context instruction and result handoff, close/reopen, legacy migration and public projection bounds.
- App: 327 tests passed across 27 files; TypeScript and Vite build passed. Camera regression includes React Strict Mode remounting and same-view projection updates. Protocol regression accepts `model_resume` only for activation.
- `make test test-e2e validate doctor check-package-boundaries` passed. Grid-agent E2E: 39 passed; registered workers: 3 passed. Static-analysis coverage: 24/24. Final App checks above include the browser-discovered follow-up fixes.
- Inline review checked model/Context identity validation, public/private workspace separation, scoped prompt history, exact view source metadata and camera restoration. Independent review remains pending.

## Actual local entry point

The checked-in local rebuild verifies API and both workers share one image. Headless Playwright uses the actual Vite entry and a new owned Thread, without the user's Chrome or Provider requests.
The final backend image is `sha256:450ef89c62488bd72c97f8348532725a334cdd4411dc7ffcc86545f8b4a9221b`; the App is the current Vite source.

The real API exercises six controls: open B, activate A, close A, reopen A, activate B, activate A. It confirms saved Context equality, two members, a fresh Context after close/reopen and continued access to the closed model's original topology.

Browser acceptance covers desktop 1600x900, phone 375x812 and landscape 812x375. Each model appears once in the composer list; the obsolete Context-based model strip is absent. A -> B -> A restores the exact zoomed SVG viewBox. Same-tab refresh retains camera and draft. Menu bounds remain inside each viewport, and Escape returns focus to the model selector.
Four continuous model switches retain conversation `scrollTop=90` with a real scroll range of 1548px. The final zoomed viewBox is `180 108 640 384` before switching, after returning and after refresh.

Browser artifacts and API receipts are under ignored `output/playwright/model-work-resume-20261008/`. The test uses only its owned Thread. Actual Provider follow-up generation, independent review and cloud-dev/demo acceptance are not part of this local receipt. No cloud release tag is created.
The owned validation Thread was archived after acceptance; its cleanup receipt is retained. The isolated test PostgreSQL container and named headless browser were removed. Local application services and user data remain available.
