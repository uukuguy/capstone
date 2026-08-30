"""Controller-owned, explicit application registration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from capability_agent.application.errors import ApplicationConfigurationError
from capability_agent.application.profile import ApplicationProfile

from grid_agent.application.profile import build_pandapower_application_profile


ApplicationProfileFactory = Callable[[], ApplicationProfile]


@dataclass(frozen=True, slots=True)
class _ApplicationRegistration:
    application_id: str
    version: str
    factory: ApplicationProfileFactory


class ApplicationRegistry:
    """Resolve only applications registered by trusted source code.

    This registry intentionally has no package scanning, import-by-name, entry
    point loading, or remote discovery.  Those capabilities belong to a later
    signed/discovery workstream.
    """

    def __init__(self) -> None:
        self._registrations: dict[tuple[str, str], _ApplicationRegistration] = {}

    def register(
        self,
        application_id: str,
        version: str,
        factory: ApplicationProfileFactory,
    ) -> None:
        _require_identity(application_id, "application_id")
        _require_identity(version, "application version")
        if not callable(factory):
            raise ApplicationConfigurationError("application factory is not callable")
        key = (application_id, version)
        if key in self._registrations:
            raise ApplicationConfigurationError(
                f"application {application_id!r} version {version!r} is already registered"
            )
        self._registrations[key] = _ApplicationRegistration(
            application_id=application_id,
            version=version,
            factory=factory,
        )

    def resolve(self, application_id: str, version: str | None = None) -> ApplicationProfile:
        _require_identity(application_id, "application_id")
        matches = [
            registration
            for (registered_id, registered_version), registration in self._registrations.items()
            if registered_id == application_id
            and (version is None or registered_version == version)
        ]
        if not matches:
            suffix = f" version {version!r}" if version is not None else ""
            raise ApplicationConfigurationError(
                f"application {application_id!r}{suffix} is not registered"
            )
        if len(matches) != 1:
            raise ApplicationConfigurationError(
                f"application {application_id!r} requires an explicit version"
            )
        registration = matches[0]
        profile = registration.factory()
        if not isinstance(profile, ApplicationProfile):
            raise ApplicationConfigurationError(
                "registered application factory did not return an ApplicationProfile"
            )
        manifest = profile.manifest
        if (
            manifest.application_id != registration.application_id
            or manifest.version != registration.version
        ):
            raise ApplicationConfigurationError(
                "registered application factory manifest does not match registration"
            )
        return profile

    def application_ids(self) -> tuple[str, ...]:
        return tuple(sorted({application_id for application_id, _ in self._registrations}))

    def versions(self, application_id: str) -> tuple[str, ...]:
        return tuple(
            sorted(
                version
                for registered_id, version in self._registrations
                if registered_id == application_id
            )
        )


def build_trusted_application_registry() -> ApplicationRegistry:
    """Return the source-defined registry for supported applications."""

    registry = ApplicationRegistry()
    registry.register(
        "pandapower-static-analysis",
        "1.0.1",
        build_pandapower_application_profile,
    )
    return registry


# Friendly aliases for callers that use the registry as the composition root.
build_application_registry = build_trusted_application_registry
trusted_application_registry = build_trusted_application_registry


def _require_identity(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ApplicationConfigurationError(f"{label} must be non-empty text")
    if any(character.isspace() for character in value):
        raise ApplicationConfigurationError(f"{label} must not contain whitespace")


__all__ = [
    "ApplicationProfileFactory",
    "ApplicationRegistry",
    "build_application_registry",
    "build_trusted_application_registry",
    "trusted_application_registry",
]
