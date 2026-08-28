#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
temporary_root="$(mktemp -d)"

cleanup() {
  rm -rf -- "$temporary_root"
}
trap cleanup EXIT

mkdir -p "$temporary_root/packages"
cp "$repo_root/Makefile" "$temporary_root/Makefile"
for package in pi-capability-tools pi-grid-tools; do
  mkdir -p "$temporary_root/packages/$package"
  cp "$repo_root/packages/$package/package.json" "$temporary_root/packages/$package/package.json"
  cp "$repo_root/packages/$package/package-lock.json" "$temporary_root/packages/$package/package-lock.json"
  cp -R "$repo_root/packages/$package/src" "$temporary_root/packages/$package/src"
done

before_generic="$(shasum -a 256 "$temporary_root/packages/pi-capability-tools/package-lock.json")"
before_grid="$(shasum -a 256 "$temporary_root/packages/pi-grid-tools/package-lock.json")"
make -C "$temporary_root" setup-tools
after_generic="$(shasum -a 256 "$temporary_root/packages/pi-capability-tools/package-lock.json")"
after_grid="$(shasum -a 256 "$temporary_root/packages/pi-grid-tools/package-lock.json")"

test "$before_generic" = "$after_generic"
test "$before_grid" = "$after_grid"
python3 - "$temporary_root/packages/pi-grid-tools" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

package_root = Path(sys.argv[1])
lock = json.loads((package_root / "package-lock.json").read_text(encoding="utf-8"))
locked_packages = lock["packages"]
installed_root = package_root / "node_modules"
checked = 0
for manifest_path in installed_root.rglob("package.json"):
    package_dir = manifest_path.parent
    relative = package_dir.relative_to(package_root).as_posix()
    tail = relative.rsplit("node_modules/", 1)[-1].split("/")
    if len(tail) != (2 if tail[0].startswith("@") else 1):
        continue
    locked = locked_packages.get(relative)
    if not isinstance(locked, dict):
        raise SystemExit(f"installed package is absent from the frozen lock: {relative}")
    installed = json.loads(manifest_path.read_text(encoding="utf-8"))
    if installed.get("version") != locked.get("version"):
        raise SystemExit(
            f"installed package drifted from the frozen lock: {relative}: "
            f"{installed.get('version')} != {locked.get('version')}"
        )
    checked += 1
if checked < 1:
    raise SystemExit("frozen source setup installed no packages")
pi_ai = json.loads(
    (installed_root / "@earendil-works/pi-ai/package.json").read_text(encoding="utf-8")
)
if pi_ai.get("version") != "0.80.6":
    raise SystemExit(f"source setup installed unexpected Pi AI version: {pi_ai.get('version')}")
PY
(
  cd "$temporary_root/packages/pi-grid-tools"
  node --input-type=module -e \
    'import("@capability-agent/pi-tools").then((module) => { if (typeof module.buildCapabilityRequest !== "function") process.exit(1); })'
)

echo "source-setup: ok"
