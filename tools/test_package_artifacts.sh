#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
temporary_root="$(mktemp -d)"
# macOS exposes its temporary directory through /var -> /private/var. The
# runtime intentionally rejects symlink ancestors, so use the physical path.
temporary_root="$(cd "$temporary_root" && pwd -P)"
artifact_dir="$temporary_root/artifacts"
venv_dir="$temporary_root/venv"
run_dir="$temporary_root/run"
grid_pack_dir="$temporary_root/pi-grid-tools-pack"

cleanup() {
  rm -rf -- "$temporary_root"
}
trap cleanup EXIT

mkdir -p "$artifact_dir" "$run_dir" "$grid_pack_dir"

cd "$repo_root"

python3 tools/check_package_boundaries.py
python3 tools/check_protected_paths.py

uv build --project packages/capability-agent-kernel --out-dir "$artifact_dir"
uv build --project packages/grid-simulator --out-dir "$artifact_dir"
uv build --project packages/pandapower-domain-pack --out-dir "$artifact_dir"
uv build --project packages/inventory-reference-service --out-dir "$artifact_dir"
uv build --project packages/inventory-domain-pack --out-dir "$artifact_dir"
uv build --project packages/grid-agent --out-dir "$artifact_dir"
npm pack --prefix packages/pi-capability-tools ./packages/pi-capability-tools --pack-destination "$artifact_dir" >/dev/null
cp packages/pi-grid-tools/package.json "$grid_pack_dir/package.json"
cp -R packages/pi-grid-tools/src "$grid_pack_dir/src"
python3 - "$grid_pack_dir/package.json" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
manifest = json.loads(path.read_text(encoding="utf-8"))
if manifest["dependencies"].get("@capability-agent/pi-tools") != "file:../pi-capability-tools":
    raise SystemExit("source wrapper must use the frozen local owning-package dependency")
manifest["dependencies"]["@capability-agent/pi-tools"] = "0.1.0"
path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
npm pack --prefix "$grid_pack_dir" "$grid_pack_dir" --pack-destination "$artifact_dir" >/dev/null

python_wheels=(
  "$artifact_dir"/capability_agent_kernel-*.whl
  "$artifact_dir"/grid_simulator-*.whl
  "$artifact_dir"/pandapower_domain_pack-*.whl
  "$artifact_dir"/inventory_reference_service-*.whl
  "$artifact_dir"/inventory_domain_pack-*.whl
  "$artifact_dir"/grid_agent-*.whl
)

if [ "${#python_wheels[@]}" -ne 6 ]; then
  echo "expected six Python wheels in $artifact_dir" >&2
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
  TMPDIR="$run_dir" PATH="$venv_dir/bin:$PATH" "$venv_dir/bin/python" "$smoke_file"
)

# Exercise the HTTP experiment against installed wheels while keeping its
# loopback adapter test-only and outside every published package artifact.
cp packages/inventory-domain-pack/tests/http_authority_experiment.py "$run_dir/http_authority_experiment.py"
cat > "$run_dir/http_authority_smoke.py" <<'PY'
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from http_authority_experiment import (
    HttpInventoryArtifactAuthority,
    HttpInventoryProvisioner,
    LoopbackInventoryService,
)
from inventory_domain.profile import build_inventory_profile


with LoopbackInventoryService() as service:
    profile = replace(
        build_inventory_profile(),
        provisioner=HttpInventoryProvisioner(service.origin),
        authority_factory=HttpInventoryArtifactAuthority,
    )
    binding = SimpleNamespace(
        binding_id="inventory",
        credential_scope=SimpleNamespace(
            scope_id="inventory-http",
            credential_names=("INVENTORY_API_TOKEN",),
        ),
    )
    lease = SimpleNamespace(
        scope_id="inventory-http",
        credentials={"INVENTORY_API_TOKEN": service.token},
    )
    workspace = Path("http-authority-workspace")
    endpoint = profile.provisioner.prepare(
        binding=binding, workspace=workspace, credentials=lease,
    )
    opened = endpoint.executor.invoke("catalog.open", {"catalog_id": "warehouse-a"})
    listed = endpoint.executor.invoke("asset.list", {"context_ref": opened["context_ref"]})
    profile.create_authority(workspace).admit(
        "asset.list", listed, tuple(listed["evidence_refs"]),
    )
    endpoint.close()
    assert endpoint.closed and service.page_requests >= 2
