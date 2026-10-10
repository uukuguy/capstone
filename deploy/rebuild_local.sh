#!/usr/bin/env bash
set -Eeuo pipefail

# Rebuild and redeploy the local API/worker pair from the current checkout.
# Keep this as the single local Compose entry point so an old image cannot be
# reused accidentally after source changes.

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="$repo_root/compose.yaml"
env_file="${CAPSTONE_LOCAL_ENV_FILE:-$repo_root/deploy/local.env}"
compose=(docker compose --env-file "$env_file" -f "$compose_file")

fail() {
  printf 'local rebuild failed: %s\n' "$1" >&2
  exit 1
}

command -v docker >/dev/null 2>&1 || fail "docker is not installed or not on PATH"
docker compose version >/dev/null 2>&1 || fail "Docker Compose is not available"
command -v curl >/dev/null 2>&1 || fail "curl is not installed or not on PATH"
command -v uv >/dev/null 2>&1 || fail "uv is not installed or not on PATH"
[ -f "$env_file" ] || fail "missing $env_file; copy deploy/local.env.example and fill local values"

model_source="${CAPSTONE_PYPSA_MODEL_LIBRARY_DIR:-$repo_root/.grid-agent/runtime/pypsa-models}"
model_stage="$repo_root/deploy/local-model-assets"
printf '%s\n' "==> Verifying and staging the local PyPSA model library"
if ! CAPSTONE_PYPSA_MODEL_LIBRARY_DIR="$model_source" uv run --project "$repo_root/packages/pypsa-agent" \
  python - "$model_source" "$model_stage" <<'PY'
from pathlib import Path
import shutil
import sys

from pypsa_model_authority.model_library import list_official_examples, verified_asset_path

source = Path(sys.argv[1])
stage = Path(sys.argv[2])
stage.mkdir(parents=True, exist_ok=True)
for entry in list_official_examples():
    source_path = verified_asset_path(entry.catalog_id, root=source)
    shutil.copy2(source_path, stage / source_path.name)
PY
then
  fail "local PyPSA model library is missing or invalid at $model_source; run make install-pypsa-models"
fi

printf '%s\n' "==> Validating local Compose configuration"
"${compose[@]}" config --quiet

build_args=(build api worker worker-pypsa objects-init)
if [ "${CAPSTONE_LOCAL_PULL:-0}" = "1" ]; then
  build_args=(build --pull api worker worker-pypsa objects-init)
fi
printf '%s\n' "==> Building API and worker from the current checkout"
"${compose[@]}" "${build_args[@]}"
"${compose[@]}" build general-pi

printf '%s\n' "==> Starting dependencies and replacing API/worker containers"
"${compose[@]}" up --no-build --force-recreate --wait -d \
  postgres objects objects-init general-pi api worker worker-pypsa

api_binding="$("${compose[@]}" port api 8766 | head -n 1)"
[ -n "$api_binding" ] || fail "Compose did not publish the API port"
api_origin="http://${api_binding}"
curl -fsS "$api_origin/health/ready" >/dev/null \
  || fail "API readiness check failed at $api_origin/health/ready"

api_container="$("${compose[@]}" ps -q api)"
worker_container="$("${compose[@]}" ps -q worker)"
worker_pypsa_container="$("${compose[@]}" ps -q worker-pypsa)"
[ -n "$api_container" ] && [ -n "$worker_container" ] && [ -n "$worker_pypsa_container" ] \
  || fail "API or worker container is not running"
api_image="$(docker inspect -f '{{.Image}}' "$api_container")"
worker_image="$(docker inspect -f '{{.Image}}' "$worker_container")"
worker_pypsa_image="$(docker inspect -f '{{.Image}}' "$worker_pypsa_container")"
[ "$api_image" = "$worker_image" ] && [ "$api_image" = "$worker_pypsa_image" ] \
  || fail "API and workers are running different image revisions"

app_host="${CAPSTONE_APP_HOST:-0.0.0.0}"
app_port="${CAPSTONE_APP_PORT:-5173}"
app_probe_origin="http://127.0.0.1:${app_port}"
app_public_host="${CAPSTONE_APP_PUBLIC_HOST:-}"
if [ -z "$app_public_host" ]; then
  if [ "$app_host" = "0.0.0.0" ]; then
    if command -v ipconfig >/dev/null 2>&1; then
      for interface in en0 en1; do
        app_public_host="$(ipconfig getifaddr "$interface" 2>/dev/null || true)"
        [ -n "$app_public_host" ] && break
      done
    elif command -v hostname >/dev/null 2>&1; then
      app_public_host="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
    fi
  else
    app_public_host="$app_host"
  fi
fi
app_public_host="${app_public_host:-127.0.0.1}"
app_origin="http://${app_public_host}:${app_port}"
app_state="already running"
if [ "${CAPSTONE_START_APP:-1}" = "1" ]; then
  if ! curl -fsS "$app_probe_origin/" >/dev/null 2>&1; then
    command -v npm >/dev/null 2>&1 || fail "npm is required to start the App"
    app_state="started by rebuild"
    app_state_dir="$repo_root/.capstone-agent"
    mkdir -p "$app_state_dir"
    app_command=(npm run dev --prefix "$repo_root/packages/capstone-app" --
      --host "$app_host" --port "$app_port")
    command -v python3 >/dev/null 2>&1 || fail "python3 is required to detach the App process"
    python3 - "$app_state_dir/app-dev.pid" "$app_state_dir/app-dev.log" "$repo_root" -- \
      "${app_command[@]}" <<'PY'
import os
import sys

pid_path, log_path, working_dir = sys.argv[1:4]
command = sys.argv[5:]
if not command:
    raise SystemExit("missing detached App command")

first_child = os.fork()
if first_child:
    _, status = os.waitpid(first_child, 0)
    raise SystemExit(os.waitstatus_to_exitcode(status))

os.setsid()
second_child = os.fork()
if second_child:
    with open(pid_path, "w", encoding="ascii") as handle:
        handle.write(f"{second_child}\n")
    os._exit(0)

os.chdir(working_dir)
log_fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
os.dup2(log_fd, 1)
os.dup2(log_fd, 2)
null_fd = os.open(os.devnull, os.O_RDONLY)
os.dup2(null_fd, 0)
os.close(log_fd)
os.close(null_fd)
os.execvp(command[0], command)
PY
    app_pid="$(cat "$app_state_dir/app-dev.pid")"
    [ -n "$app_pid" ] || fail "detached App process did not report a PID"
    ready=0
    for _ in $(seq 1 30); do
      if curl -fsS "$app_probe_origin/" >/dev/null 2>&1; then
        ready=1
        break
      fi
      sleep 1
    done
    [ "$ready" = "1" ] || fail "App did not become ready; see $app_state_dir/app-dev.log"
  fi
fi

printf '%s\n' "==> Local deployment is ready"
printf '    API:    %s\n' "$api_origin"
printf '    App:    %s/ (%s)\n' "$app_origin" "$app_state"
printf '    Image:  %s\n' "$api_image"
printf '%s\n' "    Foreground App alternative: make capstone-app-dev"
