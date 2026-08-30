"""Deterministic provider/model resolution for the generic runtime."""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import dotenv_values as read_dotenv_values

from capability_agent.runtime.catalog import ProviderCatalog
from capability_agent.runtime.models import (
    CliLLMOptions,
    ConfigurationError,
    ResolvedLLM,
    ResolvedLLMConfig,
    SecretValue,
)


DEFAULT_TIMEOUT_SECONDS = 180.0
DEFAULT_MAX_RETRIES = 2
ENV_PROVIDER = "CAPABILITY_AGENT_LLM_PROVIDER"
ENV_MODEL = "CAPABILITY_AGENT_LLM_MODEL"
ENV_BASE_URL = "CAPABILITY_AGENT_LLM_BASE_URL"
ENV_API_KEY_ENV = "CAPABILITY_AGENT_LLM_API_KEY_ENV"
ENV_TIMEOUT = "CAPABILITY_AGENT_LLM_TIMEOUT_SECONDS"
ENV_RETRIES = "CAPABILITY_AGENT_LLM_MAX_RETRIES"
_RUNTIME_CHANNEL_ENV_NAMES = frozenset(
    {
        "PATH",
        "HOME",
        "TMPDIR",
        "LANG",
        "LC_ALL",
        "SSL_CERT_FILE",
        "HTTPS_PROXY",
        "HTTP_PROXY",
        "NO_PROXY",
        "PI_CODING_AGENT_DIR",
        "PI_CODING_AGENT_SESSION_DIR",
        "PI_OFFLINE",
    }
)


def resolve_llm(
    *,
    catalog: ProviderCatalog,
    cli: CliLLMOptions,
    environ: Mapping[str, str],
    env_file: Path | None = None,
    dotenv_values: Mapping[str, str | None] | None = None,
    oauth_configured: Callable[[str], bool] | None = None,
    env_prefix: str = "CAPABILITY_AGENT",
) -> ResolvedLLM:
    """Resolve one provider without inferring identity from credentials.

    ``env_prefix`` exists solely for an explicit compatibility adapter.  The
    default path is always the domain-neutral ``CAPABILITY_AGENT`` namespace.
    """

    prefix = _validate_prefix(env_prefix)
    names = {
        "provider": f"{prefix}_LLM_PROVIDER",
        "model": f"{prefix}_LLM_MODEL",
        "base_url": f"{prefix}_LLM_BASE_URL",
        "api_key_env": f"{prefix}_LLM_API_KEY_ENV",
        "timeout": f"{prefix}_LLM_TIMEOUT_SECONDS",
        "retries": f"{prefix}_LLM_MAX_RETRIES",
    }
    dotenv_layer = _load_dotenv_layer(env_file=env_file, dotenv_values=dotenv_values)

    provider_value, provider_source = _resolve_field(
        cli.provider, names["provider"], environ, dotenv_layer, catalog.default_provider
    )
    provider = _validate_provider(provider_value, catalog)
    descriptor = catalog.provider(provider)

    model_value, model_source = _resolve_field(
        cli.model, names["model"], environ, dotenv_layer, descriptor.default_model
    )
    model = _validate_model(model_value)
    if descriptor.allowed_models is not None and model not in descriptor.allowed_models:
        choices = ", ".join(sorted(descriptor.allowed_models))
        raise ConfigurationError(
            f"provider {provider!r} supports only these model IDs: {choices}"
        )

    base_url_value, base_url_source = _resolve_field(
        cli.base_url, names["base_url"], environ, dotenv_layer, descriptor.base_url
    )
    base_url = _validate_base_url(base_url_value)
    if descriptor.base_url_policy == "fixed" and base_url != descriptor.base_url:
        raise ConfigurationError(
            f"provider {provider!r} has a fixed base URL and does not allow overrides"
        )

    timeout_value, timeout_source = _resolve_field(
        cli.timeout_seconds,
        names["timeout"],
        environ,
        dotenv_layer,
        DEFAULT_TIMEOUT_SECONDS,
    )
    timeout_seconds = _validate_timeout(timeout_value)

    retries_value, retries_source = _resolve_field(
        cli.max_retries,
        names["retries"],
        environ,
        dotenv_layer,
        DEFAULT_MAX_RETRIES,
    )
    max_retries = _validate_retries(retries_value)

    credential_reference, credential_source, secret = _resolve_auth(
        descriptor=descriptor,
        cli=cli,
        environ=environ,
        dotenv_layer=dotenv_layer,
        env_name=names["api_key_env"],
        oauth_configured=oauth_configured,
    )
    if not descriptor.supports_tools:
        raise ConfigurationError(f"provider {provider!r} must support tools")

    config = ResolvedLLMConfig(
        provider=provider,
        model=model,
        base_url=base_url,
        auth_kind=descriptor.auth.kind,
        credential_reference=credential_reference,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        pi_provider=descriptor.pi_provider,
        compatibility_profile=descriptor.compatibility_profile,
        descriptor_version=catalog.descriptor_version,
        public_headers=_public_headers(descriptor, environ, dotenv_layer),
        field_sources={
            "provider": provider_source,
            "model": model_source,
            "base_url": base_url_source,
            "credential_reference": credential_source,
            "timeout_seconds": timeout_source,
            "max_retries": retries_source,
        },
        supports_tools=descriptor.supports_tools,
    )
    return ResolvedLLM(config=config, secret=secret)


def _validate_prefix(prefix: str) -> str:
    if not isinstance(prefix, str) or not prefix or any(
        not (char.isalnum() or char == "_") for char in prefix
    ):
        raise ConfigurationError("environment prefix is invalid")
    return prefix.rstrip("_")


