# Network element name consistency

## Scope and cause

The operator diagram must show the same component names as the registered
Authority tools. Pandapower's diagram accepted only string-valued names. Its
numeric IEEE bus names therefore became zero-based table indexes in the App,
while semantic tools returned the original model names.

| IEEE39 internal bus ID | Old diagram label | Model/tool name and corrected label |
| --- | --- | --- |
| `10` | `Bus 10` | `11` |
| `12` | `Bus 12` | `13` |

## Change

- Pandapower semantic records and diagrams share `queries.element_name`.
  Numeric names, including zero, remain model names. Missing or empty names
  use the same index fallback in both paths.
- Buses, lines, two-winding transformers and three-winding transformer legs
  use that shared name. Separate transformer terminal IDs remain intact.
- Internal IDs, endpoint indexes, model revisions, calculations and evidence
  references are unchanged. Saved historical diagrams are not rewritten.
- The recorded IEEE39 UI fixture now carries the same Authority labels.
- PyPSA already uses its component name indexes for diagrams, topology tools
  and operation result tables. No renumbering was added. Tests cover all
  project-registered models and named/numeric NetCDF components, including
  lines, transformers and links.

## Verification

- Before the repair, nine numeric/string/missing-name regression cases failed
  on diagram/tool name equality. A separate three-winding transformer test and
  the recorded UI fixture test also detected mismatched labels.
- Simulator suite: 188 passed.
- Pandapower Thread and worker network projections: 73 passed.
- PyPSA operator diagrams: 17 passed.
- App: 269 passed; production build passed. The renderer preserves supplied
  model names for both Authority sources.
- `make doctor`, `make check-types`, `make check-package-boundaries` and
  `git diff --check` passed.
- Installed PyPSA matrix: all 15 project models and five drawable official
  models passed name checks. `pypsa-example/carbon_management` retains its
  existing `diagram_too_large` result; this repair does not change capacity.
  The complete record is in
  `runs/topology-names-20261006/pypsa-name-check.json`.
- Upstream pandas/pandapower warnings and the existing App bundle-size warning
  remain. They do not indicate name-check failures.

## Local runtime acceptance

`make capstone-local-rebuild` passed. API and both worker families run image
`sha256:e7cb2790796517e64f9dca9441cd9a45c1771f783cacf27878e29ac08ff4b09c`.
The API at `http://127.0.0.1:8767/health/ready` is ready; the Vite App returns
HTTP 200. Logs are in `runs/topology-names-20261006/local-rebuild.log`.

The running API's registered diagram endpoints passed these checks:

- IEEE39: all 39 buses and 46 branches use semantic-tool names. Internal bus
  IDs `10` and `12` return labels `11` and `13` respectively.
- PyPSA SciGRID-DE: all 585 buses and 948 branches use model component names.
- Provider calls: zero. The result is recorded in
  `runs/topology-names-20261006/local-api-name-check.json`.

The browser connection timed out twice. Browser visual acceptance is therefore
not claimed. App rendering tests pass. No Provider validation, cloud deployment,
data migration or rewrite of historical artifacts is part of this repair.

## 2026-10-07 — Visible component types

The user confirmed that bare numbers made buses and branches hard to
distinguish. The App now adds the type at render time: `Bus 13`, `Bus 14`,
`Line 17`, `Trafo 0`, `Trafo3W 15`, `Transformer T13-central` and
`Link electrolyser-0`. Canvas text and hover titles share this format.
Existing matching type prefixes are preserved without duplication.

Authority names, internal IDs and stored diagrams retain their prior values;
the prefix is a presentation detail. Seven checks failed before the change.
The complete App suite then passed 276 tests and the production build passed.
`make capstone-local-rebuild` passed with API and both worker families on
`sha256:2a31fe7095e6df100ce74b17d451e1f82cfae5a4b57aa4837191a03994d900fb`.
The live Vite module contains the new bus and branch formatting calls. The
rebuild log is `runs/topology-names-20261006/local-prefix-rebuild.log`.
No cloud stage was updated.

## 2026-10-07 — Selected pandapower prefixes

The user selected lowercase `bus`, `line` and `trafo` for the App. Both
pandapower and PyPSA use this display format. Two- and three-winding
transformers use `trafo`; PyPSA links use `link`. The canvas and hover titles
use the same labels. Existing type prefixes are normalized without duplication;
the name suffix, authority payload and element IDs remain unchanged.

Thirteen focused checks failed before the change. The full App suite then
passed 278 tests, and the production build passed. The live Vite module uses
the selected prefixes. `make capstone-local-rebuild` passed with API and both
worker families on
`sha256:76af6e66fca0b89a19c674826cc7142e9fce84fc5e4b12245cbdccd4328b216d`.
The rebuild log is
`runs/topology-names-20261006/local-pandapower-prefix-rebuild.log`.

## Release gate baseline

The user authorized cloud-development verification and demo promotion on
2026-10-07. The complete test suite and 42 end-to-end checks passed. The first
`make validate` run stopped because the protected simulator digest still named
the old tree. The current simulator tree contains the reviewed naming repair
and its tests, committed in `3adca04`. The gate baseline now names that tree;
the protected path list and all other digests remain unchanged. The original
failure log remains in `runs/topology-names-release-20261007/validate.log`.
