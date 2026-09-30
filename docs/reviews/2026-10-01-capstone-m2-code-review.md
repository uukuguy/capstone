# Capstone M2 Code Review

## Scope

Reviewed M2 commits `c28c2a2`, `027ebc8`, `5630f6e`, `449c3cc`, and
`e31e262`. The review covers model identity validation, composite Authority
catalogs, bounded listing metadata, family runtime dispatch, generic Pi/DSH
capability registration, Thread protocol/page projection, and the PyPSA
adapter.

## Findings

### Critical / High

None.

### Medium

None in the implemented M2 contract. The generic capability registry is an
application-owned control-plane registry and is intentionally passed through
the assembly seam; native Pi skill/MCP/plugin materialization remains a later
Harness runtime adapter step. M2 does not silently treat that registry as a
domain tool catalog or claim that native capabilities are already executable.

### Low

None blocking. Legacy `pypsa39` values remain in provider-free UI fixtures and
protocol regression fixtures only; the Authority-backed PyPSA catalog now
publishes real IDs such as `pypsa-example/scigrid_de`.

## Verification

- Capstone package: `234 passed, 27 skipped`.
- PyPSA Thread capability suite: `20 passed` (the focused catalog/type fix
  suite: `4 passed`).
- Boundary suite: `66 passed`; `python3.14 tools/check_package_boundaries.py`
  passed.
- Changed-source pyright: 0 errors for Capstone and PyPSA M2 files.
- `make doctor` passed.
- `make capstone-local-rebuild` completed with current API/worker image;
  `/health/ready` returned `{"status":"ready"}`.
- `git diff --check` passed.

## Verdict

**Approved.** M2 establishes the Capstone-owned registration and dispatch
seams without importing pandapower or PyPSA into the neutral application. The
next milestone must consume `RuntimeCapabilityRegistry` in the concrete Pi and
DSH Harness clients so registered generic capabilities become executable while
remaining outside Domain Pack semantics.
