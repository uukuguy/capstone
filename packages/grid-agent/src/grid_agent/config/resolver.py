"""Legacy environment-name adapter for generic provider resolution."""

from __future__ import annotations

from capability_agent.runtime.models import ConfigurationError
from capability_agent.runtime.resolver import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT_SECONDS,
    resolve_llm as _resolve_llm,
)

ENV_PROVIDER = "GRID_AGENT_LLM_PROVIDER"
ENV_MODEL = "GRID_AGENT_LLM_MODEL"
ENV_BASE_URL = "GRID_AGENT_LLM_BASE_URL"
ENV_API_KEY_ENV = "GRID_AGENT_LLM_API_KEY_ENV"
ENV_TIMEOUT = "GRID_AGENT_LLM_TIMEOUT_SECONDS"
ENV_RETRIES = "GRID_AGENT_LLM_MAX_RETRIES"


def resolve_llm(**kwargs):
    return _resolve_llm(**kwargs, env_prefix="GRID_AGENT")


__all__ = [
    "ConfigurationError",
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
