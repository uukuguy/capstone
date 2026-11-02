# Intranet development installation

Use the root `compose.yaml` with `deploy/intranet/compose.yaml`, a private
environment file, and a distinct Compose project (`capstone-intranet`). This is
an internal development installation, not a cloud or user-trial release. It has
its own PostgreSQL, object store, operator/control secrets and runtime volumes.
Do not reuse a gateway database or another Capstone installation's data volumes.

The default profile is selected with `CAPSTONE_WORKBENCH_PRESET=intranet`.
Its model endpoint belongs to `configs/runtime/workbench-llm-profiles.json`.
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
