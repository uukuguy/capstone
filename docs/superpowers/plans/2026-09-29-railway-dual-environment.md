# Railway Dual Environment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define an isolated Railway cloud development environment alongside the existing public demo environment, while preserving local high-frequency App iteration and same-image API/Worker operation.

**Architecture:** Keep `capstone-demo` as the public trial environment. Add a separate `capstone-cloud-dev` Railway project or equivalently isolated Railway environment with its own API, Worker, PostgreSQL, artifact bucket, credentials, and App origin. Develop locally against local Compose, validate cloud behavior in cloud-dev, and promote the exact verified backend image/source revision to demo.

**Tech Stack:** Railway services and environments, Dockerfile backend image, PostgreSQL, private S3-compatible artifact storage, Vite App, repository runbook.

## Global Constraints

- API and Worker in each environment use the same backend image/source revision.
- Demo and cloud-dev never share PostgreSQL, artifact storage, operator tokens, or Provider credentials.
- `VITE_API_ORIGIN` contains only the selected public API origin; it never contains secrets.
- Demo public access remains limited to registered scripted cases.
- Local App development continues through `make capstone-local-rebuild` and `make capstone-app-dev`.
- Railway project creation and billing-affecting resource provisioning require explicit operator authorization.

---

### Task 1: Document the two Railway environments

**Files:**
- Modify: `deploy/railway/README.md`
- Modify: `docs/RUNBOOK.md`
- Modify: `README.md`
- Modify: `README.zh-CN.md`

**Interfaces:**
- Documents the environment names, isolation matrix, branch/tag promotion policy, required variables, and validation commands.
- Preserves the current API/Worker/Bucket/App service contract.

- [ ] **Step 1: Add a Railway environment matrix and promotion flow.**

Document `capstone-demo` and `capstone-cloud-dev`, with separate data, credentials, domains, and deployment triggers. State that cloud-dev follows the development revision and demo follows release tags or an explicit promotion.

- [ ] **Step 2: Add deployment and rollback checklists.**

Include health, scripted-case, Provider, report, evidence replay, and image/source identity checks before demo promotion. Include rollback to the previous verified image/source revision.

- [ ] **Step 3: Align the bilingual top-level deployment summaries.**

Update the English and Chinese README deployment sections with the two-environment model and retain the local App workflow.

- [ ] **Step 4: Run documentation checks.**

Run:

```sh
git diff --check
make doctor
```

Expected: exit 0 and no broken deployment links.

- [ ] **Step 5: Commit.**

```sh
git add deploy/railway/README.md docs/RUNBOOK.md README.md README.zh-CN.md
git commit -m "docs: define Railway dev and demo environments"
```

### Task 2: Add non-secret environment configuration checklists

**Files:**
- Create: `deploy/railway/cloud-dev.variables.example`
- Create: `deploy/railway/demo.variables.example`

**Interfaces:**
- Each file is a reviewable key/value checklist with no real secrets.
- The files distinguish cloud-dev and demo values without becoming deploy credentials.

- [ ] **Step 1: Add cloud-dev variable names and safe defaults.**

Set `CAPSTONE_PUBLIC_DEMO=false` by default, use a cloud-dev API/App origin, and mark every secret as `<set-in-railway>`.

- [ ] **Step 2: Add demo variable names and safe defaults.**

Set `CAPSTONE_PUBLIC_DEMO=true`, `CAPSTONE_PUBLIC_PROVIDER=deepseek`, and `CAPSTONE_PUBLIC_MODEL=deepseek-flash`; leave all credentials and endpoints as explicit placeholders.

- [ ] **Step 3: Add a warning header.**

State that these files are checklists, are not complete credentials, and must not be copied into commits with secret values.

- [ ] **Step 4: Validate file hygiene.**

Run:

```sh
git diff --check
rg -n '(sk-|AKIA|SECRET|TOKEN=.{8,})' deploy/railway/*.variables.example
```

Expected: only placeholder names and no credential values.

- [ ] **Step 5: Commit.**

```sh
git add deploy/railway/*.variables.example
git commit -m "docs: add Railway environment variable checklists"
```

### Task 3: Verify the repository and preserve local state

**Files:**
- No source changes.

**Interfaces:**
- Confirms the deployment documentation does not change API contracts or local App behavior.

- [ ] **Step 1: Run focused repository gates.**

```sh
make doctor
git diff --check
```

- [ ] **Step 2: Confirm status and ignored local data.**

```sh
git status --short
git status --short --ignored | rg 'deploy/local-model-assets|\.codex' || true
```

Expected: only intentionally ignored local assets appear; no secrets or runtime state become tracked.

- [ ] **Step 3: Journal and checkpoint.**

Append the durable deployment decision to `docs/status/JOURNAL.md` and refresh the active session baton if the work continues.
