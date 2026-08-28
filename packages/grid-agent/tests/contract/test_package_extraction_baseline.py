def test_extracted_package_owner_imports_are_available() -> None:
    from capability_agent.application import prepare_domain_runtime
    from pandapower_domain import build_pandapower_profile

    assert prepare_domain_runtime.__name__ == "prepare_domain_runtime"
    assert build_pandapower_profile.__name__ == "build_pandapower_profile"


def test_legacy_public_imports_are_preserved() -> None:
    from grid_agent.application.composition import prepare_domain_runtime
    from grid_agent.domain import DomainManifest
    from grid_agent.domains import build_pandapower_profile
    from grid_agent.tools.catalog import ToolCatalog

    assert prepare_domain_runtime.__name__ == "prepare_domain_runtime"
    assert DomainManifest.__name__ == "DomainManifest"
    assert build_pandapower_profile.__name__ == "build_pandapower_profile"
    assert ToolCatalog.__name__ == "ToolCatalog"
