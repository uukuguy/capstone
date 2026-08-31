# Capstone Brand Positioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Present Capstone Agent Framework as the reusable framework while preserving `grid-static-analysis` as its first pandapower application and retaining every existing compatibility surface.

**Architecture:** This is a documentation and reader-facing metadata migration. The bilingual READMEs become the primary product entry points; the capability-composition and application/runbook documents explain the same framework/application boundary in their respective contexts. No runtime code, package identifiers, CLI, protocol, environment variable, artifact path, or Git remote changes.

**Tech Stack:** Markdown, TOML metadata, Make documentation gates.

## Global Constraints

- Keep the local directory name `grid-static-analysis` unchanged.
- Keep all Python/npm distribution names, import paths, commands, environment variables, protocols, tool names, and run-artifact paths unchanged.
- Preserve the v1.0.1 two-field stdout envelope and simulator/evidence authority contracts.
- Do not state or imply that Capstone and Asterion are upstream/downstream, runtime dependencies, or one product family.
- Keep `README.md` and `README.zh-CN.md` aligned for shared product facts, headings, commands, and references.
- Do not select or implement C.2, promote the inventory fixture into a production application, or introduce multi-domain routing or governed writes.
- Do not modify the configured Git remote; GitHub repository renaming is operator-owned.

---

## File structure

| File | Responsibility |
| --- | --- |
| `README.md` | English Capstone entry point; identifies `grid-static-analysis` as the first pandapower application while retaining usage and compatibility facts. |
| `README.zh-CN.md` | Chinese equivalent of the English reader-facing positioning. |
| `pyproject.toml` | Keeps the `grid-static-analysis` distribution name and changes only its reader-facing description to identify Capstone. |
| `docs/architecture/pandapower-capability-composition.md` | Explains the reusable Capstone/Domain Pack composition boundary in the architecture reference. |
| `docs/PANDAPOWER-APPLICATION.md` | States that the formal pandapower workflow is Capstone's first application, without changing commands or evidence behavior. |
| `docs/RUNBOOK.md` | States the same application relationship where operator setup and command ownership are documented. |
| `docs/status/CURRENT-STATE.md` | Updates the structural project snapshot's project identity and theme-level focus; retains workstream status and avoids session narration. |

### Task 1: Establish the bilingual public identity and root metadata

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: approved positioning in `docs/superpowers/specs/2026-08-31-capstone-brand-positioning-design.md`.
- Produces: bilingual public language in which Capstone is the framework and `grid-static-analysis` is its first pandapower application; unchanged setup and CLI commands.

- [ ] **Step 1: Add the English product-positioning block before the existing grid application description**

  Change the top heading and opening copy in `README.md` to communicate this exact hierarchy:

  ```markdown
  # Capstone Agent Framework

  Capstone is a capability-first framework for assembling evidence-backed
  applications over authoritative business-domain systems.

  ## First application: Grid Static Analysis

  This repository's first Capstone application is `grid-static-analysis`:
  `grid-agent` performs evidence-backed static analysis of registered
  power-system networks.
  ```

  Retain the existing explanation that `gridctl` and pinned pandapower perform
  deterministic network calculations directly below this block. Do not rename
  `grid-agent`, `gridctl`, `grid-capability/1.0`, or any command shown later in
  the README.

- [ ] **Step 2: Add the matching Chinese positioning block**

  Make the opening of `README.zh-CN.md` express the same facts and hierarchy:

  ```markdown
  # Capstone Agent Framework

  Capstone 是一个能力优先的框架，用于在权威业务领域系统之上组装具备证据闭环的应用。

  ## 首个应用：电网静态分析

  本仓库中的首个 Capstone 应用是 `grid-static-analysis`：`grid-agent`
  用于对已登记电力系统网络执行具备证据闭环的静态分析。
  ```

  Preserve every existing Chinese command, compatibility explanation, and
  cross-link. Translate any new shared heading added to the English README so
  the two documents remain structurally aligned.

