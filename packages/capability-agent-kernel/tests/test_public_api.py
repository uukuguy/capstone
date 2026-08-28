from __future__ import annotations

import subprocess
import sys

from capability_agent import DomainManifest, DomainRuntimeProfile
from capability_agent.application import prepare_domain_runtime
from capability_agent.tools import GuideIndex, ToolCatalog


def test_kernel_public_api_is_deliberate() -> None:
    assert DomainManifest.__module__.startswith("capability_agent.")
    assert DomainRuntimeProfile.__module__.startswith("capability_agent.")
    assert prepare_domain_runtime.__module__ == (
        "capability_agent.application.composition"
    )
    assert ToolCatalog.__module__ == "capability_agent.tools.catalog"
    assert GuideIndex.__module__ == "capability_agent.tools.guide"


def test_legacy_imports_are_exact_compatibility_aliases() -> None:
    from grid_agent.application.composition import (
        prepare_domain_runtime as LegacyPrepareDomainRuntime,
    )
    from grid_agent.domain import (
        DomainManifest as LegacyDomainManifest,
        DomainRuntimeProfile as LegacyDomainRuntimeProfile,
    )
    from grid_agent.tools.catalog import ToolCatalog as LegacyToolCatalog
    from grid_agent.tools.guide import GuideIndex as LegacyGuideIndex

    assert LegacyDomainManifest is DomainManifest
    assert LegacyDomainRuntimeProfile is DomainRuntimeProfile
    assert LegacyPrepareDomainRuntime is prepare_domain_runtime
    assert LegacyToolCatalog is ToolCatalog
    assert LegacyGuideIndex is GuideIndex


def test_legacy_catalog_loader_keeps_repository_path_compatibility(tmp_path) -> None:
    definitions = (
        tmp_path
        / "packages/grid-simulator/src/grid_simulator/capabilities/definitions"
    )
    definitions.mkdir(parents=True)
    (definitions / "asset.list.json").write_text(
        '{"id":"asset.list"}', encoding="utf-8"
    )

    from grid_agent.tools.catalog import load_packaged_capability_documents

    assert load_packaged_capability_documents(tmp_path) == ({"id": "asset.list"},)


def test_legacy_modules_do_not_mutate_kernel_class_methods() -> None:
    script = """
from capability_agent.application.composition import prepare_domain_runtime
from capability_agent.tools.catalog import ToolCatalog
from capability_agent.tools.guide import GuideIndex

catalog_from_documents = ToolCatalog.from_documents.__func__
catalog_from_environment = ToolCatalog.from_environment.__func__
guide_load = GuideIndex.load.__func__
prepare = prepare_domain_runtime

import grid_agent.application.composition
import grid_agent.tools.catalog
import grid_agent.tools.guide

assert ToolCatalog.from_documents.__func__ is catalog_from_documents
assert ToolCatalog.from_environment.__func__ is catalog_from_environment
assert GuideIndex.load.__func__ is guide_load
assert prepare_domain_runtime is prepare
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
