from __future__ import annotations

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
