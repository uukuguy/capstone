"""Capstone-owned model-to-profile selection above the neutral SPI."""

from __future__ import annotations

from dataclasses import dataclass
import re

from capstone_model_capability_spi import (
    ModelCapabilityDescriptor,
    ModelCapabilityFactory,
    ModelCapabilityProfileHandle,
    ModelCapabilityRegistry,
    ModelCapabilitySelection,
)

from .thread_service import ThreadModelDescriptor


_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


@dataclass(frozen=True, slots=True)
class ModelCapabilityProfileInfo:
    """User-facing metadata and implementation-family eligibility."""

    descriptor: ModelCapabilityDescriptor
    display_name: str
    implementation_families: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.display_name, str) or not self.display_name.strip():
            raise ValueError("profile display_name is invalid")
        if not self.implementation_families:
            raise ValueError("profile implementation_families is empty")
        normalized = tuple(dict.fromkeys(self.implementation_families))
        if any(
            not isinstance(family, str) or not _IDENTIFIER.fullmatch(family)
            for family in normalized
        ):
            raise ValueError("profile implementation family is invalid")
        object.__setattr__(self, "implementation_families", normalized)


class CapstoneModelCapabilityCatalog:
    """Resolve exact profile selections for a registered model context.

    This catalog does not inspect tools or infer semantic conflicts.  It only
    checks exact registry membership and declared implementation-family
    compatibility; professional users can enable overlapping packages and
    diagnose provenance during execution.
    """

    def __init__(self, registry: ModelCapabilityRegistry) -> None:
        if not isinstance(registry, ModelCapabilityRegistry):
            raise TypeError("registry must be a ModelCapabilityRegistry")
        self.registry = registry
        self._profiles: dict[tuple[str, str], ModelCapabilityProfileInfo] = {}
        self._family_defaults: dict[str, ModelCapabilitySelection] = {}
        self._model_defaults: dict[tuple[str, str], ModelCapabilitySelection] = {}

    def register_profile(
        self,
        info: ModelCapabilityProfileInfo,
        factory: ModelCapabilityFactory,
        *,
        trust_source: str = "trusted-bootstrap",
    ) -> None:
        if not isinstance(info, ModelCapabilityProfileInfo):
            raise TypeError("profile info is invalid")
        if info.descriptor.reference in self._profiles:
            raise ValueError("duplicate profile metadata")
        self.registry.register(info.descriptor, factory, trust_source=trust_source)
        self._profiles[info.descriptor.reference] = info

    def profiles_for_family(self, implementation_family: str) -> tuple[ModelCapabilityProfileInfo, ...]:
        if not isinstance(implementation_family, str) or not _IDENTIFIER.fullmatch(implementation_family):
            raise ValueError("implementation family is invalid")
        return tuple(
            info for _, info in sorted(self._profiles.items())
            if implementation_family in info.implementation_families
        )

    def set_family_default(
        self, implementation_family: str, selection: ModelCapabilitySelection,
    ) -> None:
        self._validate_family(implementation_family)
        self._validate_selection(selection, implementation_family)
        if implementation_family in self._family_defaults:
            raise ValueError("duplicate family default")
        self._family_defaults[implementation_family] = selection

    def set_model_default(
        self, model_id: str, model_revision: str, selection: ModelCapabilitySelection,
    ) -> None:
        self._validate_model_key(model_id, model_revision)
        self._validate_selection(selection, None)
        key = (model_id, model_revision)
        if key in self._model_defaults:
            raise ValueError("duplicate model default")
        self._model_defaults[key] = selection

    def resolve(
        self,
        model: ThreadModelDescriptor,
        selection: ModelCapabilitySelection | None = None,
    ) -> ModelCapabilitySelection:
        if not isinstance(model, ThreadModelDescriptor):
            raise TypeError("model must be a ThreadModelDescriptor")
        if selection is not None:
            self._validate_selection(selection, model.implementation_family)
            return selection
        exact = self._model_defaults.get((model.model_id, model.model_revision))
        if exact is not None:
            self._validate_selection(exact, model.implementation_family)
            return exact
        family = self._family_defaults.get(model.implementation_family)
        if family is not None:
            self._validate_selection(family, model.implementation_family)
            return family
        return ModelCapabilitySelection.empty()

    def prepare(
        self,
        model: ThreadModelDescriptor,
        selection: ModelCapabilitySelection | None = None,
    ) -> tuple[ModelCapabilityProfileHandle, ...]:
        """Resolve and prepare the complete selection atomically."""

        selected = self.resolve(model, selection)
        return self.registry.resolve_selection(selected)

    def _validate_selection(
        self, selection: ModelCapabilitySelection, implementation_family: str | None,
    ) -> None:
        self.registry.validate_selection(selection)
        for reference in selection.enabled_profiles:
            info = self._profiles.get(reference)
            if info is None:
                raise KeyError(reference)
            if (
                implementation_family is not None
                and implementation_family not in info.implementation_families
            ):
                raise ValueError(
                    f"profile {reference[0]} is not compatible with implementation family "
                    f"{implementation_family}",
                )

    @staticmethod
    def _validate_family(value: str) -> None:
        if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
            raise ValueError("implementation family is invalid")

    @staticmethod
    def _validate_model_key(model_id: str, model_revision: str) -> None:
        if not isinstance(model_id, str) or not _IDENTIFIER.fullmatch(model_id):
            raise ValueError("model_id is invalid")
        if not isinstance(model_revision, str) or not model_revision.strip():
            raise ValueError("model_revision is invalid")


__all__ = ["CapstoneModelCapabilityCatalog", "ModelCapabilityProfileInfo"]
