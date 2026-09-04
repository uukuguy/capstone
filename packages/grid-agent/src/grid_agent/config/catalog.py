"""Versioned compatibility adapter for the historical provider catalog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from capability_agent.runtime.catalog import (
    ProviderAuth,
    ProviderCatalog as _ProviderCatalog,
    ProviderDescriptor,
)
from capability_agent.runtime.models import ConfigurationError


APPROVED_PROVIDERS = frozenset(
    {"openai", "openrouter", "deepseek", "openai-codex", "minimax"}
)


class ProviderCatalog(_ProviderCatalog):
    """Read the v1 provider descriptor through the generic catalog parser."""

    @classmethod
    def load(
        cls, path: Path | None = None, *,
        required_providers: frozenset[str] | set[str] | None = None,
    ) -> "ProviderCatalog":
        return cls.from_mapping(_load_json(path), required_providers=required_providers)

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any],
        *,
        required_providers: frozenset[str] | set[str] | None = None,
    ) -> "ProviderCatalog":
        del required_providers
        return super().from_mapping(
            _with_legacy_public_headers(raw), required_providers=APPROVED_PROVIDERS
        )


def _load_json(path: Path | None) -> Mapping[str, Any]:
    catalog_path = path or Path(__file__).resolve().parents[5] / "configs" / "llm-providers.json"
    try:
        value = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConfigurationError("provider catalog could not be loaded") from exc
    if not isinstance(value, Mapping):
        raise ConfigurationError("provider catalog must be an object")
    return value


def _with_legacy_public_headers(raw: Mapping[str, Any]) -> Mapping[str, Any]:
    """Add the v1 header environment mapping at the compatibility boundary."""

    providers = raw.get("providers")
    if not isinstance(providers, Mapping):
        return raw
    enriched: dict[str, Any] = dict(raw)
    enriched_providers: dict[str, Any] = {}
    header_env = {
        "openai": {
            "OpenAI-Organization": "GRID_AGENT_OPENAI_ORGANIZATION",
            "OpenAI-Project": "GRID_AGENT_OPENAI_PROJECT",
        },
        "openrouter": {
            "HTTP-Referer": "GRID_AGENT_OPENROUTER_HTTP_REFERER",
            "X-Title": "GRID_AGENT_OPENROUTER_APP_NAME",
        },
    }
    for name, descriptor in providers.items():
        if not isinstance(descriptor, Mapping):
            enriched_providers[name] = descriptor
            continue
        item = dict(descriptor)
        if name in header_env:
            item.setdefault("public_header_env", header_env[name])
        enriched_providers[name] = item
    enriched["providers"] = enriched_providers
    return enriched


__all__ = [
    "APPROVED_PROVIDERS",
    "ConfigurationError",
    "ProviderAuth",
    "ProviderCatalog",
    "ProviderDescriptor",
]
