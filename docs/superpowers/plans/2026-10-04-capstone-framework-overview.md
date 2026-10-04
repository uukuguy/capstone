# Capstone Framework Overview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a single browser-openable HTML page that explains Capstone to product and business decision makers through interactive architecture, runtime, capability, and deployment views.

**Architecture:** Keep all content, inline SVG diagrams, Tailwind CDN configuration, custom CSS, and JavaScript in `docs/capstone-framework-overview.html`. Use small data arrays in the script as the single source for slider panels, timeline steps, maturity cards, and deployment stages; DOM update functions render those arrays into fixed semantic sections. No backend calls, build tooling, or project runtime dependencies are required.

**Tech Stack:** HTML5, Tailwind CSS browser CDN, inline SVG, vanilla JavaScript, CSS media queries.

## Global Constraints

- Keep the artifact self-contained in one HTML file and require no build step.
- Target product and business decision makers; lead with value and trust, then progressively disclose technical detail.
- Preserve the ownership direction `Application -> Domain Pack -> Kernel -> registered Authority`.
- Do not present M10 topology work, cloud federated deployment, or Provider validation as complete.
- Use dark navy, slate, white, emerald, and amber visual tokens with visible focus states and readable contrast.
- Respect `prefers-reduced-motion` and keep every interaction keyboard accessible.
- Do not use emoji as interface icons; use inline SVG symbols.
- Verify with direct browser opening, `git diff --check`, and a focused DOM/interaction smoke test.

---

### Task 1: Create the page shell and executive narrative

**Files:**
- Create: `docs/capstone-framework-overview.html`

**Interfaces:**
- Produces semantic sections with stable IDs: `hero`, `architecture`, `runtime`, `trust`, `maturity`, `deployment`, `workflow`, `local-use`, and `boundaries`.
- Exposes `window.capstoneOverview` only for the optional browser smoke check; the page itself has no external application API.

- [ ] **Step 1: Write the HTML document shell**

Add the document type, responsive viewport, title, Tailwind CDN script, inline Tailwind config, font fallback, and body landmarks. Define CSS variables and reusable classes for cards, focus rings, badges, and small labels. Keep all text in the document so the file works when opened directly.

- [ ] **Step 2: Add the executive content**

Write the hero statement, three outcome cards, a compact status strip, and the fixed section headings. State that Capstone lets an agent organize analysis while the registered authority owns facts and calculations. Include the current implementation line: M6–M9 complete for recorded scope; M10 scoped and pending.

- [ ] **Step 3: Add inline SVG icon symbols and navigation**

Define a hidden SVG symbol sprite with neutral line icons, then use `<svg><use href="#icon-..."></use></svg>` in navigation and cards. Add skip link, `aria-label` values, and anchor navigation for all major sections.

- [ ] **Step 4: Verify the static shell**

Run:

```bash
git diff --check -- docs/capstone-framework-overview.html
```

Expected: no output and exit code 0.

### Task 2: Add architecture, trust, and runtime interactions

**Files:**
- Modify: `docs/capstone-framework-overview.html`

**Interfaces:**
- `window.capstoneOverview.renderLayer(index)` updates the architecture explorer.
- `window.capstoneOverview.renderRunStep(index)` updates the runtime timeline.
- `window.capstoneOverview.playRun()` and `.pauseRun()` control the timeline animation.

- [ ] **Step 1: Add the architecture explorer markup**

Create a range input with `min="0"` and `max="3"`, an output label, four layer cards, and a detail panel with fields for owner, responsibility, returned value, and boundary. Give the slider a visible label and `aria-valuetext` updates.

- [ ] **Step 2: Add the architecture data and renderer**

Define four objects with these exact layer names and facts:

```js
const layers = [
  { name: 'Application', role: '选择应用、公共 UI/CLI、Provider 配置和读者呈现', output: '答案、报告和兼容投影', boundary: '不拥有领域语义、原始 Authority 对象或模型可见凭据' },
  { name: 'Domain Pack', role: '定义工具、合同、策略、指南、执行器和结果准入', output: '领域状态与已验证结果引用', boundary: '不拥有 Kernel 内部或其他 Domain Pack 的状态' },
  { name: 'Kernel', role: '管理中立编排、上下文、Turn、轨迹、工件、回放和审计', output: 'framework core 生命周期与可重放事件', boundary: '不解释 pandapower/PyPSA 语义或重算领域事实' },
  { name: 'Registered Authority', role: '访问登记模型，执行确定性计算或来源检索', output: '结果、修订版本和证据', boundary: '不负责模型规划、应用展示或无界调用' }
];
```

