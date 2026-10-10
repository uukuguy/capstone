#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/bin"
: > "$scratch/local.env"

cat > "$scratch/bin/docker" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$CAPSTONE_TEST_CALLS"
case "$*" in
  *' port api 8766') printf '127.0.0.1:8767\n' ;;
  *' port app 5173') printf '127.0.0.1:5173\n' ;;
  *' ps -q api') printf 'api-container\n' ;;
  *' ps -q worker-pypsa') printf 'worker-pypsa-container\n' ;;
  *' ps -q worker') printf 'worker-container\n' ;;
  'inspect -f {{.Image}} api-container'|'inspect -f {{.Image}} worker-container'|'inspect -f {{.Image}} worker-pypsa-container')
    printf 'sha256:same-image\n' ;;
esac
SH
cat > "$scratch/bin/curl" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$CAPSTONE_TEST_CALLS"
SH
# This is a shell orchestration test. Model digest checks have their own
# Authority tests; do not require a developer's installed model library here.
cat > "$scratch/bin/uv" <<'SH'
#!/usr/bin/env bash
printf 'uv %s\n' "$*" >> "$CAPSTONE_TEST_CALLS"
cat > "$CAPSTONE_TEST_STAGE_SCRIPT"
exit "${CAPSTONE_TEST_STAGE_EXIT:-0}"
SH
chmod +x "$scratch/bin/docker" "$scratch/bin/curl" "$scratch/bin/uv"

export CAPSTONE_TEST_CALLS="$scratch/calls"
export CAPSTONE_TEST_STAGE_SCRIPT="$scratch/stage.py"
export CAPSTONE_LOCAL_ENV_FILE="$scratch/local.env"
PATH="$scratch/bin:$PATH" "$repo_root/deploy/rebuild_local.sh" > "$scratch/output"

grep -Eq -- '--env-file .* config --quiet' "$CAPSTONE_TEST_CALLS"
grep -Eq -- '--env-file .* build api' "$CAPSTONE_TEST_CALLS"
grep -Eq -- '--env-file .* up --no-build --force-recreate --wait -d' "$CAPSTONE_TEST_CALLS"
grep -Eq -- 'http://127.0.0.1:8767/health/ready' "$CAPSTONE_TEST_CALLS"
grep -Eq 'App:.*http://.*:5173/' "$scratch/output"
grep -Eq 'uv run --project .*packages/pypsa-agent python - ' "$CAPSTONE_TEST_CALLS"
grep -Eq 'verified_asset_path\(entry.catalog_id, root=source\)' "$CAPSTONE_TEST_STAGE_SCRIPT"

# A staging failure must stop the rebuild before Compose validates or builds.
: > "$CAPSTONE_TEST_CALLS"
if CAPSTONE_TEST_STAGE_EXIT=1 PATH="$scratch/bin:$PATH" "$repo_root/deploy/rebuild_local.sh" > "$scratch/output" 2>&1; then
  echo 'local rebuild accepted a failed model library check' >&2
  exit 1
fi
grep -Eq 'local PyPSA model library is missing or invalid' "$scratch/output"
if grep -Eq 'config --quiet|build api|up --no-build' "$CAPSTONE_TEST_CALLS"; then
  echo 'local rebuild continued after a failed model library check' >&2
  exit 1
fi

echo 'local-rebuild: ok'
