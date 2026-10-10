#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/deploy" "$scratch/source/deploy" "$scratch/bin"
cp "$repo_root/deploy/rebuild_demo_local.sh" "$scratch/deploy/rebuild_demo_local.sh"
printf '# selected source\n' > "$scratch/source/deploy/rebuild_local.sh"
git -C "$scratch/source" init -q
git -C "$scratch/source" add deploy/rebuild_local.sh
git -C "$scratch/source" -c user.name=Test -c user.email=test@example.invalid commit -qm source
cat > "$scratch/bin/make" <<'SH'
#!/usr/bin/env bash
[ "$1" = capstone-local-rebuild ]
[ "$COMPOSE_PROJECT_NAME" = capstone-demo-local ]
[ "$CAPSTONE_API_PORT" = 18767 ]
[ "$CAPSTONE_APP_PORT" = 15173 ]
[ "$CAPSTONE_API_PROXY_TARGET" = http://127.0.0.1:18767 ]
[ "$CAPSTONE_LOCAL_ENV_FILE" = "$CAPSTONE_TEST_ROOT/deploy/demo-local.env" ]
[ "$CAPSTONE_BACKEND_IMAGE" = "capstone-demo-backend:$(git rev-parse HEAD)" ]
SH
chmod +x "$scratch/bin/make"
cat > "$scratch/bin/curl" <<'SH'
#!/usr/bin/env bash
printf '{"revision":"%s","dirty":false}\n' "${CAPSTONE_TEST_APP_REVISION:-$(git -C "$CAPSTONE_DEMO_SOURCE_DIR" rev-parse HEAD)}"
SH
chmod +x "$scratch/bin/curl"
export CAPSTONE_TEST_ROOT="$scratch"
export CAPSTONE_DEMO_SOURCE_DIR="$scratch/source"
PATH="$scratch/bin:$PATH" bash "$scratch/deploy/rebuild_demo_local.sh" > "$scratch/output"
python3 - "$scratch/deploy/demo-local.env" <<'PY'
import os
import stat
import sys
from pathlib import Path
p = Path(sys.argv[1])
assert stat.S_IMODE(p.stat().st_mode) == 0o600
values = dict(line.split('=', 1) for line in p.read_text().splitlines())
assert values['CAPSTONE_ARTIFACT_BUCKET'] == 'capstone-demo-local-private'
assert values['DEEPSEEK_API_KEY'] == ''
assert len(values['CAPSTONE_OPERATOR_TOKEN']) >= 32
assert values['CAPSTONE_OPERATOR_TOKEN'] != values['S3_SECRET_KEY']
PY
before="$(shasum -a 256 "$scratch/deploy/demo-local.env")"
PATH="$scratch/bin:$PATH" bash "$scratch/deploy/rebuild_demo_local.sh" > "$scratch/output"
[ "$before" = "$(shasum -a 256 "$scratch/deploy/demo-local.env")" ]
if CAPSTONE_TEST_APP_REVISION=wrong PATH="$scratch/bin:$PATH" bash "$scratch/deploy/rebuild_demo_local.sh" > "$scratch/output" 2>&1; then
  echo 'local demo accepted an App from another source' >&2
  exit 1
fi
printf '# uncommitted change\n' >> "$scratch/source/deploy/rebuild_local.sh"
if PATH="$scratch/bin:$PATH" bash "$scratch/deploy/rebuild_demo_local.sh" > "$scratch/output" 2>&1; then
  echo 'local demo accepted dirty source' >&2
  exit 1
fi
echo 'demo-local-rebuild: isolation, source identity, protected credentials and retained state pass'