print("installed-http-authority-experiment: ok")
PY
(
  cd "$run_dir"
  "$venv_dir/bin/python" "$run_dir/http_authority_smoke.py"
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
  python3 - "$tarball" <<'PY'
from __future__ import annotations

import re
import sys
import tarfile
from pathlib import PurePosixPath

tarball = sys.argv[1]
encoded_separator_pattern = re.compile(r"%(?:2f|5c)", re.IGNORECASE)
deny_components = {
    ".git",
    ".github",
    ".superpowers",
    ".worktrees",
    "__fixtures__",
    "__pycache__",
    "coverage",
    "dist",
    "docs",
    "fixture",
    "fixtures",
    "node_modules",
    "runs",
    "test",
    "tests",
    "tmp",
    "var",
}
repo_root_files = {
    "agents.md",
    "claude.md",
    "makefile",
    "pyproject.toml",
    "uv.lock",
}
sensitive_terms = ("secret", "token", "credential")


def reject(member_name: str, reason: str) -> None:
    raise SystemExit(
        f"npm tarball contains forbidden package artifact path "
        f"({reason}): {member_name}"
    )


def check_member(member_name: str) -> None:
    if member_name == "":
        reject(member_name, "empty member name")
    if member_name.startswith(("/", "\\")):
        reject(member_name, "absolute path")
    if "\\" in member_name:
        reject(member_name, "backslash separator")
    if encoded_separator_pattern.search(member_name):
        reject(member_name, "encoded separator")

    parts = member_name.split("/")
    lowered_parts = [part.lower() for part in parts]
    if any(part in ("", ".", "..") for part in lowered_parts):
        reject(member_name, "unsafe path segment")

    lowered_name = "/".join(lowered_parts)
    basename = PurePosixPath(lowered_name).name
    if any(term in lowered_name for term in sensitive_terms):
        reject(member_name, "sensitive term")
    if any("cache" in part for part in lowered_parts):
        reject(member_name, "cache component")
    if any(part in deny_components for part in lowered_parts):
        reject(member_name, "denylisted component")
    if basename in repo_root_files:
        reject(member_name, "repository root file")
    if basename.endswith((".pem", ".key", ".map")):
        reject(member_name, "forbidden suffix")
    if ".test." in basename or ".spec." in basename:
        reject(member_name, "test/spec suffix")
    if basename == ".env" or basename.startswith(".env."):
        reject(member_name, "environment file")


try:
    with tarfile.open(tarball, "r:*") as archive:
        for member in archive:
            check_member(member.name)
except tarfile.TarError as exc:
    raise SystemExit(f"could not read npm tarball {tarball}: {exc}") from exc
PY
}

self_test_npm_tarball_inspector() {
  local fixture_dir="$temporary_root/npm-tarball-negative-fixtures"
  mkdir -p "$fixture_dir"
  python3 - "$fixture_dir" <<'PY'
from __future__ import annotations

import io
import sys
import tarfile
from pathlib import Path

fixture_dir = Path(sys.argv[1])
for index, member_name in enumerate(
    (
        "package/src/Foo.MAP",
        "package/src/.ENV",
        "package/src/unit.test.mjs",
        "package/../escape",
        "package/src\\evil.mjs",
        "package/src/foo%2fbar.mjs",
        "package/src/foo%5cbar.mjs",
    ),
    start=1,
):
    path = fixture_dir / f"artifact-boundary-negative-{index}.tgz"
    with tarfile.open(path, "w:gz") as archive:
        payload = b"fixture"
        info = tarfile.TarInfo(member_name)
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
PY

  local fixture
  for fixture in "$fixture_dir"/artifact-boundary-negative-*.tgz; do
    local pattern
    pattern="$(basename "$fixture")"
    cp "$fixture" "$artifact_dir/$pattern"
    if (inspect_npm_tarball "$pattern") >/dev/null 2>&1; then
      echo "npm tarball boundary self-test expected rejection: $pattern" >&2
      exit 1
    fi
  done
  echo "npm-tarball-boundary-selftest: ok"
}

self_test_npm_tarball_inspector
inspect_npm_tarball 'capability-agent-pi-tools-*.tgz'
inspect_npm_tarball 'grid-static-analysis-pi-grid-tools-*.tgz'

