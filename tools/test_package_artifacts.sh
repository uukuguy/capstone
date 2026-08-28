#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
temporary_root="$(mktemp -d)"
artifact_dir="$temporary_root/artifacts"
venv_dir="$temporary_root/venv"
run_dir="$temporary_root/run"

cleanup() {
  rm -rf -- "$temporary_root"
}
trap cleanup EXIT

mkdir -p "$artifact_dir" "$run_dir"

cd "$repo_root"

python3 tools/check_package_boundaries.py

uv build --project packages/capability-agent-kernel --out-dir "$artifact_dir"
uv build --project packages/grid-simulator --out-dir "$artifact_dir"
uv build --project packages/pandapower-domain-pack --out-dir "$artifact_dir"
uv build --project packages/grid-agent --out-dir "$artifact_dir"
npm pack --prefix packages/pi-capability-tools ./packages/pi-capability-tools --pack-destination "$artifact_dir" >/dev/null
npm pack --prefix packages/pi-grid-tools ./packages/pi-grid-tools --pack-destination "$artifact_dir" >/dev/null

python_wheels=(
  "$artifact_dir"/capability_agent_kernel-*.whl
  "$artifact_dir"/grid_simulator-*.whl
  "$artifact_dir"/pandapower_domain_pack-*.whl
  "$artifact_dir"/grid_agent-*.whl
)

if [ "${#python_wheels[@]}" -ne 4 ]; then
  echo "expected four Python wheels in $artifact_dir" >&2
  exit 1
fi
for wheel in "${python_wheels[@]}"; do
  if [ ! -f "$wheel" ]; then
    echo "missing Python wheel: $wheel" >&2
    exit 1
  fi
done

uv venv "$venv_dir" >/dev/null
uv pip install --python "$venv_dir/bin/python" "${python_wheels[@]}"

smoke_file="$run_dir/installed_smoke.py"
cp packages/grid-agent/tests/contract/installed_smoke.py "$smoke_file"
(
  cd "$run_dir"
  "$venv_dir/bin/python" "$smoke_file"
)

inspect_npm_tarball() {
  local package_glob="$1"
  local tarball_count
  tarball_count="$(find "$artifact_dir" -maxdepth 1 -type f -name "$package_glob" | wc -l | tr -d ' ')"
  if [ "$tarball_count" != "1" ]; then
    echo "expected one npm tarball matching $package_glob in $artifact_dir" >&2
    exit 1
  fi

  local tarball
  tarball="$(find "$artifact_dir" -maxdepth 1 -type f -name "$package_glob" -print -quit)"
  local listing
  listing="$(tar -tf "$tarball")"
  if printf '%s\n' "$listing" | grep -E '(^|/)(node_modules|test|tests|fixtures|__fixtures__|\.git|\.github|\.worktrees|\.superpowers|docs|runs|var|tmp|dist|coverage|\.cache|\.pytest_cache|\.ruff_cache|__pycache__)(/|$)|(^|/)(AGENTS\.md|CLAUDE\.md|Makefile|pyproject\.toml|uv\.lock|\.env($|\.)|.*\.pem$|.*\.key$|.*secret.*|.*token.*|.*\.map$)' >&2; then
    echo "npm tarball contains forbidden package artifact paths: $tarball" >&2
    exit 1
  fi
}

inspect_npm_tarball 'capability-agent-pi-tools-*.tgz'
inspect_npm_tarball 'grid-static-analysis-pi-grid-tools-*.tgz'

echo "package-artifacts: ok"
