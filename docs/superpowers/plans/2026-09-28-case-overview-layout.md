# Case Overview Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make right-column case facts readable by keeping short values in two columns and moving long values to a key row followed by a value row.

**Architecture:** Keep the existing semantic `dl` structure and add a content-derived `is-long` class to each fact. CSS controls the two layouts, field separators, and key/value hierarchy in both dark and light themes; no case-specific selectors are introduced.

**Tech Stack:** React/TypeScript, CSS, Vitest Testing Library.

## Global Constraints

- Short values such as model and step count stay key/value on one row.
- Long descriptive values use key on one row and value on the next.
- key and value keep the same base font size; key uses color, weight, and letter spacing for distinction.
- Every fact has a bottom separator, including the final fact.
- The rule applies to all catalog cases and responsive widths.

---

### Task 1: Add content-derived fact layout classes

**Files:**
- Modify: `packages/capstone-app/src/App.tsx`
- Test: `packages/capstone-app/src/App.test.tsx`

**Interfaces:**
- Add `isLongCaseFact(value: string): boolean` with a shared threshold for descriptive values.
- Render each fact as `<div className={...}><dt>...</dt><dd>...</dd></div>` while preserving semantic `dl` markup.

- [ ] **Step 1: Add failing UI tests** asserting `IEEE-39` and `3 步` facts are short, while scenario and boundary text receive `is-long`.
- [ ] **Step 2: Run** `npm test --prefix packages/capstone-app -- --run src/App.test.tsx` and verify failure.
- [ ] **Step 3: Implement** the helper and class assignment without changing catalog data or text.
- [ ] **Step 4: Run the focused UI tests** and require them to pass.
- [ ] **Step 5: Commit** with `git add packages/capstone-app/src/App.tsx packages/capstone-app/src/App.test.tsx && git commit -m "feat: classify long case overview facts"`.

### Task 2: Style short/long facts and field separators

**Files:**
- Modify: `packages/capstone-app/src/styles.css`
- Modify: `packages/capstone-app/src/styles-light.css`
- Test: `packages/capstone-app/src/App.test.tsx`

- [ ] **Step 1: Add visual assertions** for `.case-overview-fact.is-long` and the final fact separator in the rendered DOM.
- [ ] **Step 2: Run** `npm test --prefix packages/capstone-app -- --run src/App.test.tsx` and verify the style contract test fails.
- [ ] **Step 3: Implement**:
  - default facts as a two-column grid;
  - `.is-long` as one column with `dt` above `dd`;
  - `border-bottom` on every fact and no missing final line;
  - equal base font sizes, with key color/weight/letter spacing;
  - matching dark/light theme colors.
- [ ] **Step 4: Run** `npm test --prefix packages/capstone-app -- --run` and `npm run build --prefix packages/capstone-app`.
- [ ] **Step 5: Commit** with `git add packages/capstone-app/src/styles.css packages/capstone-app/src/styles-light.css packages/capstone-app/src/App.test.tsx && git commit -m "style: improve case overview fact hierarchy"`.

### Task 3: Responsive visual verification

**Files:**
- Verify: `packages/capstone-app/src/App.tsx`
- Verify: `packages/capstone-app/src/styles.css`
- Verify: `packages/capstone-app/src/styles-light.css`

- [ ] **Step 1: Start or reuse local Vite service on port 5173** and open a PyPSA and pandapower case at desktop and narrow viewport widths.
- [ ] **Step 2: Confirm** short fields remain compact, long fields do not create narrow value columns, and the last separator is visible.
- [ ] **Step 3: Run** `git diff --check` and record the visual verification result.

