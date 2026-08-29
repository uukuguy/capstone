"""Domain acceptance declaration contracts."""

from typing import Protocol


class DomainAcceptanceProfile(Protocol):
    def offline_cases(self) -> tuple[object, ...]: ...

    def scripted_cases(self) -> tuple[object, ...]: ...

    def provider_cases(self) -> tuple[object, ...]: ...


__all__ = ["DomainAcceptanceProfile"]
