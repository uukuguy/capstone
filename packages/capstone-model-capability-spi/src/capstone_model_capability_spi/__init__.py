"""Neutral Model Capability Profile selection contracts.

This package intentionally knows nothing about Capstone's Kernel, Domain
Packs, Authorities, Pi, DSH, tools, or model catalogs.  It only provides the
small registry and exact selection boundary used by an application composition
root.  A resolved handle is process-local and must never be persisted.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol, TypeAlias, runtime_checkable


SPI_VERSION = "1"
SELECTION_SCHEMA = "capstone-model-capability-selection/1"
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_VERSION = re.compile(r"^[0-9]+(?:\.[0-9]+){1,3}(?:[-+][a-z0-9.-]+)?$")
ProfileReference: TypeAlias = tuple[str, str]


def _text(value: object, *, name: str, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"{name} is invalid")
    return value


@dataclass(frozen=True, slots=True)
class ModelCapabilityDescriptor:
    """The only identity a neutral profile registry exposes publicly."""

    profile_id: str
    profile_version: str
    spi_version: str = SPI_VERSION

    def __post_init__(self) -> None:
        _text(self.profile_id, name="profile_id", pattern=_IDENTIFIER)
        _text(self.profile_version, name="profile_version", pattern=_VERSION)
        if self.spi_version != SPI_VERSION:
            raise ValueError("unsupported model capability SPI version")

    @property
    def reference(self) -> ProfileReference:
        return self.profile_id, self.profile_version

    def to_document(self) -> dict[str, str]:
        return {
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "spi_version": self.spi_version,
        }


@dataclass(frozen=True, slots=True)
class ModelCapabilitySelection:
    """An exact user/application selection; an empty selection is valid."""

    enabled_profiles: tuple[ProfileReference, ...] = ()

    def __post_init__(self) -> None:
        seen: set[ProfileReference] = set()
        normalized: list[ProfileReference] = []
        for reference in self.enabled_profiles:
            if not isinstance(reference, tuple) or len(reference) != 2:
                raise ValueError("profile reference is invalid")
            profile_id = _text(reference[0], name="profile_id", pattern=_IDENTIFIER)
            profile_version = _text(reference[1], name="profile_version", pattern=_VERSION)
            normalized_reference = (profile_id, profile_version)
            if normalized_reference in seen:
                raise ValueError("duplicate profile reference")
            seen.add(normalized_reference)
            normalized.append(normalized_reference)
        object.__setattr__(self, "enabled_profiles", tuple(normalized))

    @classmethod
    def empty(cls) -> "ModelCapabilitySelection":
        return cls()

    def to_document(self) -> dict[str, object]:
        return {
            "schema": SELECTION_SCHEMA,
            "enabled_profiles": [
                {"profile_id": profile_id, "profile_version": profile_version}
                for profile_id, profile_version in self.enabled_profiles
            ],
        }


@runtime_checkable
class ModelCapabilityProfileHandle(Protocol):
    """A context-scoped profile resource returned by exact registry lookup."""

    descriptor: ModelCapabilityDescriptor

    def close(self) -> None: ...


class ModelCapabilityFactory(Protocol):
    def __call__(self) -> ModelCapabilityProfileHandle: ...


@dataclass(frozen=True, slots=True)
class _Registration:
    descriptor: ModelCapabilityDescriptor
    factory: ModelCapabilityFactory
    trust_source: str


class ModelCapabilityRegistry:
    """Trusted bootstrap registry with exact, read-only runtime resolution."""

    def __init__(self, *, spi_version: str = SPI_VERSION) -> None:
        if spi_version != SPI_VERSION:
            raise ValueError("unsupported model capability SPI version")
        self._spi_version = spi_version
        self._registrations: dict[ProfileReference, _Registration] = {}
        self._sealed = False

    @property
    def sealed(self) -> bool:
        return self._sealed

    def register(
        self,
        descriptor: ModelCapabilityDescriptor,
        factory: ModelCapabilityFactory,
        *,
        trust_source: str = "trusted-bootstrap",
    ) -> None:
        if self._sealed:
            raise RuntimeError("model capability registry is sealed")
        if not isinstance(descriptor, ModelCapabilityDescriptor):
            raise TypeError("descriptor must be a ModelCapabilityDescriptor")
        if descriptor.spi_version != self._spi_version:
            raise ValueError("descriptor SPI version does not match registry")
        if not callable(factory):
            raise TypeError("model capability factory must be callable")
        if not isinstance(trust_source, str) or not trust_source.strip():
            raise ValueError("trust_source is invalid")
        if descriptor.reference in self._registrations:
            raise ValueError("duplicate model capability profile")
        self._registrations[descriptor.reference] = _Registration(
            descriptor, factory, trust_source,
        )

    def seal(self) -> None:
        self._sealed = True

    def descriptors(self) -> tuple[ModelCapabilityDescriptor, ...]:
        return tuple(
            registration.descriptor
            for _, registration in sorted(self._registrations.items())
        )

    def resolve(self, reference: ProfileReference) -> ModelCapabilityProfileHandle:
        if not isinstance(reference, tuple) or len(reference) != 2:
            raise ValueError("profile reference is invalid")
        registration = self._registrations.get(reference)
        if registration is None:
            raise KeyError(reference)
        handle = registration.factory()
        try:
            descriptor = getattr(handle, "descriptor", None)
            if descriptor != registration.descriptor:
                raise ValueError("resolved profile handle descriptor does not match")
            if not callable(getattr(handle, "close", None)):
                raise ValueError("resolved profile handle is not closeable")
            return handle
        except BaseException as error:
            close = getattr(handle, "close", None)
            if callable(close):
                try:
                    close()
                except BaseException as cleanup_error:
                    raise BaseExceptionGroup(
                        "profile validation and cleanup failed", [error, cleanup_error],
                    ) from None
            raise

    def resolve_selection(
        self, selection: ModelCapabilitySelection,
    ) -> tuple[ModelCapabilityProfileHandle, ...]:
        if not isinstance(selection, ModelCapabilitySelection):
            raise TypeError("selection must be a ModelCapabilitySelection")
        # Validate the complete set before factories allocate context resources.
        for reference in selection.enabled_profiles:
            if reference not in self._registrations:
                raise KeyError(reference)
        handles: list[ModelCapabilityProfileHandle] = []
        try:
            for reference in selection.enabled_profiles:
                handles.append(self.resolve(reference))
            return tuple(handles)
        except BaseException as error:
            cleanup_errors: list[BaseException] = []
            for handle in reversed(handles):
                try:
                    handle.close()
                except BaseException as cleanup_error:
                    cleanup_errors.append(cleanup_error)
            if cleanup_errors:
                raise BaseExceptionGroup(
                    "profile preparation and cleanup failed", [error, *cleanup_errors],
                ) from None
            raise


__all__ = [
    "ModelCapabilityDescriptor",
    "ModelCapabilityFactory",
    "ModelCapabilityProfileHandle",
    "ModelCapabilityRegistry",
    "ModelCapabilitySelection",
    "ProfileReference",
    "SELECTION_SCHEMA",
    "SPI_VERSION",
]
