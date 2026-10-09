# Native resource installation receipt

The project setup command installed the two selected resources in an isolated
local runtime. The [machine receipt](2026-10-09-native-resource-installation.json)
records source hashes, all 102 dependency versions, ten tool schema hashes,
input and result hashes, the protocol, and cleanup. This is a sample observation.
It does not establish a current registered Capstone model or simulator evidence.

Run `make install-agent-resources` from the repository root. The command fetches
missing fixed sources, verifies the selected commits and files, builds a new
Python environment, runs the MCP sample check, and atomically publishes the
installation pointer. Use `RESOURCE_INSTALL_ARGS=--no-fetch` to require existing
source clones. Operator options also include `--source-root` and `--config-root`.
No personal client configuration is changed. Task execution never downloads a
resource or dependency. Linux images must run setup for Linux; do not copy this
Mac environment into an image.

The fixed `venv/bin/python` launcher may link to the operator-selected base
CPython outside its installation root. Its base binary digest is recorded in
the accepted descriptor. Check that digest before any launch or runtime probe.
A changed link target fails verification. Source and resource paths remain
confined to their trusted roots; no arbitrary external interpreter is admitted.

The accepted local installation uses CPython 3.12.12 on Darwin arm64. It uses
pandapower 3.4.0, MCP and MCP types 2.3.0, PowerIO 0.11.4, and PowerMCP 0.4.0.
The selected commits are in the [lock](../../configs/runtime/power-samples.lock.json).
The real MCP check negotiated protocol `2025-11-25`, listed ten tools, and ran
`load_network`, `get_network_info`, `audit_network`, and `run_power_flow`.
The pinned PowerSkills asset loaded 39 buses, 35 lines, and 11 transformers.
The audit completed with no findings. The bounded AC power flow converged.
The final fresh runtime check took 66.958 seconds, including cold cache preparation.
The separate warm discovery check took 2.38 seconds.

All three role profiles resolve installed resources. They report
`ready=false`, with `execution adapter is unavailable`. A resource declaration
does not publish a tool. Readiness requires a matching adapter source and an
actual load/publication receipt, plus exact required tool IDs. Native Pi and
Harness adapters remain Tasks 4 and 5.

The original skill provides a useful base-case-first method. Its file paths,
script execution, upstream tool names, and example numbers need adaptation for
Harness. The upstream sample example has different line/transformer counts from
the real load. Harness must use registered model results. The native skill
scripts are private sample operations. They cannot admit Authority evidence.
PowerMCP uses a separate mutable network and returns dictionaries without
Capstone revision/evidence identities. The selected professional enhancement is
an Authority-owned structural audit with exact schemas and current-run admission.
This receipt does not claim that enhancement has been implemented.

PowerMCP has an MIT license; its managed source retains that license. No license
grant was found for the selected PowerSkills subtree. Its body, scripts and asset
remain in ignored managed storage. The marketplace request returned HTTP 403;
the fixed original GitHub source was inspected instead.

Two discovery attempts failed before a pass: the verifier first used MCP 1 style
Python field names, then failed to unwrap the MCP 2 structured `result` object.
The corrected verifier passed. The earlier parent cold 45-second timeout was
not counted as a pass. The warm discovery emitted the optional numba warning.
The solver still converged. No Provider call or deployment was performed.
