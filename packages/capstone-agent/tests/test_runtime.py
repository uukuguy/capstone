from __future__ import annotations

from pathlib import Path

import pytest

from capstone_agent.harness import HarnessRuntimeConfigurationError
from capstone_agent.runtime import load_runtime_environment, resolve_harness_llm


def test_harness_provider_resolution_classifies_configuration_without_raw_details(tmp_path: Path) -> None:
    (tmp_path / "configs").mkdir()
    catalog = Path(__file__).resolve().parents[3] / "configs/llm-providers.json"
    (tmp_path / "configs/llm-providers.json").write_text(catalog.read_text())
    environment = {"CAPABILITY_AGENT_LLM_API_KEY_ENV": "MISSING_TEST_CREDENTIAL"}
    with pytest.raises(HarnessRuntimeConfigurationError) as caught:
        resolve_harness_llm(tmp_path, environment)
    assert str(caught.value) == "Thread runtime configuration is invalid"
    assert "MISSING_TEST_CREDENTIAL" not in str(caught.value)
    assert environment["CAPABILITY_AGENT_LLM_PROVIDER"] == "deepseek"
    assert environment["CAPABILITY_AGENT_LLM_MODEL"] == "deepseek-flash"
    assert caught.value.__suppress_context__


def test_harness_provider_resolution_preserves_explicit_application_selection(tmp_path: Path) -> None:
    (tmp_path / "configs").mkdir()
    catalog = Path(__file__).resolve().parents[3] / "configs/llm-providers.json"
    (tmp_path / "configs/llm-providers.json").write_text(catalog.read_text())
    environment = {
        "CAPSTONE_PUBLIC_PROVIDER": "openai",
        "CAPSTONE_PUBLIC_MODEL": "stage-model",
        "CAPABILITY_AGENT_LLM_PROVIDER": "deepseek",
        "CAPABILITY_AGENT_LLM_MODEL": "explicit-model",
        "DEEPSEEK_API_KEY": "synthetic-test-credential",
    }
    resolved = resolve_harness_llm(tmp_path, environment)
    assert resolved.config.provider == "deepseek"
    assert resolved.config.model == "explicit-model"


def test_runtime_environment_loads_project_dotenv_and_adapts_legacy_llm_names(tmp_path) -> None:
    (tmp_path / ".env").write_text(
        "GRID_AGENT_LLM_PROVIDER=deepseek\n"
        "GRID_AGENT_LLM_MODEL=deepseek-flash\n",
        encoding="utf-8",
    )

    environment = load_runtime_environment(
        tmp_path,
        {"OPENAI_API_KEY": "placeholder", "GRID_AGENT_LLM_MODEL": "process-model"},
    )

    assert environment["GRID_AGENT_LLM_PROVIDER"] == "deepseek"
    assert environment["GRID_AGENT_LLM_MODEL"] == "process-model"
    assert environment["CAPABILITY_AGENT_LLM_PROVIDER"] == "deepseek"
    assert environment["CAPABILITY_AGENT_LLM_MODEL"] == "process-model"