- [ ] **Step 3: Add a concise framework/application explanation beside Package Assembly in both READMEs**

  Immediately before the existing package table, add a paragraph that says
  Capstone supplies the reusable Kernel, Domain Pack, capability transport,
  current-run authority, and application-composition seams. State that the
  pandapower packages assemble the first formal application and that inventory
  remains a conformance/reference fixture, not a production second domain.

  Use this English source text in `README.md`:

  ```markdown
  Capstone's reusable seams assemble domain packages through the Kernel,
  capability transport, current-run authority, and application composition.
  The pandapower packages below form the first formal application;
  `inventory-domain-pack` remains conformance infrastructure, not a selected
  second production domain.
  ```

  Add the faithful Chinese equivalent in `README.zh-CN.md` before its matching
  table. Do not mention Asterion in either README; the public entry points need
  only the Capstone/application relationship.

- [ ] **Step 4: Change only the root distribution description**

  In `pyproject.toml`, retain `name = "grid-static-analysis"` and replace only
  the description with:

  ```toml
  description = "Capstone Agent Framework's first pandapower static-analysis application"
  ```

  Do not change the project name, version, scripts, dependencies, or package
  discovery fields.

- [ ] **Step 5: Verify public-name and compatibility consistency**

  Run:

  ```sh
  rg -n 'Capstone|grid-static-analysis|grid-agent|gridctl|grid-capability/1\.0' README.md README.zh-CN.md pyproject.toml
  git diff --check -- README.md README.zh-CN.md pyproject.toml
  ```

  Expected: both READMEs name Capstone and the first pandapower application;
  existing grid compatibility identifiers remain present; `git diff --check`
  prints no output.

- [ ] **Step 6: Commit the public identity change**

  ```sh
  git add README.md README.zh-CN.md pyproject.toml
  git commit -m "docs: position Capstone as the framework"
  ```

### Task 2: Align architecture, operator documentation, and structural state

**Files:**
- Modify: `docs/architecture/pandapower-capability-composition.md`
- Modify: `docs/PANDAPOWER-APPLICATION.md`
- Modify: `docs/RUNBOOK.md`
- Modify: `docs/status/CURRENT-STATE.md`
- Modify: `docs/status/JOURNAL.md`

**Interfaces:**
- Consumes: the public terminology committed by Task 1 and the product boundary from `docs/superpowers/specs/2026-08-31-capstone-brand-positioning-design.md`.
- Produces: architecture and operation references that identify the same Capstone/pandapower relationship without altering command or authority contracts; a structural state snapshot consistent with that identity.

- [ ] **Step 1: Add a current-positioning note to the capability-composition architecture**

  Near the document introduction in
  `docs/architecture/pandapower-capability-composition.md`, add this bounded
  note:

  ```markdown
  ## Product position

  This document describes the first Capstone application:
  `grid-static-analysis` for pandapower static analysis. Capstone reuses the
  Domain Pack and application-composition seams for future authoritative
  business domains; this does not change the existing grid compatibility
  contract or select a second production domain.
  ```

  Leave existing protocol names, `gridctl` authority statements, and
  model-capability restrictions intact.

- [ ] **Step 2: Identify the formal pandapower workflow as the first application**

  In `docs/PANDAPOWER-APPLICATION.md`, insert a concise introduction before the
  first command section:

  ```markdown
  This is Capstone's first formal application. It assembles the pandapower
  Domain Pack through the existing `grid-agent` compatibility product; all
  commands, output envelopes, and current-run evidence rules below remain the
  versioned grid contract.
  ```

  Do not change a command, make target, result path, report path, or provider
  instruction in the document.

- [ ] **Step 3: Add the same boundary to the runbook overview**

  In `docs/RUNBOOK.md`, add a short overview sentence near the repository setup
  introduction:

  ```markdown
  Capstone's current shipped application is `grid-static-analysis` for
  pandapower static analysis. This runbook documents that application and its
  established grid compatibility and evidence contracts.
  ```

  Keep the existing fresh-worktree sequence (`make setup`, `make install-pi`,
  `make doctor`) and all credential restrictions unchanged.

