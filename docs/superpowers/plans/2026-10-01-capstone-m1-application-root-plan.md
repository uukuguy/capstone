# Capstone M1 Application Root Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move hosted Thread process control and application assembly ownership into `capstone-agent`, leaving `grid-agent.hosted` as a thin pandapower compatibility adapter.

**Architecture:** `capstone-agent` will expose a typed hosted application registration seam that accepts an application-owned `ThreadApplicationAssembly` factory and owns API/worker mode dispatch. The pandapower adapter will retain only registered authority/profile/session construction and delegate process startup to the Capstone host. No `capstone-agent` source will import `grid_agent`; future PyPSA registration can use the same seam.

**Tech Stack:** Python 3.12, dataclasses, callable registration, existing `capstone_agent.cli`, pytest, package-boundary checker.

## Global Constraints

- Preserve `Application -> Domain Pack -> Kernel -> registered Authority`.
- `capstone-agent` is the only application host; `grid-agent` remains a compatibility adapter.
- Preserve `serve-hosted` and `work-hosted` command behavior and current Thread protocol.
- Do not add PyPSA behavior or change Web/UI behavior in M1.
- Do not stage the pre-existing `.gitignore` modification.
- Keep `grid-agent` as the owner of pandapower authority/profile imports; `capstone-agent` receives factories through a public seam.

---

### Task 1: Lock the hosted application boundary with failing tests

**Files:**
- Create: `packages/capstone-agent/tests/test_hosted_application.py`
- Modify: `packages/grid-agent/tests/application/test_hosted_thread.py`
- Modify: `packages/grid-agent/tests/application/test_hosted.py`

**Interfaces:**
- Consumes the new `capstone_agent.hosted` functions `run_hosted_api`, `run_hosted_worker`, and `HostedApplicationFactory`.
- Produces regression coverage proving the Capstone host owns mode dispatch and the grid module remains only a factory adapter.

- [ ] **Step 1: Write the failing tests**

Add tests that monkeypatch `capstone_agent.hosted.capstone_main`, pass a factory returning a sentinel assembly, and assert API mode calls `["serve-hosted"]` while worker mode calls `["work-hosted"]` with that assembly. Add an AST/import test that `capstone_agent.hosted` has no import beginning with `grid_agent`.

- [ ] **Step 2: Run the focused tests**

Run:
```bash
uv run --project packages/capstone-agent pytest -q packages/capstone-agent/tests/test_hosted_application.py
```
Expected: FAIL because `capstone_agent.hosted` does not yet exist.

---

### Task 2: Implement the Capstone hosted root

**Files:**
- Create: `packages/capstone-agent/src/capstone_agent/hosted.py`
- Test: `packages/capstone-agent/tests/test_hosted_application.py`

**Interfaces:**
- Produces:
  ```python
  HostedApplicationFactory = Callable[[], ThreadApplicationAssembly]
  run_hosted_api(factory: HostedApplicationFactory) -> int
  run_hosted_worker(factory: HostedApplicationFactory) -> int
  ```
- Each function must call the existing `capstone_agent.cli.main` with exactly one hosted mode and the factory result as `thread_application`.
- The module must remain domain-neutral and must not import `grid_agent`, `grid_simulator`, pandapower, or PyPSA.

- [ ] **Step 1: Implement the smallest typed host**

Use `Callable`, `ThreadApplicationAssembly`, and a private `_build` validator that rejects non-callable factories and factories that do not return `ThreadApplicationAssembly`. Keep the existing CLI as the only process runner.

- [ ] **Step 2: Run the focused tests**

Run:
```bash
uv run --project packages/capstone-agent pytest -q packages/capstone-agent/tests/test_hosted_application.py
```
Expected: PASS.

---

### Task 3: Convert grid hosted entry points into compatibility adapters

**Files:**
- Modify: `packages/grid-agent/src/grid_agent/hosted.py`
- Modify: `packages/grid-agent/src/grid_agent/hosted_worker.py`
- Modify: `packages/grid-agent/tests/application/test_hosted_thread.py`
- Modify: `packages/grid-agent/tests/application/test_hosted.py`
- Preserve: `deploy/entrypoint.sh`; its compatibility process commands continue to invoke the grid adapter.

**Interfaces:**
- `grid_agent.hosted.build_registered_pandapower_thread_application()` remains a compatibility factory with the existing return value.
- `grid_agent.hosted.main()` delegates API mode to `capstone_agent.hosted.run_hosted_api`.
- `grid_agent.hosted_worker.main()` delegates worker mode to `capstone_agent.hosted.run_hosted_worker`.
- No new Web, TUI, model catalog, or PyPSA behavior is introduced.

- [ ] **Step 1: Add delegation assertions**

Extend the existing hosted tests to monkeypatch the Capstone host functions and verify the grid entry points pass the existing pandapower factory without directly invoking `capstone_agent.cli.main`.

- [ ] **Step 2: Refactor the two entry points**

Replace direct `capstone_main` calls with the Capstone hosted functions. Keep all pandapower authority/profile/session construction unchanged in `build_registered_pandapower_thread_application`.

- [ ] **Step 3: Run focused grid tests**

Run:
```bash
uv run --project packages/grid-agent pytest -q packages/grid-agent/tests/application/test_hosted.py packages/grid-agent/tests/application/test_hosted_thread.py
```
Expected: PASS.

- [ ] **Step 4: Run package and integration gates**

Run:
```bash
uv run --project packages/capstone-agent pytest -q
uv run --project packages/grid-agent pytest -q packages/grid-agent/tests/application/test_hosted.py packages/grid-agent/tests/application/test_hosted_thread.py
python tools/check_package_boundaries.py
git diff --check
make doctor
```
Expected: all commands exit 0; existing `.gitignore` remains unstaged.

- [ ] **Step 5: Commit**

```bash
git add packages/capstone-agent/src/capstone_agent/hosted.py packages/capstone-agent/tests/test_hosted_application.py packages/grid-agent/src/grid_agent/hosted.py packages/grid-agent/src/grid_agent/hosted_worker.py packages/grid-agent/tests/application/test_hosted.py packages/grid-agent/tests/application/test_hosted_thread.py
git commit -m "refactor: move hosted process root into capstone agent"
```

---

## Self-review

- M1 moves process ownership and the public hosted seam without introducing a reverse `capstone-agent -> grid-agent` dependency.
- Authority/profile/session construction remains in the pandapower adapter, so M2 can replace the single factory with a composite model/profile registry.
- Thread protocol, Web UI, TUI, CLI stdout, and current-run evidence contracts remain unchanged.
- Real PyPSA catalog and TurnRouter/Jev are intentionally deferred to M2/M3.
