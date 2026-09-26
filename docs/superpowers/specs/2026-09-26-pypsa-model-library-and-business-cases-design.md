# PyPSA Model Library and Business Cases

**Status:** local model library and scripted-agent cases implemented; container and frontend remain future work.

## Goal

Capstone's PyPSA authority provides a discoverable, versioned library of registered networks. An application case chooses a library model, gives an agent a bounded business task, and produces a result that a later App can present with model provenance and current-run evidence.

## Scope and sources

The initial official collection is the complete `pypsa.examples` Network set in the repository's pinned PyPSA 1.3.0 release. These six networks are registered alongside the existing 15 project-authored models. The official assets are fetched only by an explicit operator install command from `https://data.pypsa.org/networks/examples/v1.3.0/`, checked against the digests below, and kept in ignored runtime storage. They are never downloaded by an agent turn or redistributed in a wheel. Upstream dataset attribution and terms must be retained for public App display.

| Library ID | Upstream function | Bytes | SHA-256 | Business role |
| --- | --- | ---: | --- | --- |
| `pypsa-example/ac_dc_meshed` | `ac_dc_meshed()` | 109290 | `a976648b7a8f2b11c17435606730304ce7627b7950ff6c12c2125b83bf11ab3d` | AC/DC interconnection |
| `pypsa-example/storage_hvdc` | `storage_hvdc()` | 130077 | `ea7b6a86f7d27b9f54f869d543a4f29ea0123e859760f89c25b92910daadd299` | storage and transfer |
| `pypsa-example/scigrid_de` | `scigrid_de()` | 1530579 | `4f4f38868fc9898db6dc81dc5308b77a00c19e4c2099310f1152093c8f602919` | regional grid operation |
| `pypsa-example/model_energy` | `model_energy()` | 156931 | `11d35d6a19e2fe5841c2aa80219220d79e99edebce90db50253cfeb4d39cadc9` | capacity mix |
| `pypsa-example/stochastic_network` | `stochastic_network()` | 122861 | `dd1da43e4391531577f739b5cee29cac90e825dd903980c7e1497b1faf8a13fb` | uncertain investment |
| `pypsa-example/carbon_management` | `carbon_management()` | 38358898 | `7b1a0e7b37e7861c315ea6b248416d3ac1c9762f433d55a944c4f20208e3495e` | sector and carbon system inspection |

