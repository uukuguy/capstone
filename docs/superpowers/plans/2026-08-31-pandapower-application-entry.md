# Pandapower Application Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `make application` as the formal Provider-backed pandapower application entry while preserving v1.0.1 compatibility commands and one authoritative operator reference.

**Architecture:** `application` supplies target-specific defaults for the registered pandapower application and canonical task file, then inherits the existing `analysis-generic` recipe. A focused Bash test checks the dry-run command shape without calling a Provider.

**Tech Stack:** GNU Make, Bash, existing `grid-agent analysis-generic` CLI, Markdown.

## Global Constraints

- `make application` may call a billable Provider; credentials remain in environment variables or ignored authentication state.
- `make analysis` and `make report` retain their v1.0.1 two-field stdout envelope.
- Formal application stdout remains `capability-agent-output/1.0` with `core` and `domains.grid`.
- Detailed formal-application instructions live only in `docs/PANDAPOWER-APPLICATION.md`.

---

### Task 1: Add the Makefile target and dry-run contract test

**Files:**

- Create: `tools/test_makefile_application.sh`
- Modify: `Makefile`

**Interfaces:**

- Consumes: `analysis-generic`, which requires `APPLICATION` and `INSTRUCTIONS` and accepts `PROVIDER` and `MODEL`.
- Produces: `application`, inheriting `APPLICATION=pandapower-static-analysis` and `INSTRUCTIONS=validation/questions/task.md.txt`.
- Produces: `test-makefile-application`.

- [ ] **Step 1: Write the failing test**

Create `tools/test_makefile_application.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

test_root=$(git rev-parse --show-toplevel)
default_output=$(make -C "$test_root" --no-print-directory -n application)
override_output=$(make -C "$test_root" --no-print-directory -n application APPLICATION=custom-domain INSTRUCTIONS=custom-questions.txt PROVIDER=deepseek MODEL=deepseek-v4-flash)

grep -Fq 'grid-agent analysis-generic --application "pandapower-static-analysis" --instructions "validation/questions/task.md.txt"' <<<"$default_output"
grep -Fq 'grid-agent analysis-generic --application "custom-domain" --instructions "custom-questions.txt" --provider "deepseek" --model "deepseek-v4-flash"' <<<"$override_output"
! grep -Fq 'grid-agent analysis-generic' < <(make -C "$test_root" --no-print-directory -n analysis)
```

- [ ] **Step 2: Confirm the test fails**

Run `bash tools/test_makefile_application.sh`.

Expected: non-zero because `application` does not exist.

- [ ] **Step 3: Implement the target**

Extend `.PHONY` with `application test-makefile-application`; add this help line:

```make
	@echo "  make application [INSTRUCTIONS=...] [PROVIDER=...] [MODEL=...]  Run the formal registered application"
```

Add after `analysis-generic`:

```make
application: APPLICATION = pandapower-static-analysis
application: INSTRUCTIONS = $(ANALYSIS_DEFAULT_INSTRUCTIONS)
application: analysis-generic

test-makefile-application:
	bash tools/test_makefile_application.sh
```

Change the aggregate test target to:

```make
test: test-agent test-simulator test-tools test-makefile-application
```

- [ ] **Step 4: Verify the target**

Run:

```sh
bash tools/test_makefile_application.sh
make help | rg 'make application'
```

Expected: both exit 0 and help identifies the production application entry.

- [ ] **Step 5: Commit**

```sh
git add Makefile tools/test_makefile_application.sh
git commit -m "feat: add formal application make target"
```

### Task 2: Consolidate the operator documentation

**Files:**

- Modify: `docs/PANDAPOWER-APPLICATION.md`
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `docs/RUNBOOK.md`
- Modify: `docs/MANUAL-VALIDATION.md`

**Interfaces:**

- Consumes: `application`, `analysis`, and `validate-application`.
- Produces: one detailed formal-application reference at `docs/PANDAPOWER-APPLICATION.md`; discovery documents retain only short entry-point references.

- [ ] **Step 1: Write the failing documentation discovery check**

Run:

```sh
rg -F 'PANDAPOWER-APPLICATION.md' README.md README.zh-CN.md docs/RUNBOOK.md docs/MANUAL-VALIDATION.md
```

Expected: initially fail until every discovery document links to the single reference.

- [ ] **Step 2: Make the reference current**

Replace `approved design; Makefile entry implementation pending` with `current operator reference` in `docs/PANDAPOWER-APPLICATION.md` and preserve its output, compatibility, billing, evidence, and failure-contract sections.

- [ ] **Step 3: Remove duplicated long execution blocks**

Keep short references to `make application`, `make analysis`, and `make validate-application` in README, RUNBOOK, and MANUAL-VALIDATION. Replace detailed Provider-backed command blocks with a link to `docs/PANDAPOWER-APPLICATION.md`.

- [ ] **Step 4: Verify documentation**

Run:

```sh
git diff --check
rg -F 'PANDAPOWER-APPLICATION.md' README.md README.zh-CN.md docs/RUNBOOK.md docs/MANUAL-VALIDATION.md
```

Expected: no whitespace errors and four discovery-document matches.

- [ ] **Step 5: Commit**

```sh
git add docs/PANDAPOWER-APPLICATION.md README.md README.zh-CN.md docs/RUNBOOK.md docs/MANUAL-VALIDATION.md
git commit -m "docs: consolidate pandapower application guidance"
```

### Task 3: Verify the production application

**Files:**

- Modify: `docs/status/JOURNAL.md` after a verified Provider-backed outcome.

**Interfaces:**

- Consumes: `make application` and configured, authorized Provider credentials.
- Produces: a current-run directory with composite stdout and admitted artifacts.

- [ ] **Step 1: Run non-billable gates**

```sh
make doctor
make validate-application
make test-e2e
make validate
```

Expected: all exit 0; application acceptance contains two passing cases.

- [ ] **Step 2: Run the formal application**

```sh
make application
```

Expected: one `capability-agent-output/1.0` stdout object with `core` and `domains.grid`.

- [ ] **Step 3: Inspect current-run artifacts**

Use the `core.run_id` from Step 2 and run:

```sh
find runs/{run_id} -type f | rg '/(turns|domains/grid/evidence|output|core)/'
```

Expected: turn, evidence, output, and core artifacts exist for the new run.

- [ ] **Step 4: Journal the verified result and commit task-owned changes**

```sh
git add Makefile tools/test_makefile_application.sh docs/PANDAPOWER-APPLICATION.md README.md README.zh-CN.md docs/RUNBOOK.md docs/MANUAL-VALIDATION.md docs/status/JOURNAL.md
git commit -m "feat: ship formal pandapower application entry"
```
