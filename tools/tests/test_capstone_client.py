"""One client request contract for the registered pandapower and PyPSA applications."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("capstone_client", ROOT / "tools/capstone_client.py")
assert SPEC is not None and SPEC.loader is not None
client = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(client)


def test_client_routes_pandapower_instructions_through_registered_application(tmp_path) -> None:
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=json.dumps({
            "schema": "capability-agent-output/1.0",
            "core": {"application_id": "pandapower-static-analysis", "run_id": "grid-run", "status": "completed", "answer_refs": ["a", "b"]},
            "domains": {"grid": {}},
        }), stderr="")

    result = client.run_request({
        "schema": "capstone-client-request/1.0",
        "application_id": "pandapower-static-analysis",
        "instructions": ["打开 IEEE-39 模型。", "运行交流潮流并报告网损。"],
    }, repo_root=ROOT, runner=run)

    assert result["application_id"] == "pandapower-static-analysis"
    assert result["run_id"] == "grid-run"
    command, options = calls[0]
    assert command[:5] == ["uv", "run", "--project", "packages/grid-agent", "grid-agent"]
    assert command[5:9] == ["analysis-generic", "--application", "pandapower-static-analysis", "--instructions"]
    assert options["cwd"] == ROOT
    assert "OPENAI_API_KEY" not in command


def test_client_routes_pypsa_case_to_separate_worker_without_provider_credentials() -> None:
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=json.dumps({
            "schema": "capstone-pypsa-case-presentation/1.0",
            "case_id": "regional-demand-stress", "run_id": "pypsa-run", "status": "completed",
            "turns": [{"answer": "a"}, {"answer": "b"}, {"answer": "c"}],
        }), stderr="")

    result = client.run_request({
        "schema": "capstone-client-request/1.0",
        "application_id": "pypsa-business-cases",
        "case_id": "regional-demand-stress",
        "instructions": ["one", "two", "three"],
    }, repo_root=ROOT, runner=run, environment={"PATH": "/bin", "HOME": "/tmp", "OPENAI_API_KEY": "secret"})

    assert result["run_id"] == "pypsa-run"
    command, options = calls[0]
    assert command[:5] == ["uv", "run", "--project", "packages/pypsa-power-operations-domain-pack", "python"]
    assert command[5:9] == ["validation/pypsa_cases.py", "run", "regional-demand-stress", "--instructions"]
    assert "OPENAI_API_KEY" not in options["env"]


def test_client_routes_pandapower_scripted_demo_without_provider_credentials() -> None:
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=json.dumps({
            "schema": "capability-agent-output/1.0",
            "core": {"application_id": "pandapower-static-analysis", "run_id": "grid-demo", "status": "completed", "answer_refs": ["a", "b", "c"]},
            "domains": {"grid": {}},
        }), stderr="")

    result = client.run_request({
        "schema": "capstone-client-request/1.0",
        "application_id": "pandapower-static-analysis",
        "mode": "scripted-demo",
        "case_id": "pandapower-scripted-task",
        "instructions": ["one", "two", "three"],
    }, repo_root=ROOT, runner=run, environment={"PATH": "/bin", "HOME": "/tmp", "OPENAI_API_KEY": "secret"})

    assert result["run_id"] == "grid-demo"
    command, options = calls[0]
    assert command[:5] == ["uv", "run", "--project", "packages/grid-agent", "python"]
    assert command[5:9] == ["tools/pandapower_scripted_demo.py", "--case", "pandapower-scripted-task", "--instructions"]
    assert "OPENAI_API_KEY" not in options["env"]


@pytest.mark.parametrize("client_request", [
    {"schema": "capstone-client-request/1.0", "application_id": "unknown", "instructions": ["hi"]},
    {"schema": "capstone-client-request/1.0", "application_id": "pandapower-static-analysis", "instructions": []},
    {"schema": "capstone-client-request/1.0", "application_id": "pypsa-business-cases", "instructions": ["hi"]},
    {"schema": "capstone-client-request/1.0", "application_id": "pypsa-business-cases", "case_id": "x", "instructions": ["hi"], "provider": "openai"},
    {"schema": "capstone-client-request/1.0", "application_id": "pandapower-static-analysis", "mode": "scripted-demo", "instructions": ["hi"]},
    {"schema": "capstone-client-request/1.0", "application_id": "pandapower-static-analysis", "mode": "", "instructions": ["hi"]},
])
def test_client_rejects_invalid_routes_before_starting_worker(client_request) -> None:
    with pytest.raises(ValueError):
        client.run_request(client_request, repo_root=ROOT, runner=lambda *args, **kwargs: pytest.fail("worker launched"))


def test_demo_requests_match_registered_instruction_sources() -> None:
    pandapower = json.loads((ROOT / "validation/client/pandapower-scripted-task.json").read_text())
    pandapower_source = json.loads((ROOT / "validation/application/pandapower-scripted-task.json").read_text())
    assert pandapower["instructions"] == [item["text"] for item in pandapower_source["questions"]]

    pypsa = json.loads((ROOT / "validation/client/pypsa-regional-demo.json").read_text())
    pypsa_source = json.loads((ROOT / "validation/pypsa-cases/cases.json").read_text())
    regional = next(item for item in pypsa_source["cases"] if item["id"] == pypsa["case_id"])
    assert pypsa["instructions"] == regional["introduction"]["demo_instructions"]


def test_client_rejects_malformed_worker_turns() -> None:
    def run(command, **kwargs):
        return SimpleNamespace(returncode=0, stdout=json.dumps({
            "schema": "capstone-pypsa-case-presentation/1.0",
            "case_id": "regional-demand-stress", "run_id": "pypsa-run", "status": "completed",
            "turns": None,
        }), stderr="")

    with pytest.raises(RuntimeError, match="does not match its request"):
        client.run_request({
            "schema": "capstone-client-request/1.0",
            "application_id": "pypsa-business-cases",
            "case_id": "regional-demand-stress",
            "instructions": ["one"],
        }, repo_root=ROOT, runner=run)
