# Application capacity initialization

The Application owns capacity policy. Its versioned defaults are in
[`configs/runtime/application-capacity.json`](../../configs/runtime/application-capacity.json).
Kernel and Domain Packs receive neutral numeric mappings through their public
constructors and descriptors. They do not read Application configuration files.
Identity, hash, path, isolation and Authority admission rules remain separate.

For local Compose, set one optional partial override in ignored `deploy/local.env`:

```dotenv
CAPSTONE_CAPACITY_JSON={"artifact_file_bytes":134217728,"native_storage_bytes":8589934592}
```

Run `make capstone-local-rebuild` after changing configuration. The shared setting
is passed to API, workers and the isolated native service. Do not configure these
roles independently. `CAPSTONE_CAPACITY_FILE` is an alternative for a directly
launched process with an operator-mounted configuration file; JSON and file
sources cannot be combined. Custom hosted deployment launchers must forward the
same chosen configuration to each role.

An embedded Application can call:

```python
from capstone_agent.application_capacity import initialize_capacity

profile = initialize_capacity({"artifact_file_bytes": 128 * 1024**2})
```

Initialize before creating runtimes or accepting requests. Limits are positive
exact integers. Unknown names, booleans, negative values and inconsistent
cross-field settings fail at startup. Only `provider_stream_bytes=0` means no
cumulative SSE byte cap: streaming still has bounded buffering, cancellation and
the task deadline. Model context/output settings must fit the selected model.

`GET /api/v1/runtime-capacity` and the `capacity` field of thread-access expose
only safe capacity values and a fingerprint. The App loads these before parsing
payloads. The native executor includes its selected fingerprint in its accepted
configuration identity. Changing configuration requires restarting/rebuilding
the deployment, not changing one active task's tool arguments.

Uploaded source size, bounded model context, observation windows, output-file
size and persistent-storage quota are distinct capacities. Large sources use
chunked storage and private staging; they are not inserted wholesale into the
model prompt. Explicit history windows retain full ledger records and expose
omission/truncation information. A preview window is not a file admission limit.

The lightweight task adapter treats `research_summary_chars` as a model-context
window. When the automatic graph summary exceeds it, the adapter returns an
explicit partial projection, including the retained graph identity, record counts
and text omission counts. `agent_research_read` overview accepts `offset` and
`limit` for recovery pages. Full goal and execution records stay in the ledger.
This projection fallback also applies in DEBUG mode; a summary overflow does not
cancel sibling tasks or close the whole goal. The request guard checks the exact
prepared projection. Storage, file admission and execution resource limits are
separate from this presentation window.

The lightweight task adapter also isolates node capacity failures in DEBUG mode.
It does not subscribe to the legacy process-wide capacity abort listener. A node
that exceeds a limit returns a failed result with the exact capacity diagnostic;
retained observations and admitted products stay available. The controller can
revise or split the work. Local control-request capacity errors request smaller
input or pages, never unchanged retries. Unknown persistence outcomes still use
exact-request recovery. These rules do not waive storage or admission limits and
do not turn incomplete work into whole-goal completion.

Capacity failures include the dimension, measured actual use, configured limit,
unit and phase. The shared UI displays these fields without raw exception text.
Failed output saves retain verified saved-file metadata and the task workspace
for normal retention cleanup. They do not turn partial work into a successful
report or repeat the original task.

Deployment resources remain explicit as well: local native workspace tmpfs uses
`CAPSTONE_NATIVE_WORKSPACE_SIZE` (default `4g`). Provision disk and memory for the
selected workload. A configured 64 GiB upload default is not a claim that every
64 GiB analysis can run in an unchanged container or model context.

External tool implementations may have their own documented output windows.
The pinned SDK read/bash tools report truncation and preserve full file/output
access. Their independent factory configuration remains an audit item; raising
transport limits alone must not be described as changing those tool windows.
