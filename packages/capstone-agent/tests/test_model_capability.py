from __future__ import annotations

import pytest

from capstone_agent.model_capability import (
    CapstoneModelCapabilityCatalog,
    ModelCapabilityProfileInfo,
)
from capstone_agent.thread_service import ThreadModelDescriptor
from capstone_model_capability_spi import (
    ModelCapabilityDescriptor,
    ModelCapabilityRegistry,
    ModelCapabilitySelection,
)


class _Handle:
    def __init__(self, descriptor: ModelCapabilityDescriptor) -> None:
        self.descriptor = descriptor

    def close(self) -> None:
        return None


def _catalog() -> CapstoneModelCapabilityCatalog:
    registry = ModelCapabilityRegistry()
    catalog = CapstoneModelCapabilityCatalog(registry)
    for profile_id, family in (("static-analysis", "pandapower"), ("operations", "pypsa")):
        descriptor = ModelCapabilityDescriptor(profile_id, "1.0.0")
        catalog.register_profile(
            ModelCapabilityProfileInfo(
                descriptor=descriptor, display_name=profile_id.title(),
                implementation_families=(family,),
            ),
            lambda descriptor=descriptor: _Handle(descriptor),
        )
    return catalog


def _model(
    model_id="ieee39", revision="revision:sha256:" + "a" * 64, family="pandapower",
):
    return ThreadModelDescriptor(model_id, revision, family)


def test_catalog_resolves_model_revision_then_family_then_empty() -> None:
    catalog = _catalog()
    static = ("static-analysis", "1.0.0")
    catalog.set_family_default("pandapower", ModelCapabilitySelection((static,)))

    assert catalog.resolve(_model()).enabled_profiles == (static,)
    model_specific = ModelCapabilitySelection.empty()
    catalog.set_model_default("ieee39", _model().model_revision, model_specific)
    assert catalog.resolve(_model()) == model_specific
    assert catalog.resolve(_model("other39")) == ModelCapabilitySelection((static,))
    assert catalog.resolve(_model(family="unknown")) == ModelCapabilitySelection.empty()


def test_explicit_selection_is_exact_and_family_checked_without_conflict_detection() -> None:
    catalog = _catalog()
    selection = ModelCapabilitySelection((("static-analysis", "1.0.0"),))
    assert catalog.resolve(_model(), selection) == selection
    with pytest.raises(ValueError, match="implementation family"):
        catalog.resolve(_model(), ModelCapabilitySelection((("operations", "1.0.0"),)))


def test_catalog_rejects_unknown_defaults_and_duplicate_profile_metadata() -> None:
    catalog = _catalog()
    with pytest.raises(KeyError):
        catalog.set_family_default("pandapower", ModelCapabilitySelection((("missing", "1.0.0"),)))
    with pytest.raises(ValueError, match="duplicate"):
        catalog.register_profile(
            ModelCapabilityProfileInfo(
                descriptor=ModelCapabilityDescriptor("static-analysis", "1.0.0"),
                display_name="Duplicate", implementation_families=("pandapower",),
            ),
            lambda: _Handle(ModelCapabilityDescriptor("static-analysis", "1.0.0")),
        )


def test_catalog_lists_only_profiles_compatible_with_the_model_family() -> None:
    catalog = _catalog()
    assert [item.descriptor.profile_id for item in catalog.profiles_for_family("pandapower")] == [
        "static-analysis",
    ]
