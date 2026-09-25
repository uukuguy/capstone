# PyPSA Model Reference and Network Modeling Plan

**Status:** active implementation plan  
**Design:** [approved PyPSA pack design](../specs/2026-09-25-pypsa-multibinding-domain-packs-design.md)  
**Scope:** program order 2 only. The operations, planning, and sector packs stay unregistered.

## Goal and contract

Deliver a separately installable `pypsa-model-authority` and
`pypsa-network-modeling-domain-pack`. A registered, run-scoped authority holds
immutable PyPSA model revisions. The modeling pack publishes bounded semantic
model creation, derivation, and inspection. One explicit application policy can
admit a source model reference for a named target binding and capability family;
the target receives only a verified receipt and reference. The default remains
deny. No tool argument can select an executable, authority endpoint, source
path, credential, or arbitrary Python operation.

Pin `pypsa==1.3.0` and `highspy==1.15.1` in the new authority distribution.
The release exists on [PyPI](https://pypi.org/project/pypsa/), and the
[versioned PyPSA API](https://docs.pypsa.org/v1.3.0/api/networks/indexing/)
documents `Network.set_snapshots`. The first modeling contract does not invoke
a solver; the solver pin fixes the installed authority environment for the
dependent operations pack.

## Owned files and interfaces

| Unit | Files | Public boundary |
| --- | --- | --- |
| Authority protocol and model store | `packages/pypsa-model-authority/pyproject.toml`, `src/pypsa_model_authority/{models,store,operations,cli}.py`, `src/pypsa_model_authority/resources/models/`, tests | `pypsamodelctl request --workspace <trusted-run-root>`; one `pypsa-model-capability/1.0` JSON request and response |
| Modeling Domain Pack | `packages/pypsa-network-modeling-domain-pack/pyproject.toml`, `src/pypsa_network_modeling/{profile,provisioning,execution,authority,projection,state,output,guide,resources}.py`, contract and guide resources, tests | `build_pypsa_network_modeling_profile()` through public Kernel SPI; tool prefix `pypsa_model_` |
| Typed sharing | Kernel `application/profile.py`, `composition.py`, `turns.py`, a bounded handoff module and tests | Explicit source/target/family grant, authority-validated receipt; deny if no grant |
| Assembly and release | `Makefile`, package setup/verification tooling, `docs/architecture/capstone-framework.md`, onboarding guide, both READMEs | One explicitly selected modeling binding; installed-wheel two-binding conformance with a test receiver |

Model references are content-addressed strings, never paths. Every stored
revision contains `run_id`, registered catalog ID, parent reference, typed
component edits, snapshot index/weightings, canonical component digest, and
PyPSA version. The authority reconstructs a `pypsa.Network` internally for
inspection, and persists immutable JSON documents. A result and its evidence
identify the exact revision. The receipt binds source binding, target binding,
run ID, model reference/digest, purpose, and allowed capability family.

## Task 1: Registered model store and real PyPSA construction

1. Add one small registered two-bus model fixture under authority resources.
   The catalog ID, snapshots, buses, one load, one generator, and one line are
   fixed data. Reject unknown catalog IDs and arbitrary source paths.
2. First write focused authority tests: open the registered fixture, derive one
   typed change, inspect both revisions, and verify the parent remains intact.
   Include one foreign-run reference and one altered document case. Run:

   ```sh
   uv run --project packages/pypsa-model-authority pytest packages/pypsa-model-authority/tests/test_model_store.py -q
   ```

3. Implement `CapabilityRequest` with exact protocol/version/capability and
   bounded arguments. `model.open` accepts `catalog_id`; `model.derive` accepts
   `model_ref` plus a constrained edit such as a load `p_set` update;
   `model.inspect` accepts `model_ref`. Construct the real Network inside the
   authority with `Network()`, `set_snapshots(...)`, and typed `add(...)` calls.
   Persist a new canonical model document and return `model_ref`, `result_ref`,
   and `evidence_refs` without raw Network data or model-selected paths.
4. Keep the CLI's stdout to one protocol JSON object and diagnostics on stderr.
   Verify one real CLI request and a malformed request.

## Task 2: Complete modeling Domain Pack

1. Add focused tests that construct the complete Profile, prepare its trusted
   endpoint and no-credential lease, call each published modeling operation,
   and admit current-run result/evidence. Start with a failing test before code.
2. Publish exact JSON contracts for `model.open`, `model.derive`, and
   `model.inspect`; map them to names under `pypsa_model_`. The Pack provisioner
   copies/locates only the installed `pypsamodelctl`; the executor fixes the
   protocol, executable, workspace, and sanitized environment. The authority
   adapter verifies model/result/evidence digests and run ownership. The
   projector records only bounded model metadata and refs.
3. Supply all mandatory DomainRuntimeProfile components: state, answer policy
   and admission, policy, digest-bound guides, presentation, output, acceptance,
   and provisioning. Use the inventory Pack's complete SPI as the closest
   analog, while keeping PyPSA semantics and credentials within this Pack.
4. Run the new Pack's focused tests and a one-binding provider-free
   `AgentApplication` acceptance. Exact command:

   ```sh
   uv run --project packages/pypsa-network-modeling-domain-pack pytest packages/pypsa-network-modeling-domain-pack/tests -q
   ```

## Task 3: Explicit read-only model-reference handoff

1. Add a Kernel test with two prepared bindings. With default `deny`, reject a
   target invocation using a source model reference. With one declared grant,
   record a source/target/run/model/purpose/family decision before target call.
2. Add a typed `ModelReferenceGrant` to the application policy contract and a
   handoff receipt value type. The grant is installed by trusted application
   assembly and names fixed bindings and capability family; model arguments
   cannot alter it. Require the source authority to verify its current-run
   model revision and require the target authority to admit the receipt against
   the same registered run store. Unknown target, stale or foreign-run model,
   altered receipt, and absent grant all fail before target execution.
3. Keep the generic Kernel free of PyPSA imports. A test-only receiver binding
   exercises the public SPI and shared authority protocol; the later operations
   Pack will replace that receiver in its own acceptance. Verify the accepted
   transfer and one representative failure per distinct trust boundary.

## Task 4: Installed application proof and integration

1. In a clean install, run a provider-free two-turn application: first create
   a real model revision, then derive or inspect it through an admitted target
   receipt. Assert exact source and target bindings, run ID, revision lineage,
   current-run result/evidence, answer admission, report, and replay. Confirm
   the managed Pi descriptor registers the modeling tools and one core group.
2. Register the two new distributions in setup, package-boundary, and
   clean-wheel scripts without changing the grid compatibility CLI. Publish
   only tested modeling capabilities in a machine-readable coverage catalog.
   Align architecture, onboarding, README, and README.zh-CN product facts.
3. Run focused tests first. Then run `make doctor`, `make test`,
   `make test-e2e`, `make validate`, `make test-packages`, `git diff --check`,
   and the `CLAUDE.md -> AGENTS.md` symlink check. Do not run billed provider
   validation. Integrate accepted commits to `main` and verify its real grid
   CLI entry point there.

## Acceptance boundary

- Published operations are backed by real PyPSA 1.3.0 calls and an installed,
  pinned authority. Unimplemented operations and the other three packs are not
  exposed to the model.
- The first revision remains immutable after a derived revision is created.
- Only a current-run, policy-granted, authority-verified model reference crosses
  a binding boundary; no raw Network, DataFrame, arbitrary file, or solver
  callable crosses it.
- The original grid `run` stdout still has exactly `question_id` and
  `answer_output`.
