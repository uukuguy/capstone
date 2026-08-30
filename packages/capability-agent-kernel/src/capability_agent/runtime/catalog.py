"""Explicit, domain-neutral provider catalog contracts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Mapping, Protocol, runtime_checkable

from capability_agent.runtime.models import ConfigurationError


_CATALOG_FIELDS = frozenset(
    {"schema_version", "descriptor_version", "default_provider", "providers"}
)
_PROVIDER_FIELDS = frozenset(
    {
        "default_model",
        "base_url",
        "base_url_policy",
        "auth",
        "pi_provider",
        "compatibility_profile",
        "supports_tools",
        "allowed_models",
        "public_header_env",
    }
)
_AUTH_FIELDS = frozenset({"kind", "default_env", "profile"})


@dataclass(frozen=True, slots=True)
class ProviderAuth:
    kind: Literal["api_key_env", "pi_oauth"]
    default_env: str | None = None
    profile: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    name: str
    default_model: str
    base_url: str
    base_url_policy: Literal["override_allowed", "fixed"]
    auth: ProviderAuth
    pi_provider: str
    compatibility_profile: str
    supports_tools: bool
    allowed_models: frozenset[str] | None = None
    public_header_env: MappingProxyType | dict[str, str] = MappingProxyType({})

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "public_header_env", MappingProxyType(dict(self.public_header_env))
        )


@runtime_checkable
class ProviderCatalogSource(Protocol):
    """Source that provides the explicitly selected provider descriptors."""

    def load(self) -> "ProviderCatalog": ...


@dataclass(frozen=True, slots=True)
class ProviderCatalog:
    schema_version: int
    descriptor_version: str
    default_provider: str
    providers: Mapping[str, ProviderDescriptor]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "providers", MappingProxyType(dict(self.providers))
        )

    @classmethod
    def load(
        cls,
        path: Path | None = None,
        *,
        required_providers: frozenset[str] | set[str] | None = None,
    ) -> "ProviderCatalog":
        catalog_path = path or _default_catalog_path()
        try:
            raw = json.loads(catalog_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConfigurationError("provider catalog could not be loaded") from exc
        return cls.from_mapping(raw, required_providers=required_providers)

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any],
        *,
        required_providers: frozenset[str] | set[str] | None = None,
    ) -> "ProviderCatalog":
        if not isinstance(raw, Mapping):
            raise ConfigurationError("provider catalog must be an object")
        unknown = set(raw).difference(_CATALOG_FIELDS)
        if unknown:
            raise ConfigurationError(
                "provider catalog contains unknown fields: "
                + ", ".join(sorted(str(field) for field in unknown))
            )
        providers_raw = raw.get("providers")
        if not isinstance(providers_raw, Mapping) or not providers_raw:
            raise ConfigurationError("provider catalog must contain providers")

        provider_names = {name for name in providers_raw if isinstance(name, str)}
        if len(provider_names) != len(providers_raw):
            raise ConfigurationError("provider catalog provider names must be text")
        if required_providers is not None and provider_names != set(required_providers):
            raise ConfigurationError(
                "provider catalog must bind exactly the required provider set"
            )

        schema_version = raw.get("schema_version")
        if schema_version != 1:
            raise ConfigurationError("provider catalog schema_version must be 1")
        descriptor_version = _required_string(raw, "descriptor_version")
        default_provider = _required_string(raw, "default_provider")
        if default_provider not in providers_raw:
            raise ConfigurationError(
                f"default provider {default_provider!r} is not in the provider catalog"
            )
        providers = {
            name: _parse_provider(name, value)
            for name, value in providers_raw.items()
        }
        return cls(
            schema_version=schema_version,
            descriptor_version=descriptor_version,
            default_provider=default_provider,
            providers=providers,
        )

    def provider(self, name: str) -> ProviderDescriptor:
        try:
            return self.providers[name]
        except KeyError as exc:
            raise ConfigurationError(f"unknown provider {name!r}") from exc


def _default_catalog_path() -> Path:
    return Path.cwd() / "configs" / "llm-providers.json"


def _parse_provider(name: str, raw: Any) -> ProviderDescriptor:
    if not isinstance(name, str) or not name.strip():
        raise ConfigurationError("provider names must be non-empty text")
    if not isinstance(raw, Mapping):
        raise ConfigurationError(f"provider {name!r} must be an object")
    unknown = set(raw).difference(_PROVIDER_FIELDS)
    if unknown:
        raise ConfigurationError(
            f"provider {name!r} contains unknown fields: "
            + ", ".join(sorted(str(field) for field in unknown))
        )
    auth_raw = raw.get("auth")
    if not isinstance(auth_raw, Mapping):
        raise ConfigurationError(f"provider {name!r} must include auth")
    unknown_auth = set(auth_raw).difference(_AUTH_FIELDS)
    if unknown_auth:
        raise ConfigurationError(
            f"provider {name!r} auth contains unknown fields: "
            + ", ".join(sorted(str(field) for field in unknown_auth))
        )
    auth_kind = _required_string(auth_raw, "kind")
    if auth_kind == "api_key_env":
        auth = ProviderAuth(
            kind="api_key_env",
            default_env=_required_string(auth_raw, "default_env"),
        )
    elif auth_kind == "pi_oauth":
        auth = ProviderAuth(
            kind="pi_oauth", profile=_required_string(auth_raw, "profile")
        )
    else:
        raise ConfigurationError(f"provider {name!r} has unsupported auth kind")

    base_url_policy = _required_string(raw, "base_url_policy")
    if base_url_policy not in {"override_allowed", "fixed"}:
        raise ConfigurationError(f"provider {name!r} has unsupported base URL policy")
    supports_tools = raw.get("supports_tools")
    if not isinstance(supports_tools, bool):
        raise ConfigurationError(f"provider {name!r} must declare supports_tools")
    header_env_raw = raw.get("public_header_env", {})
    if not isinstance(header_env_raw, Mapping) or any(
        not isinstance(key, str) or not isinstance(value, str) or not value.strip()
        for key, value in header_env_raw.items()
    ):
        raise ConfigurationError(f"provider {name!r} public_header_env is invalid")
    return ProviderDescriptor(
        name=name,
        default_model=_required_string(raw, "default_model"),
        base_url=_required_string(raw, "base_url"),
        base_url_policy=base_url_policy,  # type: ignore[arg-type]
        auth=auth,
        pi_provider=_required_string(raw, "pi_provider"),
        compatibility_profile=_required_string(raw, "compatibility_profile"),
        supports_tools=supports_tools,
        allowed_models=_optional_string_set(raw, "allowed_models"),
        public_header_env=dict(header_env_raw),
    )


def _required_string(raw: Mapping[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"provider catalog field {key!r} must be a non-empty string")
    return value.strip()


def _optional_string_set(
    raw: Mapping[str, Any], key: str
) -> frozenset[str] | None:
    value = raw.get(key)
    if value is None:
        return None
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item.strip() for item in value)
    ):
        raise ConfigurationError(
            f"provider catalog field {key!r} must be a non-empty string list"
        )
    normalized = [item.strip() for item in value]
    if len(set(normalized)) != len(normalized):
        raise ConfigurationError(
            f"provider catalog field {key!r} must not contain duplicates"
        )
    return frozenset(normalized)


__all__ = [
    "ProviderAuth",
    "ProviderCatalog",
    "ProviderCatalogSource",
    "ProviderDescriptor",
]
