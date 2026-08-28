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
(
  cd "$temporary_root/packages/pi-grid-tools"
  node --input-type=module -e \
    'import("@capability-agent/pi-tools").then((module) => { if (typeof module.buildCapabilityRequest !== "function") process.exit(1); })'
)

echo "source-setup: ok"