- [ ] **Step 4: Refresh only structural facts in CURRENT-STATE**

  Change the `Project Snapshot` facts in `docs/status/CURRENT-STATE.md` to:

  ```markdown
  - Project: Capstone Agent Framework
  - Theme-level focus: capability-first framework for authoritative business-domain applications
  ```

  Keep the local directory name, direct project route, current C.2 scope,
  workstream status, and architecture bullets. Do not add a “completed
  recently” or “next steps” section and do not alter the handoff baton.

- [ ] **Step 5: Verify documentation and state boundaries**

  Run:

  ```sh
  rg -n 'Capstone|Asterion|first formal application|首个 Capstone 应用|Project: Capstone' \
    README.md README.zh-CN.md docs/architecture/pandapower-capability-composition.md \
    docs/PANDAPOWER-APPLICATION.md docs/RUNBOOK.md docs/status/CURRENT-STATE.md
  git diff --check
  make doctor
  ```

  Expected: Capstone consistently names the framework; no document claims an
  Asterion runtime or dependency relationship; `make doctor` exits zero; and
  `git diff --check` prints no output.

- [ ] **Step 6: Commit the architecture and operations alignment**

  ```sh
  git add docs/architecture/pandapower-capability-composition.md \
    docs/PANDAPOWER-APPLICATION.md docs/RUNBOOK.md \
    docs/status/CURRENT-STATE.md
  git commit -m "docs: align Capstone application positioning"
  ```

- [ ] **Step 7: Journal the architectural naming decision after the documentation commit**

  Append, never edit, one line under the current date in
  `docs/status/JOURNAL.md` after the Task 2 commit. Obtain the values with:

  ```sh
  date '+%H:%M'
  git log -1 --format='%h'
  ```

  Insert the two command results into this fixed journal sentence:

  ```markdown
  - 对齐 Capstone 框架与 pandapower 首应用文档，保留所有 grid 兼容契约
  ```

  The time appears immediately after `- ` and the commit hash appears in
  square brackets at the end, following the repository's append-only journal
  format. Leave the append uncommitted until the next task-owned commit.

### Task 3: Perform the documentation integrity pass

**Files:**
- Verify: `README.md`
- Verify: `README.zh-CN.md`
- Verify: `pyproject.toml`
- Verify: `docs/architecture/pandapower-capability-composition.md`
- Verify: `docs/PANDAPOWER-APPLICATION.md`
- Verify: `docs/RUNBOOK.md`
- Verify: `docs/status/CURRENT-STATE.md`

**Interfaces:**
- Consumes: completed Tasks 1 and 2.
- Produces: evidence that the positioning migration did not alter supported runtime contracts or leave bilingual/documentation drift.

- [ ] **Step 1: Check the preserved identifiers and prohibited technical renames**

  Run:

  ```sh
  rg -n 'name = "grid-static-analysis"|grid-agent|gridctl|grid-capability/1\.0|runs/' \
    pyproject.toml README.md README.zh-CN.md \
    docs/architecture/pandapower-capability-composition.md \
    docs/PANDAPOWER-APPLICATION.md docs/RUNBOOK.md \
    docs/status/CURRENT-STATE.md
  ```

  Expected: the original distribution name and all required compatibility
  identifiers remain documented. Investigate any missing required identifier
  before proceeding; do not substitute a Capstone-prefixed protocol or command.

- [ ] **Step 2: Run the documentation and repository health gates**

  Run:

  ```sh
  make doctor
  git diff --check
  git status --short
  ```

  Expected: `make doctor` exits zero, `git diff --check` prints no output, and
  `git status --short` contains only intended documentation/state changes (or
  is clean after the Task 2 commit).

- [ ] **Step 3: Leave the tree clean after verification**

  If verification reveals a documentation defect, return to the task owning
  that document, correct it, and repeat that task's verification command. Do
  not create an empty verification commit.
