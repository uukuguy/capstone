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


def test_recognition_role_selection_does_not_mutate_execution_configuration(tmp_path):
    from capstone_agent.runtime import resolve_recognition_llm
    (tmp_path / "configs").mkdir()
    catalog = Path(__file__).resolve().parents[3] / "configs/llm-providers.json"
    (tmp_path / "configs/llm-providers.json").write_text(catalog.read_text())
    environment = {"CAPABILITY_AGENT_LLM_PROVIDER": "deepseek", "CAPABILITY_AGENT_LLM_MODEL": "execution-model",
        "DEEPSEEK_API_KEY": "synthetic-test-credential"}
    execution = resolve_harness_llm(tmp_path, dict(environment))
    assert resolve_recognition_llm(tmp_path, environment, execution) is execution
    environment["CAPSTONE_RECOGNITION_MODEL"] = "recognition-model"
    recognized = resolve_recognition_llm(tmp_path, environment, execution)
    assert recognized.config.provider == "deepseek" and recognized.config.model == "recognition-model"
    assert execution.config.model == environment["CAPABILITY_AGENT_LLM_MODEL"] == "execution-model"


def test_provider_only_recognition_uses_catalog_defaults_not_execution_dotenv(tmp_path):
    from capstone_agent.runtime import resolve_recognition_llm
    (tmp_path / "configs").mkdir()
    catalog = Path(__file__).resolve().parents[3] / "configs/llm-providers.json"
    (tmp_path / "configs/llm-providers.json").write_text(catalog.read_text())
    (tmp_path / '.env').write_text('CAPABILITY_AGENT_LLM_MODEL=execution-model\nCAPABILITY_AGENT_LLM_BASE_URL=https://execution.invalid\nCAPABILITY_AGENT_LLM_API_KEY_ENV=EXECUTION_KEY\n')
    environment = {"CAPABILITY_AGENT_LLM_PROVIDER": "deepseek", "CAPABILITY_AGENT_LLM_MODEL": "execution-model",
        "CAPABILITY_AGENT_LLM_BASE_URL": "https://execution.invalid", "CAPABILITY_AGENT_LLM_API_KEY_ENV": "EXECUTION_KEY",
        "EXECUTION_KEY": "synthetic", "OPENAI_API_KEY": "synthetic-recognition", "CAPSTONE_RECOGNITION_PROVIDER": "openai"}
    execution = resolve_harness_llm(tmp_path, dict(environment))
    recognized = resolve_recognition_llm(tmp_path, environment, execution)
    assert recognized.config.provider == 'openai' and recognized.config.model == 'gpt-5.5'
    assert recognized.config.base_url == 'https://api.openai.com/v1'
    assert recognized.secret.value == 'synthetic-recognition'
    assert execution.config.model == 'execution-model'
