#!/bin/sh
# Human deployment entry. Credentials are consumed by Compose, never by eval.
set -eu
umask 077
base=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
instance=${CAPSTONE_INSTANCE:-capstone-user-local-dev}
case "$instance" in
  capstone-user-*) ;;
  *) printf '%s\n' 'CAPSTONE_INSTANCE must start with capstone-user- to isolate trial data.' >&2; exit 1 ;;
esac
state="$base/.capstone-trial/$instance"
case "$instance" in
  ''|*[!a-z0-9_-]*) printf '%s\n' 'Use a lower-case CAPSTONE_INSTANCE name.' >&2; exit 1 ;;
esac
command -v docker >/dev/null 2>&1 || { printf '%s\n' 'Docker is required.' >&2; exit 1; }
docker compose version >/dev/null 2>&1 || { printf '%s\n' 'Docker Compose is required.' >&2; exit 1; }
for file in release.env manifest.json compose.yaml; do
  [ -f "$base/$file" ] || { printf '%s\n' 'This deployment package is incomplete.' >&2; exit 1; }
done
[ ! -L "$base/.capstone-trial" ] && [ ! -L "$state" ] || { printf '%s\n' 'Local state must not be a symlink.' >&2; exit 1; }
mkdir -p "$state"
for file in internal.env installation.json last-operation.log config-check.log; do
  [ ! -L "$state/$file" ] || { printf '%s\n' 'Local state files must not be symlinks.' >&2; exit 1; }
