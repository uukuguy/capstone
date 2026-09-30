from __future__ import annotations

import pytest

from capstone_model_capability_spi import (
    ModelCapabilityDescriptor,
    ModelCapabilityProfileHandle,
    ModelCapabilityRegistry,
    ModelCapabilitySelection,
)


class _Handle:
    def __init__(self, descriptor: ModelCapabilityDescriptor) -> None:
        self.descriptor = descriptor
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _descriptor(profile_id: str = "static-analysis", version: str = "1.0.0"):
    return ModelCapabilityDescriptor(profile_id, version)


def test_descriptor_is_small_exact_and_immutable() -> None:
    descriptor = _descriptor()
    assert descriptor.to_document() == {
        "profile_id": "static-analysis",
        "profile_version": "1.0.0",
        "spi_version": "1",
    }
    assert descriptor.reference == ("static-analysis", "1.0.0")
    with pytest.raises(AttributeError):
        descriptor.profile_id = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    "values",
    [
        ("", "1.0.0", "1"),
        ("bad profile", "1.0.0", "1"),
        ("profile", "", "1"),
        ("profile", "1.0.0", "2"),
    ],
)
def test_descriptor_rejects_invalid_identity_or_spi(values: tuple[str, str, str]) -> None:
    with pytest.raises(ValueError):
        ModelCapabilityDescriptor(*values)


def test_selection_preserves_exact_refs_and_allows_empty() -> None:
    selection = ModelCapabilitySelection((
        ("operations", "2.0.0"), ("modeling", "1.0.0"),
    ))
    assert selection.to_document() == {
        "schema": "capstone-model-capability-selection/1",
        "enabled_profiles": [
            {"profile_id": "operations", "profile_version": "2.0.0"},
            {"profile_id": "modeling", "profile_version": "1.0.0"},
        ],
    }
    assert ModelCapabilitySelection.empty().enabled_profiles == ()


def test_selection_rejects_duplicate_or_malformed_refs() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        ModelCapabilitySelection((("operations", "1.0.0"), ("operations", "1.0.0")))
    with pytest.raises(ValueError):
        ModelCapabilitySelection((("operations", "1.0.0", "extra"),))  # type: ignore[arg-type]


def test_registry_requires_exact_resolution_and_seals_bootstrap() -> None:
    registry = ModelCapabilityRegistry()
    descriptor = _descriptor()
    registry.register(descriptor, lambda: _Handle(descriptor), trust_source="test")
    assert registry.descriptors() == (descriptor,)
    handle = registry.resolve(("static-analysis", "1.0.0"))
    assert isinstance(handle, ModelCapabilityProfileHandle)
    handle.close()

    with pytest.raises(KeyError):
        registry.resolve(("static-analysis", "2.0.0"))
    with pytest.raises(ValueError, match="duplicate"):
        registry.register(descriptor, lambda: _Handle(descriptor), trust_source="test")

    registry.seal()
    assert registry.sealed is True
    with pytest.raises(RuntimeError, match="sealed"):
        registry.register(_descriptor("other"), lambda: _Handle(_descriptor("other")))


def test_registry_closes_mismatched_handle_before_failing() -> None:
    registry = ModelCapabilityRegistry()
    requested = _descriptor()
    wrong = _Handle(_descriptor("other"))
    registry.register(requested, lambda: wrong)

    with pytest.raises(ValueError, match="descriptor"):
        registry.resolve(requested.reference)
    assert wrong.closed is True


def test_registry_rejects_duplicate_selection_without_auto_conflict_detection() -> None:
    registry = ModelCapabilityRegistry()
    first = _descriptor("first")
    second = _descriptor("second")
    registry.register(first, lambda: _Handle(first))
    registry.register(second, lambda: _Handle(second))
    selection = ModelCapabilitySelection((first.reference, second.reference))
    handles = registry.resolve_selection(selection)
    assert tuple(handle.descriptor.reference for handle in handles) == (
        first.reference, second.reference,
    )
    for handle in handles:
        handle.close()
