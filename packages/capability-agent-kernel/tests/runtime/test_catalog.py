from __future__ import annotations

import pytest

from capability_agent.runtime.catalog import ProviderCatalog, ProviderCatalogSource
from capability_agent.runtime.models import ConfigurationError


def test_provider_catalog_is_domain_neutral_and_accepts_registered_provider() -> None:
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

    assert isinstance(catalog, ProviderCatalogSource)
    assert catalog.provider("alpha").default_model == "alpha-model"


def _catalog(provider: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "schema_version": 1,
        "descriptor_version": "fixture-1",
        "default_provider": "alpha",
        "providers": {
            "alpha": provider
            or {
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


@pytest.mark.parametrize(
    "payload",
    [
        {**_catalog(), "schema_version": 2},
        {**_catalog(), "unexpected": True},
        {
            **_catalog(),
            "providers": {
                "alpha": {
                    **_catalog()["providers"]["alpha"],  # type: ignore[index]
                    "unexpected": True,
                }
            },
        },
    ],
)
def test_catalog_rejects_invalid_schema_and_unknown_fields(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ConfigurationError):
        ProviderCatalog.from_mapping(payload)


def test_catalog_rejects_unknown_provider_and_keeps_provider_map_detached() -> None:
    catalog = ProviderCatalog.from_mapping(_catalog())
    with pytest.raises(ConfigurationError, match="unknown provider"):
        catalog.provider("unknown")
    with pytest.raises(TypeError):
        catalog.providers["beta"] = catalog.providers["alpha"]  # type: ignore[index]


def test_catalog_rejects_duplicate_allowed_models() -> None:
    provider = dict(_catalog()["providers"]["alpha"])  # type: ignore[index]
    provider["allowed_models"] = ["alpha-model", "alpha-model"]
    with pytest.raises(ConfigurationError, match="duplicates"):
        ProviderCatalog.from_mapping(_catalog(provider))
