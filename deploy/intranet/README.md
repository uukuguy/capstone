# Intranet development installation

Use the root `compose.yaml` with `deploy/intranet/compose.yaml`, a private
environment file, and a distinct Compose project (`capstone-intranet`). This is
an internal development installation, not a cloud or user-trial release. It has
its own PostgreSQL, object store, operator/control secrets and runtime volumes.
Do not reuse a gateway database or another Capstone installation's data volumes.

The default profile is selected with `CAPSTONE_WORKBENCH_PRESET=intranet`.
Its model endpoint belongs to `configs/runtime/workbench-llm-profiles.json`.
The default model is `Qwen3.8-Flash-Next` at `http://192.168.72.69:8013/v1`,
with a 262,144-token context reported by the service. Existing dsv4 profiles
remain selectable. Previously submitted tasks retain their frozen model selection.
Mount a mode-0600 `connection.json` in the private gateway configuration directory;
select the server's gateway and label it `内网联调`. Do not copy local session state
or put connection tokens in this repository or browser build variables.

The App serves its API through the same origin. Set `CAPSTONE_APP_ORIGIN` and
`CAPSTONE_APP_PORT`; the API port remains host-loopback only. Set exact, source-bound
`CAPSTONE_BACKEND_IMAGE`, `CAPSTONE_GENERAL_IMAGE` and `CAPSTONE_APP_IMAGE` values.
Use `--no-build --pull never` when starting an offline image bundle. Professional
solver workers are optional under the `professional` profile and need their own
provider configuration. The default deployment starts the enterprise/native path.

For an offline x86_64 host, build Linux amd64 images from the recorded commit,
save the backend, native executor, App, PostgreSQL and object-store images, and
transfer them with checksums. Prepare the App from that exact source using
`deploy/prepare_app_source.py` (same-origin `local-dev` identity), build its static
files, then use `App.Dockerfile` here with the shared dev-trial `Caddyfile`.
Keep the deployment receipt's host/stage separate from the App's development-lane
label. Verify image identities, readiness, the default model and gateway, one real
short task and downloaded product hashes before claiming deployment acceptance.

Start or update with the saved project name and private environment file. Never
use `down -v`. Retain the previous image/source receipt for rollback. Scope any
build-cache cleanup to Capstone-owned images; preserve images referenced by any
container and all gateway/Kubernetes resources on the host.

## Persistent Skills and MCP

Installed packages and receipts use the separate `managed-resources` volume.
Do not delete it on update. Local Compose selects the `local` permission profile;
the intranet overlay selects `intranet`, which permits use and denies management.
Skills/MCP management is temporarily disabled in intranet deployments. The settings
entry is disabled, and API/model management actions are blocked by the executor.
`CAPSTONE_INTRANET_RESOURCE_MANAGEMENT_ENABLED` defaults to `0` for both API and
executor. Future enablement requires this deployment switch and policy grants;
existing installed resources retain their use permissions. Local management stays enabled.
Resource installation does not grant network access or business authority.

Before first startup, initialize the private, directory-mounted policy:

```sh
python3 deploy/prepare_resource_policy.py --directory .capstone-agent/resource-policy
```

Set `CAPSTONE_RESOURCE_POLICY_DIR` for a different deployment-owned policy directory.
The helper preserves an existing policy. Each later operation rereads this file;
operators can revoke actions without rebuilding the image. Keep the directory
private. Never copy provider credentials into resource packages or manifests.

The workbench Settings menu offers Skills/MCP management. A Git source must use
an exact commit. Remote MCP discovers and pins the actual publication. Installed,
enabled and load-verified states are separate. Preinstall draft/publication changes
do not update another deployment. Referenced package versions remain after uninstall.

Locked dependency installation supports root `requirements.txt` with exact Python
pins and npm lockfiles. Python uses binary wheels and does not resolve undeclared
transitive dependencies; npm lifecycle scripts are disabled. Unsupported formats
fail explicitly. Local MCP receives its private dependency environment. Skill load
returns the environment required to run its bundled Python scripts; it does not
change the task's system Python packages.

For authenticated resources, set `CAPSTONE_RESOURCE_SECRET_BINDINGS_FILE` to a
protected file inside the existing private policy mount. Its schema is
`capstone-managed-resource-bindings/1`. Each `secret:reference` binds exactly one
workspace, resource ID, source URL and resource kind. Header/environment values
come from separate absolute protected files. Both the configuration and value
files must be owned by the executor UID, have no group/world access, and use no
symlink path components. Never put secret values in resource requests or manifests.
Remote MCP receives selected headers; local MCP receives selected environment
values. Missing or mismatched bindings fail before connection. Rotated bindings
apply to later calls without changing historical receipts.

After publishing a preinstall manifest, an authorized executor operator can export
the exact packages for offline deployment:

```sh
python -m capstone_agent.managed_resource_bundle export /private-output/resources.tar --workspace enterprise
python -m capstone_agent.managed_resource_bundle apply /private-input/resources.tar --workspace enterprise
```

These commands run inside the protected native executor, with its permission
configuration and mounted operator input/output directories. The intranet default
still denies management; an operator must explicitly configure the required grants.
The standalone command does not change the running firewall and does not permit
remote acquisition. Remote MCP still requires live target verification through a
network-enabled runtime. Bundle files contain references, never credential values;
bind credentials separately at the destination. Package ABI compatibility and real
loading are checked again. Existing resource overrides require an explicit JSON
map passed with `--expected-versions`. A partial multi-resource application retains
earlier verified installs and records no successful deployment receipt.
