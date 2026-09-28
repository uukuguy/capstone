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
[ -f "$env_file" ] || fail "missing $env_file; copy deploy/local.env.example and fill local values"

printf '%s\n' "==> Validating local Compose configuration"
"${compose[@]}" config --quiet

build_args=(build api worker objects-init)
if [ "${CAPSTONE_LOCAL_PULL:-0}" = "1" ]; then
  build_args=(build --pull api worker objects-init)
fi
printf '%s\n' "==> Building API and worker from the current checkout"
"${compose[@]}" "${build_args[@]}"

printf '%s\n' "==> Starting dependencies and replacing API/worker containers"
"${compose[@]}" up --no-build --force-recreate --wait -d \
  postgres objects objects-init api worker

api_binding="$("${compose[@]}" port api 8766 | head -n 1)"
[ -n "$api_binding" ] || fail "Compose did not publish the API port"
api_origin="http://${api_binding}"
curl -fsS "$api_origin/health/ready" >/dev/null \
  || fail "API readiness check failed at $api_origin/health/ready"

api_container="$("${compose[@]}" ps -q api)"
worker_container="$("${compose[@]}" ps -q worker)"
[ -n "$api_container" ] && [ -n "$worker_container" ] \
  || fail "API or worker container is not running"
api_image="$(docker inspect -f '{{.Image}}' "$api_container")"
worker_image="$(docker inspect -f '{{.Image}}' "$worker_container")"
[ "$api_image" = "$worker_image" ] \
  || fail "API and worker are running different image revisions"

app_host="${CAPSTONE_APP_HOST:-127.0.0.1}"
app_port="${CAPSTONE_APP_PORT:-5173}"
app_origin="http://${app_host}:${app_port}"
app_state="already running"
if [ "${CAPSTONE_START_APP:-1}" = "1" ]; then
  if ! curl -fsS "$app_origin/" >/dev/null 2>&1; then
    command -v npm >/dev/null 2>&1 || fail "npm is required to start the App"
    app_state="started by rebuild"
    app_state_dir="$repo_root/.capstone-agent"
    mkdir -p "$app_state_dir"
    nohup npm run dev --prefix "$repo_root/packages/capstone-app" -- \
      --host "$app_host" --port "$app_port" \
      >"$app_state_dir/app-dev.log" 2>&1 < /dev/null &
    app_pid=$!
    printf '%s\n' "$app_pid" >"$app_state_dir/app-dev.pid"
    ready=0
    for _ in $(seq 1 30); do
      if curl -fsS "$app_origin/" >/dev/null 2>&1; then
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