Render the selected item, update `aria-valuetext`, and animate only opacity/transform when motion is allowed.

- [ ] **Step 3: Add the run timeline**

Create seven steps: request, published tool, authority calculation, admission, evidence binding, answer, report. Show a progress rail, current-step copy, play/pause/restart buttons, and a live region. The model may organize and write text; it cannot create numerical claims or evidence references.

- [ ] **Step 4: Add trust callouts**

Add three cards for “authority owns facts”, “current-run evidence only”, and “failure boundaries”. Explain that offline informational answers create no simulator evidence, while authority-backed claims require admitted references from the current run.

### Task 3: Add maturity, deployment, workflow, and usage views

**Files:**
- Modify: `docs/capstone-framework-overview.html`

**Interfaces:**
- `window.capstoneOverview.renderStage(index)` updates the deployment stage panel.
- `window.capstoneOverview.toggleMaturity(id)` expands a capability card.

- [ ] **Step 1: Add capability maturity cards**

Render M6, M7, M8, M9, and M10 cards from a data array. Mark M6–M9 as complete for recorded scope and M10 as “下一阶段 / 待实现”. Include one sentence per milestone and a “why it matters” line. Expand details on click and keyboard activation.

- [ ] **Step 2: Add the deployment stage slider**

Create a second range input with three stages: local Compose, cloud development, and user trial. Render stage-specific components, data separation, verification gate, and promotion rule. State that cloud development and user trial never share databases, buckets, credentials, origins, or mutable run data.

- [ ] **Step 3: Add operator workflow**

Show the sequence “选择登记案例 → 查看完整模型图 → 逐步或自动执行 → 查看结果图层 → 读取报告和证据”. Add a small explanation that the browser receives bounded API projections, not bucket credentials or raw artifacts.

- [ ] **Step 4: Add local usage and boundaries**

Show the safe local commands `cp deploy/local.env.example deploy/local.env`, `make capstone-local-rebuild`, and the App/API URLs. Use a disclosure for operational details. Add boundary notes for Provider credentials, public demo cases, Railway single-family deployment, and the pending M10 topology provider.

### Task 4: Wire accessibility, motion preferences, and verification hooks

**Files:**
- Modify: `docs/capstone-framework-overview.html`

**Interfaces:**
- All controls use buttons, range inputs, or semantic disclosure elements.
- `window.capstoneOverview.state` exposes selected layer, selected stage, current run step, and playing state for smoke verification.

- [ ] **Step 1: Implement the interaction controller**

Use event listeners for `input`, `click`, `keydown`, and `change`. Keep the active card and selected step synchronized. Use `setInterval` only while the run timeline is playing and clear it on completion, pause, hidden tab, or reduced-motion mode.

- [ ] **Step 2: Add reduced-motion handling**

Read `window.matchMedia('(prefers-reduced-motion: reduce)')`. In reduced-motion mode, skip stagger/reveal transitions, keep the timeline static until explicitly advanced, and preserve all information in text and state labels.

- [ ] **Step 3: Run static and browser checks**

Run:

```bash
git diff --check -- docs/capstone-framework-overview.html
python3 - <<'PY'
from pathlib import Path
p = Path('docs/capstone-framework-overview.html')
s = p.read_text()
for marker in ('tailwindcss.com', 'Application', 'Domain Pack', 'Registered Authority', 'make capstone-local-rebuild', 'prefers-reduced-motion'):
    assert marker in s, marker
print('content smoke: PASS')
PY
```

Open the file directly in a browser and verify the two sliders, timeline play/pause/restart, maturity disclosures, and local usage disclosure with mouse and keyboard.

- [ ] **Step 4: Commit the artifact**

```bash
git add docs/capstone-framework-overview.html
git commit -m "docs: add interactive Capstone framework overview"
```
