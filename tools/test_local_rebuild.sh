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
chmod +x "$scratch/bin/docker" "$scratch/bin/curl"

export CAPSTONE_TEST_CALLS="$scratch/calls"
export CAPSTONE_LOCAL_ENV_FILE="$scratch/local.env"
PATH="$scratch/bin:$PATH" "$repo_root/deploy/rebuild_local.sh" > "$scratch/output"

rg -q -- '--env-file .* config --quiet' "$CAPSTONE_TEST_CALLS"
rg -q -- '--env-file .* build api' "$CAPSTONE_TEST_CALLS"
rg -q -- '--env-file .* up --no-build --force-recreate --wait -d' "$CAPSTONE_TEST_CALLS"
rg -q -- 'http://127.0.0.1:8767/health/ready' "$CAPSTONE_TEST_CALLS"
rg -q 'App:.*http://.*:5173/' "$scratch/output"

echo 'local-rebuild: ok'