done
if [ ! -f "$base/.env" ]; then cp "$base/.env.example" "$base/.env"; fi
image=$(sed -n 's/^CAPSTONE_BACKEND_IMAGE=//p' "$base/release.env")
platform=$(sed -n 's/^CAPSTONE_TRIAL_PLATFORM=//p' "$base/release.env")
case "$platform" in ''|linux/amd64|linux/arm64) ;; *) printf '%s\n' 'Unsupported trial platform.' >&2; exit 1 ;; esac
case "$image" in
  sha256:*)
    channel=$(sed -n 's/.*"channel"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$base/manifest.json")
    [ "$channel" = dev-trial-offline ] && [ "$platform" = linux/amd64 ] || { printf '%s\n' 'Local image IDs require an offline AMD64 manifest.' >&2; exit 1; }
    for kind in BACKEND APP POSTGRES OBJECTS; do
      ref=$(sed -n "s/^CAPSTONE_${kind}_IMAGE=//p" "$base/release.env")
      tail=${ref#sha256:}
      case "$tail" in *[!0-9a-f]*|'') printf '%s\n' 'Offline image ID is invalid.' >&2; exit 1;; esac
      [ "$ref" = "sha256:$tail" ] && [ "${#tail}" -eq 64 ] || exit 1
      actual=$(docker image inspect --format '{{.Id}}' "$ref")
      [ "$actual" = "$ref" ] || { printf '%s\n' 'Offline image ID differs.' >&2; exit 1; }
      actual=$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$ref")
      [ "$actual" = linux/amd64 ] || { printf '%s\n' 'Offline image platform differs.' >&2; exit 1; }
    done ;;
  registry.cn-beijing.aliyuncs.com/uukuguy/*@sha256:*|ghcr.io/uukuguy/*@sha256:*) ;;
  capstone-trial-backend*:*)
    [ "${CAPSTONE_CANDIDATE_VALIDATION:-0}" = 1 ] || { printf '%s\n' 'Candidate images require operator validation mode.' >&2; exit 1; } ;;
  *) printf '%s\n' 'Release backend image must have a recorded registry digest.' >&2; exit 1 ;;
esac
operation=${1:-up}
case "$operation" in up|status|logs|stop) ;; *) printf '%s\n' 'Use up, status, logs or stop.' >&2; exit 1 ;; esac
# Internal service credentials belong to this instance, not another shell session.
unset POSTGRES_PASSWORD S3_ACCESS_KEY S3_SECRET_KEY CAPSTONE_OPERATOR_TOKEN
unset CAPSTONE_BACKEND_IMAGE CAPSTONE_APP_IMAGE CAPSTONE_POSTGRES_IMAGE CAPSTONE_OBJECTS_IMAGE CAPSTONE_TRIAL_PLATFORM

run_private() {
  if ! "$@" >"$state/last-operation.log" 2>&1; then
    printf '%s\n' "Trial operation failed. Details are in .capstone-trial/$instance/last-operation.log." >&2
    return 1
  fi
}
docker_run() {
  if [ -n "$platform" ]; then docker run --platform "$platform" --pull never "$@"; else docker run --pull never "$@"; fi
}
helper() {
  docker_run --network none --rm --user "$(id -u):$(id -g)" \
    -e CAPSTONE_CANDIDATE_VALIDATION="${CAPSTONE_CANDIDATE_VALIDATION:-0}" \
    -e CAPSTONE_INSTANCE="$instance" \
    -v "$state:/state" -v "$base/manifest.json:/bundle/manifest.json:ro" \
    --entrypoint /app/packages/capstone-agent/.venv/bin/python "$image" \
    /app/deploy/dev_trial_runtime.py "$@"
}
compose() {
  docker compose --project-name "$instance" \
    --env-file "$base/.env" --env-file "$base/release.env" --env-file "$state/internal.env" \
    -f "$base/compose.yaml" "$@"
}

if [ "$operation" = up ]; then
  if grep -q '"offline_image_identities"' "$base/manifest.json"; then
    run_private helper verify
  fi
  if [ -f "$state/installation.json" ] && [ ! -f "$state/internal.env" ]; then
    printf '%s\n' 'Restore this instance private configuration before restarting existing data.' >&2
    exit 1
  fi
  if [ ! -f "$state/installation.json" ]; then
    existing=$(docker ps -a --filter "label=com.docker.compose.project=$instance" --format '{{.ID}}')
    volumes=$(docker volume ls --filter "label=com.docker.compose.project=$instance" --format '{{.Name}}')
    if [ -n "$existing$volumes" ]; then
      printf '%s\n' 'An existing trial instance requires its original deployment directory.' >&2
      exit 1
    fi
  fi
  run_private helper init
  run_private compose config --quiet
  if ! compose run --pull never --rm --no-deps config-check >"$state/config-check.log" 2>&1; then
    printf '%s\n' 'LLM or image configuration is invalid. Check the selected Provider/model and its startup Key.' >&2
    exit 1
  fi
  run_private helper record
  run_private compose up --pull never --wait --wait-timeout 240 -d
  backend_id=''
  for service in api worker worker-pypsa; do
    container=$(compose ps -q "$service")
    current=$(docker inspect --format '{{.Image}}' "$container")
    if [ -z "$backend_id" ]; then backend_id=$current; fi
    [ "$current" = "$backend_id" ] || { printf '%s\n' 'API and workers must use the same exact image.' >&2; exit 1; }
  done
  for service in api worker worker-pypsa app postgres objects; do
    container=$(compose ps -q "$service")
    current=$(docker inspect --format '{{.Image}}' "$container")
    architecture=$(docker image inspect --format '{{.Architecture}}' "$current")
    [ -z "$platform" ] || [ "$platform" = "linux/$architecture" ] || { printf '%s\n' 'Running image platform differs from the candidate manifest.' >&2; exit 1; }
  done
  run_private compose run --pull never --rm --no-deps --entrypoint /app/packages/capstone-agent/.venv/bin/python \
    config-check /app/deploy/dev_trial_runtime.py ready
  printf '%s\n' 'Local-dev trial is ready. Inspect the App port in .env, then open http://127.0.0.1:<port>/.'
  compose ps
elif [ -f "$state/internal.env" ]; then
  run_private helper record
  case "$operation" in
    status) compose ps ;;
    logs) compose logs --tail 100 ;;
    stop) compose stop ;;
  esac
else
  printf '%s\n' 'This trial instance has not been initialized.' >&2
  exit 1
fi
