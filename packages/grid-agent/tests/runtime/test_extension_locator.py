from __future__ import annotations

import json
from pathlib import Path

import pytest

from grid_agent.runtime.extension import PiExtensionLocator, PiExtensionLocatorError


def test_locator_resolves_verified_source_checkout_extension(tmp_path: Path) -> None:
    extension = _write_package(tmp_path / "packages/pi-grid-tools")

    assert PiExtensionLocator(tmp_path).resolve() == extension


def test_locator_resolves_verified_project_local_installed_extension(
    tmp_path: Path,
) -> None:
    extension = _write_package(
        tmp_path / "node_modules/@grid-static-analysis/pi-grid-tools"
    )

    assert PiExtensionLocator(tmp_path).resolve() == extension


def test_locator_rejects_unverified_fallback_and_environment_paths(
    tmp_path: Path,
) -> None:
    outside = _write_package(tmp_path.parent / "outside-pi-grid-tools")

    with pytest.raises(PiExtensionLocatorError, match="project-local"):
        PiExtensionLocator(
            tmp_path,
            environ={"GRID_AGENT_PI_EXTENSION": str(outside)},
        ).resolve()


def test_locator_rejects_symlinked_package_components(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    _write_package(outside)
    package_parent = tmp_path / "node_modules/@grid-static-analysis"
    package_parent.mkdir(parents=True)
    (package_parent / "pi-grid-tools").symlink_to(outside, target_is_directory=True)

    with pytest.raises(PiExtensionLocatorError, match="project-local"):
        PiExtensionLocator(tmp_path).resolve()


def _write_package(package_root: Path) -> Path:
    source = package_root / "src"
    source.mkdir(parents=True)
    extension = source / "domain-tools.mjs"
    extension.write_text("export default function extension() {}\n", encoding="utf-8")
    (package_root / "package.json").write_text(
        json.dumps(
            {
                "name": "@grid-static-analysis/pi-grid-tools",
                "version": "1.0.1",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return extension