def _load_dotenv_layer(
    *,
    env_file: Path | None,
    dotenv_values: Mapping[str, str | None] | None,
) -> Mapping[str, str | None]:
    if dotenv_values is not None:
        return dict(dotenv_values)
    candidate = env_file or Path.cwd() / ".env"
    if not candidate.exists():
        return {}
    try:
        return dict(read_dotenv_values(candidate))
    except OSError as exc:
        raise ConfigurationError("provider environment file could not be read") from exc


def _resolve_field(
    cli_value: Any,
    env_name: str,
    environ: Mapping[str, str],
    dotenv_layer: Mapping[str, str | None],
    default: Any,
) -> tuple[Any, str]:
    value = _normalize_optional(cli_value)
    if value is not None:
        return value, "cli"
    value = _normalize_optional(environ.get(env_name))
    if value is not None:
        return value, "process"
    value = _normalize_optional(dotenv_layer.get(env_name))
    if value is not None:
        return value, "dotenv"
    return default, "default"


def _resolve_auth(
    *,
    descriptor: Any,
    cli: CliLLMOptions,
    environ: Mapping[str, str],
    dotenv_layer: Mapping[str, str | None],
    env_name: str,
    oauth_configured: Callable[[str], bool] | None,
) -> tuple[str, str, SecretValue | None]:
    if descriptor.auth.kind == "api_key_env":
        credential_reference, source = _resolve_field(
            cli.api_key_env,
            env_name,
            environ,
            dotenv_layer,
            descriptor.auth.default_env,
        )
        credential_reference = _validate_env_var_name(credential_reference)
        secret = _secret_from_layers(credential_reference, environ, dotenv_layer)
        if secret is None:
            raise ConfigurationError(
                f"missing API key in environment variable {credential_reference}"
            )
        return credential_reference, source, SecretValue(secret)

    if descriptor.auth.kind == "pi_oauth":
        profile = descriptor.auth.profile
        if not profile:
            raise ConfigurationError("OAuth provider is missing a profile")
        if _normalize_optional(cli.api_key_env) is not None:
            raise ConfigurationError("OAuth provider does not accept an API key override")
        if oauth_configured is None or not oauth_configured(profile):
            raise ConfigurationError(f"OAuth profile {profile!r} is not configured")
        return profile, "default", None
    raise ConfigurationError("unsupported provider authentication kind")


def _secret_from_layers(
    credential_reference: str,
    environ: Mapping[str, str],
    dotenv_layer: Mapping[str, str | None],
) -> str | None:
    process_value = _normalize_optional(environ.get(credential_reference))
    if process_value is not None:
        return str(process_value)
    dotenv_value = _normalize_optional(dotenv_layer.get(credential_reference))
    if dotenv_value is not None:
        return str(dotenv_value)
    return None


def _public_headers(
    descriptor: Any,
    environ: Mapping[str, str],
    dotenv_layer: Mapping[str, str | None],
) -> dict[str, str]:
    headers: dict[str, str] = {}
    for header_name, env_name in descriptor.public_header_env.items():
        value = _normalize_optional(environ.get(env_name))
        if value is None:
            value = _normalize_optional(dotenv_layer.get(env_name))
        if value is not None:
            headers[str(header_name)] = str(value)
    return headers


def _normalize_optional(value: Any) -> Any | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _validate_provider(value: Any, catalog: ProviderCatalog) -> str:
    provider = _validate_non_empty_string(value, "provider")
    if provider not in catalog.providers:
        raise ConfigurationError(f"unknown provider {provider!r}")
    return provider


def _validate_model(value: Any) -> str:
    return _validate_non_empty_string(value, "model")


def _validate_env_var_name(value: Any) -> str:
    name = _validate_non_empty_string(value, "API key environment variable")
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is None:
        raise ConfigurationError(f"invalid API key environment variable name {name!r}")
    if name in _RUNTIME_CHANNEL_ENV_NAMES or name.startswith("CAPABILITY_AGENT_"):
        raise ConfigurationError(
            "API key environment variable conflicts with a runtime channel"
        )
    return name


def _validate_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"invalid {field_name}: expected a non-empty string")
    return value.strip()


def _validate_base_url(value: Any) -> str:
    base_url = _validate_non_empty_string(value, "base URL")
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        raise ConfigurationError("base URL must be an absolute URL")
    if parsed.scheme == "https":
        return base_url
    if parsed.scheme == "http" and _is_loopback_host(parsed.hostname):
        return base_url
    if parsed.scheme != "http":
        raise ConfigurationError(
            "base URL must be an absolute URL using an http or https scheme"
        )
    raise ConfigurationError("base URL must use HTTPS unless it targets a loopback host")


def _is_loopback_host(hostname: str | None) -> bool:
    if hostname is None or hostname == "localhost":
        return hostname == "localhost"
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def _validate_timeout(value: Any) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError("timeout must be a positive number of seconds") from exc
    if timeout <= 0:
        raise ConfigurationError("timeout must be a positive number of seconds")
    return timeout


def _validate_retries(value: Any) -> int:
    if isinstance(value, str) and "." in value:
        raise ConfigurationError("retries must be a nonnegative integer")
    try:
        retries = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError("retries must be a nonnegative integer") from exc
    if retries < 0:
        raise ConfigurationError("retries must be a nonnegative integer")
    return retries


__all__ = [
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_TIMEOUT_SECONDS",
    "ENV_API_KEY_ENV",
    "ENV_BASE_URL",
    "ENV_MODEL",
    "ENV_PROVIDER",
    "ENV_RETRIES",
    "ENV_TIMEOUT",
    "resolve_llm",
]
