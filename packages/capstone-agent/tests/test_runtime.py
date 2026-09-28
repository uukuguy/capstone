from __future__ import annotations

from capstone_agent.runtime import load_runtime_environment


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
