from __future__ import annotations

import subprocess
import sys

from capability_agent import DomainManifest, DomainRuntimeProfile
from capability_agent.application import prepare_domain_runtime
from capability_agent.tools import GuideIndex, ToolCatalog


def test_application_uses_kernel_contracts() -> None:
    from pandapower_application.composition import (
        prepare_domain_runtime as legacy_prepare_domain_runtime,
    )
    from capability_agent.domain import (
        DomainManifest as LegacyDomainManifest,
        DomainRuntimeProfile as LegacyDomainRuntimeProfile,
    )
    from capability_agent.tools.catalog import ToolCatalog as LegacyToolCatalog
    from capability_agent.tools.guide import GuideIndex as LegacyGuideIndex

    assert LegacyDomainManifest is DomainManifest
    assert LegacyDomainRuntimeProfile is DomainRuntimeProfile
    assert legacy_prepare_domain_runtime is prepare_domain_runtime
    assert LegacyToolCatalog is ToolCatalog
    assert LegacyGuideIndex is GuideIndex


def test_catalog_uses_installed_domain_resources(
    tmp_path, capability_documents: tuple[dict[str, object], ...]
) -> None:
    from pandapower_domain.capabilities import FilesystemCapabilityContractSource
    from pandapower_domain.resources import PandapowerResourceSet

    fake_root = tmp_path / "not-a-repository"
    fake_root.mkdir()
    documents = FilesystemCapabilityContractSource(PandapowerResourceSet.load()).load()

    assert {document["id"] for document in documents} == {
        document["id"] for document in capability_documents
    }
    assert {document["id"] for document in documents} >= {
        "environment.describe",
        "analysis.run",
        "context.open",
    }


def test_application_imports_do_not_mutate_kernel_class_methods() -> None:
    script = """
from capability_agent.application.composition import prepare_domain_runtime
from capability_agent.tools.catalog import ToolCatalog
from capability_agent.tools.guide import GuideIndex

catalog_from_documents = ToolCatalog.from_documents.__func__
catalog_from_environment = ToolCatalog.from_environment.__func__
guide_load = GuideIndex.load.__func__
prepare = prepare_domain_runtime

import pandapower_application.composition
import capability_agent.tools.catalog
import capability_agent.tools.guide

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