Official source: [PyPSA example Network API](https://docs.pypsa.org/latest/api/other/api-examples/). The names and downloaded bytes above were checked with the pinned 1.3.0 package on 2026-09-26. All six are registered models; registration does not imply that every solver capability applies to every model.

## Ownership

- `pypsa-model-authority` owns the catalog manifest, local asset installation, hash verification, Network construction, immutable revision identity, applicability checks, calculations, results, and evidence.
- Network Modeling Domain Pack publishes semantic catalog/open/inspect/validate capabilities and their contracts. It does not expose paths, NetCDF, a raw `Network`, or DataFrames to the model.
- Operations, Planning, and Sector Packs continue to receive only application-granted, verified model references. Each Pack declares which formulations it can execute for a model. Unsupported combinations fail before solving with a clear reason.
- The application owns business case manifests, selected bindings, task wording, and presentation projection. The Kernel remains domain neutral.

## Catalog and asset lifecycle

Official entries have a stable ID, source URL, pinned PyPSA version, SHA-256 digest, byte count, display name, business theme, and installed state. The existing project models remain registered package resources. Case manifests state which combinations are runnable; future App catalog work can add richer per-model summaries and attribution terms after source review. Future additions use the same manifest plus validation and case acceptance; they do not require a Kernel change.

An operator runs an explicit install command for local development. A container build runs the same command and places all six checked assets in a read-only image directory such as `/opt/capstone/pypsa-models`. It downloads into a temporary file, validates size and SHA-256, then atomically publishes the asset. A failed download, digest mismatch, symlink, or missing asset does not create a usable entry. Agent execution never fetches data. `model.open` pins the catalog ID and asset digest in a current-run model revision. Subsequent reads recheck the trusted installed asset digest before constructing a Network; removal or modification fails closed. Existing project JSON catalog IDs and revision behavior remain compatible.

The catalog exposes bounded metadata so an agent can select or verify a case model without raw data access. A business case selects an exact catalog ID; the authority-owned library entry pins the digest. The selected model is opened at run time, producing a fresh current-run `model_ref`; references from another run remain invalid.

For official assets, `model.validate` currently checks nonempty buses/snapshots plus PyPSA's unknown-bus, time-series, and shape rules, and returns the checked rule names. Other PyPSA consistency warnings remain visible in authority diagnostics; this limited structural pass is not an all-formulations feasibility claim.

## Business cases

Each case manifest names a business question, audience, model ID/digest, required Pack bindings, allowed capabilities, expected result fields, evidence rules, and App presentation fields. Numerical expected values are test assertions against real authority results, not answer text or model shortcuts. The agent may choose the bounded tool sequence, but the application validates the selected model and binds current-turn evidence.

| Case | Model | Current status | Decision task and acceptance |
| --- | --- | --- | --- |
| Regional demand stress | `regional-six-bus` | Runnable | Increase central demand 10 MW per snapshot; compare two current-run dispatch costs and solver states. |
| SciGRID-DE dispatch | `pypsa-example/scigrid_de` | Runnable | Solve fixed-capacity dispatch; present carrier generation and top line-loading summary with source assumptions. |
| AC/DC interconnection | `pypsa-example/ac_dc_meshed` | Runnable structure case | Identify buses, lines, links and connections; make no unsupported flow or transfer claim. |
| Interconnector and storage | `pypsa-example/storage_hvdc` | Catalog-only | Requires registered scenario comparison, bounded storage state, transfer and energy-balance projection. |
| Investment under uncertainty | `pypsa-example/stochastic_network` | Catalog-only | Requires registered stochastic solve and separate probability, capacity and scenario outputs. |
| Capacity transition | `pypsa-example/model_energy` | Catalog-only | Requires registered planning formulation and cost decomposition. |
| Sector/carbon inventory | `pypsa-example/carbon_management` | Catalog-only | Requires carrier-filtered inventory view; no initial full-network reoptimization. |

The local acceptance uses the small regional case and official SciGRID-DE and AC/DC examples. The regional case is in the offline test gate. Official assets are opt-in installation, so their application runs are local integration checks rather than required fast tests. A case is marked runnable after its real PyPSA workflow, bounded output, and source/target evidence have passed; installed-wheel acceptance of the new case runner remains a release follow-up. Catalog-only models remain clearly labelled as such. The provider-free scripted agent proves application composition and evidence binding, not open-ended LLM reasoning.

## App presentation contract

### Professional case introductions

Each runnable case owns a static `introduction` object in `validation/pypsa-cases/cases.json` and a linked Markdown article under `validation/pypsa-cases/introductions/`. Structured fields cover a short summary, business problem, completed work, PyPSA/framework support, the change in professional interaction, the agent mechanism, professional and framework value, interpretation boundary, and current validation scope. The Markdown article uses the same statements in a readable case narrative. Catalog-only cases gain introductions when their workflows become runnable.

The introduction distinguishes the default fixed-question run from the explicit three-instruction demonstration. `demo_instructions` is an ordered list of professional requests for a continuous, single-model App session, and `demo_workflow` partitions the existing scripted capability sequence across those turns. The local `--demo` and exact-match `--instructions` modes now submit that sequence through the Kernel's ordered `ApplicationRequest.questions` contract. A unified client selects a trusted Application Profile and passes the same list to the selected application, which binds its parallel Domain Packs and registered authorities; the client does not call a Pack's internals or a raw network directly. Deterministic multi-turn acceptance proves context reuse and per-turn answer/evidence commits for all three cases. It does not prove open-ended LLM planning, arbitrary user instructions, or registration of PyPSA in the current generic CLI.

An App can use the structured content for a card and sectioned case detail, and the Markdown for a full article. The catalog owns static context; the current run's presentation owns solver status, metrics, topology results, answer and admitted references. Neither introduction predicts an outcome or presents the scripted provider as verified open-ended LLM planning. The App resolves only the declared Markdown assets for registered case IDs, never a caller-supplied path.

The application projection supplies: case title and question; model display name, origin, version, data timestamp and attribution; scenario assumptions; ordered instructions and committed turn answers; KPI cards with units and objective meaning; baseline/variant comparison with both result references where present; topology/time-series data references; solver status; limitations; and clickable current-run result/evidence references. The App reads these through validated application output, not raw simulator files. An unavailable model displays an installation action rather than an invented answer. This contract can serve a CLI report first and a future graphical App without making it a Kernel-wide output requirement.

PyPSA 1.3.0 already provides `Network.plot.map()` for static maps, `Network.plot.iplot()` for interactive Plotly, and `Network.plot.explore()` for interactive Pydeck maps. The container may use these for internal diagnostics and exported report images. The frontend's primary map consumes an authority-produced, bounded topology projection: stable bus/branch IDs, coordinates or a declared schematic fallback, component types, and a selected snapshot's admitted result metrics. It can then render flows, loading, prices, and baseline/variant differences without receiving a raw Network or executing Python. A visual is labelled “model topology” until a result/evidence reference establishes a computed overlay. For large official networks, the projection supports server-side filtering or clustering and reports the omitted count.

## Container and frontend deployment

Capstone's PyPSA backend runs in a container with the pinned Python environment, all six checked official model assets, the four Domain Packs, application assembly, and the authority process. The model directory is mounted or baked in read-only. Run workspaces and admitted results/evidence use a persistent volume or object-backed artifact service, not the container filesystem layer. A new container verifies its model catalog before accepting jobs. The existing pandapower dependency set requires a separate Python environment or worker image; the frontend can still present both applications under one product.

The frontend is a unified web client, deployable on Vercel or an equivalent host. It calls a bounded backend API for application/profile selection, model catalog and availability, business case catalog, ordered instruction submission, run status/events, and validated presentation/evidence. The backend selects only explicitly registered application bindings and may route pandapower and PyPSA to different pinned worker environments while keeping one client contract. The API returns opaque run and reference IDs rather than paths or raw NetCDF. Long solves run as asynchronous jobs with status and cancellation; a request/response web function does not execute PyPSA. The UI shows model provenance, scenario inputs, progress, per-turn answers, metrics, and evidence as separate views. Authentication and artifact access checks are enforced by the backend, so a copied run ID alone does not grant access.

## Acceptance and boundaries

1. Six official entries appear in the catalog with checked source metadata; all install reproducibly from the pinned URL and reject tampering or missing bytes.
2. Existing 15 project-authored models, `model.open`, four Packs, grid CLI stdout, and current-run evidence remain compatible.
3. At least one official network is opened, inspected, and used by a real registered business workflow through the application; the resulting answer is committed with admitted current-run references.
4. The case and App projection distinguish available from runnable and never present a catalog record as a completed simulation.
5. Full `make doctor`, `make test`, `make test-e2e`, `make validate`, and package gates pass after behavior changes. Provider-backed validation remains opt-in.

Unregistered files, runtime URL fetches, raw Network/DataFrame exposure, arbitrary solver options, and direct cross-Pack state access remain outside this feature.
