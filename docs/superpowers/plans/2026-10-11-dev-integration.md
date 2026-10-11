# Dev integration implementation plan

> Execute in this session in order. Preserve user files, runtime data and all
> unmerged experiment references. User approved the design and implementation.

**Goal:** Establish a development integration branch and close the current
answer baseline before starting the Research Model implementation branch.

**Architecture:** dev owns current integration and project control; main owns
release snapshots. Exact tags and stage receipts own deployment identity.

**Tech Stack:** Git, GitHub App publishing, GitHub Actions, Python and static HTML.

## Global constraints

- No cloud deployment or paid Provider calls in this task.
- Keep Linux/macOS required check names and registered Authority boundaries.
- No history rewrite, bulk experiment merge or ignored-data deletion.

## Tasks

- [x] Create dev from accepted main723b8e8 through the independent App;
  retarget PR #11, set default branch and read back both branch protections.
- [x] Add fail-closed change classification in tools/ci_scope.py with tests in
  tools/tests/test_ci_scope.py. Update verify.yml: docs, governance and product
  checks on dev; full checks for main PRs and explicit release dispatch.
  Verify focused classification and existing gate contracts before publishing.
  Route trusted Issue policy/source and normal repair PRs to dev in
  tools/issue_automation/{cli,repair,bootstrap,github,service}.py; retain immutable
  task receipts, reject old mismatched PR recovery, and run the complete tool
  suite without selecting the optional real Docker image.
- [x] Align AGENTS.md, bilingual READMEs, lifecycle, canonical worklist,
  CURRENT-STATE, INDEX, live checkpoint and VERSION-CONTROL. Regenerate overview
  using actual Git sources. Check desktop/mobile layout and all source edges.
- [x] Review and publish the updated PR #11; merge only after exact required
  checks pass. Fast-forward local dev and make it the main development checkout.
- [x] Tag exact local technical baseline2473e48 with verification limits and
  source receipts. Start feat/research-model from accepted dev, preserve R0.
  Update control records and affected research plans; do not claim R1 complete.

Validation: focused CI/gate tests, make doctor, relative Markdown links,
CLAUDE.md relative symlink, git diff --check, renderer compilation, browser
source/edge/card/mobile checks, remote protection/default/PR readbacks.

Receipt: PR11cfa6c1c merged50d8ebc after exact CI38126098431 success;
Linux60seconds/macOS131seconds. Independent review APPROVE,68 local checks pass,
two optional Docker tests skipped. Root development checkout follows dev;
feat/research-model starts from50d8ebc, R1 remains unimplemented. B2 local tag
published; merged PR9/10/11 branch names archived and closed without deleting data.
