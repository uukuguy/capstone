from __future__ import annotations

import pytest

from capability_agent.runtime.catalog import ProviderCatalog
from capability_agent.runtime.models import CliLLMOptions, ConfigurationError
from capability_agent.runtime.resolver import resolve_llm


def test_resolver_uses_capability_agent_environment_names() -> None:
    catalog = ProviderCatalog.from_mapping(
        {
            "schema_version": 1,
            "descriptor_version": "fixture-1",
            "default_provider": "alpha",
            "providers": {
                "alpha": {
                    "default_model": "alpha-model",
                    "base_url": "https://provider.example/v1",
                    "base_url_policy": "override_allowed",
                    "auth": {"kind": "api_key_env", "default_env": "ALPHA_KEY"},
                    "pi_provider": "alpha",
                    "compatibility_profile": "generic",
                    "supports_tools": True,
                }
            },
        }
    )

    resolved = resolve_llm(
        catalog=catalog,
        cli=CliLLMOptions(),
        environ={"ALPHA_KEY": "secret", "CAPABILITY_AGENT_LLM_MODEL": "override"},
    )

    assert resolved.config.model == "override"
    assert resolved.config.credential_reference == "ALPHA_KEY"


def _catalog(*, allowed_models: list[str] | None = None) -> ProviderCatalog:
    descriptor: dict[str, object] = {
        "default_model": "alpha-model",
        "base_url": "https://provider.example/v1",
        "base_url_policy": "override_allowed",
        "auth": {"kind": "api_key_env", "default_env": "ALPHA_KEY"},
        "pi_provider": "alpha",
        "compatibility_profile": "generic",
        "supports_tools": True,
    }
    if allowed_models is not None:
        descriptor["allowed_models"] = allowed_models
    return ProviderCatalog.from_mapping(
        {
            "schema_version": 1,
            "descriptor_version": "fixture-1",
            "default_provider": "alpha",
            "providers": {"alpha": descriptor},
        }
    )


def test_resolver_rejects_unknown_model_for_allowlisted_provider() -> None:
    with pytest.raises(ConfigurationError, match="model IDs"):
        resolve_llm(
            catalog=_catalog(allowed_models=["alpha-model"]),
            cli=CliLLMOptions(model="not-registered"),
            environ={"ALPHA_KEY": "secret"},
        )


def test_resolver_rejects_invalid_custom_secret_environment_name() -> None:
    with pytest.raises(ConfigurationError, match="environment variable"):
        resolve_llm(
            catalog=_catalog(),
            cli=CliLLMOptions(api_key_env="ALPHA-KEY"),
            environ={"ALPHA-KEY": "secret"},
        )


@pytest.mark.parametrize("name", ["PATH", "HOME", "CAPABILITY_AGENT_RUNTIME_DESCRIPTOR"])
def test_resolver_rejects_runtime_channel_as_secret_environment_name(name: str) -> None:
    with pytest.raises(ConfigurationError, match="runtime channel"):
        resolve_llm(
            catalog=_catalog(),
            cli=CliLLMOptions(api_key_env=name),
            environ={name: "secret"},
        )


def test_resolved_config_maps_are_immutable_and_secret_is_redacted() -> None:
    resolved = resolve_llm(
        catalog=_catalog(),
        cli=CliLLMOptions(),
        environ={"ALPHA_KEY": "do-not-print"},
    )
    with pytest.raises(TypeError):
        resolved.config.field_sources["injected"] = "bad"  # type: ignore[index]
    assert "do-not-print" not in repr(resolved)
