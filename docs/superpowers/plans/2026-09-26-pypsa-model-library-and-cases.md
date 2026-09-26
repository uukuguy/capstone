# PyPSA Model Library and Business Cases Implementation Plan

**Status:** local model library and scripted-agent phase complete on 2026-09-26; container and frontend phase deferred by the requested priority.

> **For agentic workers:** implement each checked task with focused tests before code and verify the final main checkout. This plan is executed inline because the user requested direct progress.

**Goal:** Register all six PyPSA 1.3.0 example Networks in an extensible authority-owned library and deliver agent-ready business cases with an App-facing presentation contract.

**Architecture:** A pinned catalog records official and existing project models. An explicit installer checks official bytes before the authority opens them. Model revisions bind the source digest and current run. Case manifests select a catalog entry and semantic capabilities; application output carries bounded business results and evidence.

**Tech Stack:** Python 3.14, PyPSA 1.3.0, HiGHS, JSON contracts, pytest, Makefile.

## Global constraints

- Keep the Kernel domain neutral and retain the existing grid CLI two-field stdout contract.
- Never expose raw Network, DataFrame, paths, arbitrary functions or solver options as model tools.
- Network access is operator-initiated asset installation; agent turns use only locally checked registered assets.
- Preserve existing 15 JSON models and all unrelated user worktree changes.
- The `carbon_management` asset is 38,358,898 bytes; catalog registration is distinct from interactive solve support.

## File map

- `packages/pypsa-model-authority/src/pypsa_model_authority/catalog.py`: parse and validate the catalog; preserve existing `load_registered_model` behavior.
- `packages/pypsa-model-authority/src/pypsa_model_authority/resources/model-library.json`: official pinned source and applicability metadata.
- `packages/pypsa-model-authority/src/pypsa_model_authority/model_library.py`: explicit asset installation and verified read.
- `packages/pypsa-model-authority/src/pypsa_model_authority/store.py`: current-run official model revision verification and Network construction.
- `packages/pypsa-model-authority/src/pypsa_model_authority/operations.py`: bounded catalog/open/inspect/validate behavior.
- `packages/pypsa-network-modeling-domain-pack/src/pypsa_network_modeling/resources/`: model-facing semantic contracts and guides.
- `validation/pypsa-cases/`: business case definitions and expected App projection.
- `docs/RUNBOOK.md`, `README.md`, `README.zh-CN.md`: install, run, provenance, and supported-case guidance.
- `containers/` (new): PyPSA worker image build and startup validation; image assets are read-only and runs use mounted persistence.
- `apps/` (future): frontend and bounded job API consuming the application presentation projection.

### Task 1: Catalog and checked installation

- [x] Add six official manifest entries with source URLs, exact sizes and SHA-256 hashes.
- [x] Test all six IDs, 21 total catalog entries, and unknown-ID rejection.
- [x] Test bad bytes and symlink rejection; install and verify all six real upstream assets locally.
- [x] Implement catalog listing, official entry lookup, explicit installation, and verified asset reads with an atomic same-directory publish.
- [x] Run focused catalog tests.

### Task 2: Current-run official revision and bounded inspection

- [x] Open an official sample through the authority and verify current-run revision, result, and evidence.
- [x] Reject changed assets and cross-run model references in focused tests.
- [x] Extend model revisions for the pinned official source while keeping JSON revisions compatible.
- [x] Add bounded inspect, validate, and topology results, including counts, omitted totals, and coordinate status.
- [x] Run authority and Network Pack tests; manually open and inspect all six official assets.

### Task 3: Agent-ready business cases and application output

- [x] Define seven case manifests with explicit runnable or catalog-only status.
- [x] Add provider-free `AgentApplication` acceptance selected from case manifests; the regional case compares two real current-run dispatch results.
- [x] Produce bounded case presentation JSON with provenance, scenario, solver data, topology, limitations, answer/result/evidence references, and admission checks.
- [x] Run the official AC/DC and SciGRID-DE cases through the local application; verify installed-wheel handoff of the model and operations Packs independently.

### Task 4: Documentation and release gates

- [x] Document explicit installation and case execution commands in the runbook and bilingual READMEs.
- [x] Run focused tests, `make doctor`, `make test`, `make test-e2e`, `make validate`, `make test-packages`, package boundaries, `make check-types`, and `git diff --check`.
- [x] Verify the actual main `grid-agent run` stdout envelope after integration.
- [x] Journal verified results without touching unrelated staged configuration.

### Future phase: container and frontend contract

- [ ] Build a PyPSA container with six checked model assets in a read-only directory and a separate persistent run mount. Verify startup rejects missing or altered assets.
- [ ] Publish bounded model/case/run/presentation API shapes with opaque IDs and asynchronous run status; keep raw PyPSA and credential state behind the backend.
- [ ] Build a frontend flow that selects a runnable case and model, follows a run, and displays its validated answer, metrics, provenance and admitted evidence.
- [ ] Add a bounded topology/snapshot projection for frontend maps, with coordinate fallback and omitted counts; verify result overlays cite admitted current-run evidence.
- [ ] Verify the containerized backend and frontend against one complete business case, including refresh after a backend restart.