npm_install_dir="$run_dir"
mkdir -p "$npm_install_dir"
(
  cd "$npm_install_dir"
  npm init -y >/dev/null
  npm install "$artifact_dir"/capability-agent-pi-tools-*.tgz "$artifact_dir"/grid-static-analysis-pi-grid-tools-*.tgz >/dev/null
  npm ls @capability-agent/pi-tools @grid-static-analysis/pi-grid-tools --json >/dev/null
  node --input-type=module <<'EOF'
import {
  buildCapabilityRequest,
  createDomainToolsExtension,
} from "@capability-agent/pi-tools";
import gridTools, {
  buildGridRequest,
} from "@grid-static-analysis/pi-grid-tools";
import {
  configureModelRequestCapture as configureCapabilityCapture,
} from "@capability-agent/pi-tools/model-request-capture";
import {
  configureModelRequestCapture as configureGridCapture,
} from "@grid-static-analysis/pi-grid-tools/model-request-capture";

if (typeof buildCapabilityRequest !== "function") {
  throw new Error("@capability-agent/pi-tools named export is missing");
}
if (typeof createDomainToolsExtension !== "function") {
  throw new Error("@capability-agent/pi-tools extension export is missing");
}
if (typeof gridTools !== "function") {
  throw new Error("@grid-static-analysis/pi-grid-tools default export is not callable");
}
if (typeof buildGridRequest !== "function") {
  throw new Error("@grid-static-analysis/pi-grid-tools named export is missing");
}
if (typeof configureCapabilityCapture !== "function") {
  throw new Error("@capability-agent/pi-tools model capture export is missing");
}
if (typeof configureGridCapture !== "function") {
  throw new Error("@grid-static-analysis/pi-grid-tools model capture export is missing");
}
EOF
  echo "npm-install-smoke: ok"
)

(
  cd "$run_dir"
  PATH="$venv_dir/bin:$PATH" "$venv_dir/bin/grid-agent" doctor --json > doctor.json
  "$venv_dir/bin/python" - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("doctor.json").read_text(encoding="utf-8"))
extension = Path(payload["pi_extension"])
expected_root = Path.cwd() / "node_modules/@grid-static-analysis/pi-grid-tools"
assert extension.is_relative_to(expected_root), payload
assert extension.name == "domain-tools.mjs"
PY
  PATH="$venv_dir/bin:$PATH" "$venv_dir/bin/grid-agent" run \
    --offline --question-id installed-offline-envelope \
    "母线电压正常运行范围是多少?" > offline-envelope.json
  "$venv_dir/bin/python" - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("offline-envelope.json").read_text(encoding="utf-8"))
assert set(payload) == {"question_id", "answer_output"}, payload
assert payload["question_id"] == "installed-offline-envelope", payload
PY
  node --input-type=module <<'EOF'
import { mkdir, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { join } from "node:path";
import extension from "@grid-static-analysis/pi-grid-tools";

const workspace = join(process.cwd(), "installed-extension-run");
const guides = join(workspace, "guides");
await mkdir(join(workspace, "pi"), { recursive: true });
await mkdir(guides, { recursive: true });
await writeFile(
  join(workspace, "tool-catalog.json"),
  JSON.stringify({ tools: [{
    name: "grid_environment_describe",
    capability: "environment.describe",
    description: "Describe installed runtime",
    input_schema: { type: "object", additionalProperties: false, properties: {} },
  }] }),
  "utf8",
);
await writeFile(join(guides, "overview.md"), "# Installed guide\n", "utf8");
const guideIndex = JSON.stringify({
  protocol: "grid-guide-index",
  version: "1.0",
  root: guides,
  resources: { overview: join(guides, "overview.md") },
});
await writeFile(join(workspace, "guide-index.json"), guideIndex, "utf8");
const descriptorPath = join(workspace, "pi/domain-runtime.json");
await writeFile(
  descriptorPath,
  JSON.stringify({
    protocol: "grid-capability",
    protocol_version: "1.0",
    executable: "gridctl",
    executable_args: ["request", "--workspace", workspace],
    tool_name_prefix: "grid_",
    guide_tool_name: "grid_guide_open",
    context_tool_name: "grid_analysis_context_get",
    decision_tool_name: "grid_record_decision",
    tool_catalog_path: join(workspace, "tool-catalog.json"),
    guide_index_path: join(workspace, "guide-index.json"),
    guide_root_path: guides,
    guide_index_sha256: createHash("sha256").update(guideIndex).digest("hex"),
    workspace_path: workspace,
  }),
  "utf8",
);
process.env.CAPABILITY_AGENT_RUNTIME_DESCRIPTOR = descriptorPath;
const registered = [];
extension({ registerTool: (tool) => registered.push(tool) });
const names = registered.map((tool) => tool.name).sort();
if (JSON.stringify(names) !== JSON.stringify(["grid_environment_describe", "grid_guide_open"])) {
  throw new Error(`installed extension registration mismatch: ${JSON.stringify(names)}`);
}
EOF
  echo "installed-grid-agent-smoke: ok"
)

echo "package-artifacts: ok"
