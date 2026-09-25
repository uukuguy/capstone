# PyPSA Power Operations Pack Plan

**Status:** active implementation plan  
**Design:** [approved four-pack design](../specs/2026-09-25-pypsa-multibinding-domain-packs-design.md)  
**Predecessor:** Network Modeling Pack and reference handoff on `main` at `a70ccff`.

## Outcome

Publish a separately installable `pypsa-power-operations-domain-pack` only after
real PyPSA 1.3.0/HiGHS calls and current-run evidence are verified. The first
release covers fixed-model economic dispatch, fixed-capacity unit commitment,
selected line-outage security-constrained dispatch, and dispatch-to-AC
validation. Every operation receives an application-granted model or result
reference, uses a fixed registered authority endpoint, and returns typed
status, objective meaning, formulation, solver version, revision lineage,
result, and evidence. Infeasible or warning termination is a typed failure,
not an admitted success. No user-authored Linopy callable or raw Network crosses
the boundary.

Official PyPSA references: [optimization accessor](https://docs.pypsa.org/v1.3.0/api/networks/optimize/),
[unit commitment](https://docs.pypsa.org/v1.3.0/examples/unit-commitment/),
[security-constrained LOPF](https://docs.pypsa.org/v1.3.0/examples/scigrid-sclopf/),
and [power flow](https://docs.pypsa.org/v1.3.0/user-guide/power-flow/).

## Sequence

1. **Authority and fixtures.** Add small registered dispatch, commitment, and
   three-bus contingency models to the existing authority catalog, with exact
   versions and deterministic, finite input bounds. Add a separate fixed
   `pypsaopsctl` executable/operation protocol so each Pack's
   `environment.describe` exposes only its own published capability IDs. The
   operations endpoint uses a trusted source model workspace and its own target
   result/evidence store. Solver calls stay in the authority package. First
   write one focused authority test per distinct formulation and one
   infeasible/status boundary; then implement the four operations.
2. **Receipt-gated execution.** Add a Kernel read-only receipt resolver that
   replays the application context, validates content digest and run identity,
   and returns a typed receipt. The operations Pack executor checks the
   receipt's target, source, purpose, and capability family and verifies the
   registered source revision before sending a fixed request to
   `pypsaopsctl`. The model cannot choose source paths or authority endpoints.
   Existing default-deny and tamper tests remain lean; add one direct target
   bypass rejection test.
3. **Domain Pack.** Supply the complete public Kernel SPI, four exact JSON
   contracts under `pypsa_ops_`, policy, guides, projector, state, output,
   answer admission, and fixed provisioner. No sibling Pack import. Test
   `prepare_application` with modeling and operations bindings, then one
   provider-free application sequence that grants model handoff, executes
   dispatch and AC validation, checks separate binding evidence, report and
   replay. Commitment and security capabilities each get a focused authority
   and Pack call proof.
4. **Release.** Add a machine-readable operations coverage catalog, isolated
   PyPSA wheel install smoke, package-boundary rules, setup/test targets, and
   aligned architecture/onboarding/README facts. Run focused tests, then
   `make doctor`, `make test`, `make test-e2e`, `make validate`,
   `make test-packages`, type/boundary checks, diff/link checks. Keep billed
   provider validation off. Fast-forward accepted commits to `main` and verify
   its real grid CLI entry point.

## Acceptance boundaries

- The source model revision is never mutated by a solve; each result names its
  revision and all authority-owned result/evidence references are current-run.
- Dispatch objective is system operating cost, commitment includes binary
  status and startup costs, security formulation names the selected registered
  outage set, and AC validation reports convergence and bounded electrical
  observations separately from linear dispatch.
- A model-supplied reference or receipt cannot bypass the application grant or
  select another binding's workspace.
- The grid compatibility CLI still writes exactly `question_id` and
  `answer_output` to stdout.
