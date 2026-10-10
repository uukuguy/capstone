#!/usr/bin/env bash
set -Eeuo pipefail

# Run the selected clean demo checkout with separate local data and ports.
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="${CAPSTONE_DEMO_SOURCE_DIR:-$repo_root/.worktrees/demo-n1-repair}"
env_file="$repo_root/deploy/demo-local.env"
[ -f "$source_dir/deploy/rebuild_local.sh" ] || { echo 'local demo: selected source is missing' >&2; exit 1; }
source_revision="$(git -C "$source_dir" rev-parse HEAD)"
[ -z "$(git -C "$source_dir" status --porcelain --untracked-files=normal -- packages configs deploy Dockerfile compose.yaml)" ] \
  || { echo 'local demo: commit or restore selected source changes first' >&2; exit 1; }

if [ ! -f "$env_file" ]; then
  python3 - "$env_file" <<'PY'
import os
import secrets
import sys

values = {
    'POSTGRES_PASSWORD': secrets.token_hex(24),
    'S3_ACCESS_KEY': secrets.token_hex(16),
    'S3_SECRET_KEY': secrets.token_hex(32),
    'CAPSTONE_OPERATOR_TOKEN': secrets.token_hex(32),
    'CAPSTONE_GENERAL_CONTROL_TOKEN': secrets.token_hex(32),
    'CAPSTONE_PUBLIC_DEMO': 'true',
    'CAPSTONE_THREAD_OPEN_ACCESS': 'true',
    'CAPSTONE_HOSTED_APPLICATION': 'capstone',
    'CAPSTONE_PUBLIC_PROVIDER': 'deepseek',
    'CAPSTONE_PUBLIC_MODEL': 'deepseek-flash',
    'DEEPSEEK_API_KEY': '',
    'CAPSTONE_ARTIFACT_BUCKET': 'capstone-demo-local-private',
    'CAPSTONE_DEPLOYMENT_STAGE': 'local',
}
fd = os.open(sys.argv[1], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as output:
    output.write('\n'.join(f'{key}={value}' for key, value in values.items()) + '\n')
PY
  echo 'local demo: created protected deploy/demo-local.env; set its Provider key for interactive questions'
fi

export COMPOSE_PROJECT_NAME=capstone-demo-local
export CAPSTONE_BACKEND_IMAGE="capstone-demo-backend:${source_revision}"
export CAPSTONE_LOCAL_ENV_FILE="$env_file"
export CAPSTONE_API_PORT=18767
export CAPSTONE_APP_PORT=15173
export CAPSTONE_API_PROXY_TARGET=http://127.0.0.1:18767
export CAPSTONE_API_PROXY_ORIGIN=http://127.0.0.1:5173
echo "local demo source: $source_revision"
(cd "$source_dir" && make capstone-local-rebuild)
curl -fsS http://127.0.0.1:15173/__capstone-build | python3 -c '
import json, sys
build = json.load(sys.stdin)
if build.get("revision") != sys.argv[1] or build.get("dirty"):
    raise SystemExit("local demo: App source differs from the selected clean checkout")
' "$source_revision"
echo 'local demo: App and selected source identity match'
