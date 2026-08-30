"""Provider-selection value objects with secrets kept out of repr output."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


class ConfigurationError(ValueError):
    """Raised when provider configuration cannot be resolved safely."""


@dataclass(frozen=True, slots=True)
class CliLLMOptions:
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    api_key_env: str | None = None
    timeout_seconds: float | int | str | None = None
    max_retries: int | str | None = None


@dataclass(frozen=True, slots=True, repr=False)
class SecretValue:
    value: str = field(repr=False)

    def __repr__(self) -> str:
        return "SecretValue(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class ResolvedLLMConfig:
    provider: str
    model: str
    base_url: str
    auth_kind: str
    credential_reference: str
    timeout_seconds: float
    max_retries: int
    pi_provider: str
    compatibility_profile: str
    descriptor_version: str
    public_headers: Mapping[str, str]
    field_sources: Mapping[str, str]
    supports_tools: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "public_headers", MappingProxyType(dict(self.public_headers))
        )
        object.__setattr__(
            self, "field_sources", MappingProxyType(dict(self.field_sources))
        )

    def __repr__(self) -> str:
        return (
            "ResolvedLLMConfig("
            f"provider={self.provider!r}, model={self.model!r}, "
            f"base_url={self.base_url!r}, auth_kind={self.auth_kind!r}, "
            f"credential_reference={self.credential_reference!r}, "
            f"timeout_seconds={self.timeout_seconds!r}, "
            f"max_retries={self.max_retries!r}, pi_provider={self.pi_provider!r}, "
            f"compatibility_profile={self.compatibility_profile!r}, "
            f"descriptor_version={self.descriptor_version!r}, "
            f"public_headers={dict(self.public_headers)!r}, "
            f"field_sources={dict(self.field_sources)!r}, "
            f"supports_tools={self.supports_tools!r})"
        )


@dataclass(frozen=True, slots=True, repr=False)
class ResolvedLLM:
    config: ResolvedLLMConfig
    secret: SecretValue | None = field(default=None, repr=False)

    def __repr__(self) -> str:
        return f"ResolvedLLM(config={self.config!r}, secret=<redacted>)"


__all__ = [
    "CliLLMOptions",
    "ConfigurationError",
    "ResolvedLLM",
    "ResolvedLLMConfig",
    "SecretValue",
]
