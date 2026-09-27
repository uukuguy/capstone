# CAPSTONE Workbench Desktop Readability Implementation Plan

> **For agentic workers:** Work inline in this checkout. Preserve unrelated staged and untracked files. Each step uses the local App and focused checks; do not run a billed provider validation or a cloud analysis.

**Goal:** Restore readable desktop text and controls while keeping the approved visual layout, then keep the header and sidebars visible during long-page reading.

**Architecture:** Only `packages/capstone-app/src/styles-light.css` changes application behavior. Existing React state, network data, report data, and generated hero image remain untouched. CSS breakpoints govern desktop, tablet, and phone separately.

**Tech Stack:** React, Vite, CSS, Playwright CLI.

## Global Constraints

- Keep the original hero artwork and all copy unchanged.
- Preserve the three-column centered desktop composition and equal sidebars.
- Phone widths up to 680 px retain the current vertical layout and page scrolling.
- Do not introduce horizontal page overflow at 375, 768, 1280, or 1920 px.
- Use the local `http://127.0.0.1:5173/` App for browser acceptance.

---

### Task 1: Replace page zoom with real desktop dimensions

**Files:** Modify `packages/capstone-app/src/styles-light.css`.

**Interfaces:** CSS classes already emitted by `App.tsx`; no component or API contract changes.

- [ ] Capture and retain baseline screenshots and dimensions at 375, 768, 1280, and 1920 px in `output/playwright/`.
- [ ] Replace `.app-shell { zoom: .67; }` with `zoom: 1`, set a 1280 px centered shell, 205 px equal desktop sidebars, a 740 px hero cap, and an approximately 760 px content measure. Add scoped font-size and padding overrides to keep hierarchy balanced without shrinking the page as a whole. Initial layout rules:

```css
.app-shell { zoom: 1; }
.topbar, .workspace { max-width: 1280px; }
.workspace { grid-template-columns: 205px minmax(0, 1fr) 205px; }
.run-panel { max-width: 820px; }
.intro-breadcrumb, .capstone-intro { max-width: 740px; }
```

- [ ] At widths through 1020 px, use a two-column grid with a 190 px catalog and place running details below the center. At widths through 680 px, preserve the current one-column rules.
- [ ] Check actual `getBoundingClientRect()` button heights and text appearance, plus before/after screenshots. Adjust only scoped dimensions that visibly break the approved proportions.

### Task 2: Keep desktop context visible during scrolling

**Files:** Modify `packages/capstone-app/src/styles-light.css`.

**Interfaces:** The existing header and sidebars; no JavaScript scroll handler.

- [ ] Add a sticky header and sticky sidebars under it. Use a single 58 px header height for desktop top offset; cap sidebars to the remaining viewport and allow their content to scroll. Initial rules:

```css
.topbar { min-height: 58px; position: sticky; top: 0; }
.catalog-panel, .detail-panel {
  position: sticky;
  top: 58px;
  height: calc(100vh - 58px);
  overflow-y: auto;
  align-self: start;
}
```

- [ ] At the two-column breakpoint, reset the detail panel to normal flow. At the phone breakpoint, reset both sidebars and the header to normal page flow.
- [ ] Scroll the local page to its bottom at 1280 px and verify header, catalog heading, and detail heading remain visible, while the action bar remains reachable. Check sidebar scrolling with short and long content.

### Task 3: Focused acceptance and delivery

**Files:** Modified CSS and this plan; no additional application files unless the browser reveals a concrete issue.

- [ ] Capture final local screenshots at 375, 768, 1280, and 1920 px; compare with the saved baseline for hero content, equal sidebars, topology frame, and action order.
- [ ] Run `npm --prefix packages/capstone-app run build`, the App's focused tests, `make doctor`, and `git diff --check`. Do not run the repository's full test suite for this CSS-only change.
- [ ] Record any remaining report/topology findings from the visual review without changing those features in this pass. Commit only task-owned paths; keep `.codex/config.toml`, the existing journal edit, and `output/` untouched.
