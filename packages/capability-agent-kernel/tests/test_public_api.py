from __future__ import annotations

from capability_agent import DomainManifest, DomainRuntimeProfile
from capability_agent.application import prepare_domain_runtime
from capability_agent.tools import GuideIndex, ToolCatalog, describe_tool_document


def test_kernel_public_api_is_deliberate() -> None:
    assert DomainManifest.__module__.startswith("capability_agent.")
    assert DomainRuntimeProfile.__module__.startswith("capability_agent.")
    assert prepare_domain_runtime.__module__ == (
        "capability_agent.application.composition"
    )
    assert ToolCatalog.__module__ == "capability_agent.tools.catalog"
    assert GuideIndex.__module__ == "capability_agent.tools.guide"
    assert describe_tool_document.__module__ == "capability_agent.tools.catalog"
