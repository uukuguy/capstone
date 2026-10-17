from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("host_runtime", ROOT / "deploy/launch_host_runtime.py")
assert SPEC and SPEC.loader
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)


def environment(application="capstone", stage="local"):
    return {"CAPSTONE_RUNTIME_PROFILE": "capstone-workbench-v1",
            "CAPSTONE_DEPLOYMENT_STAGE": stage,
            "CAPSTONE_HOSTED_APPLICATION": application,
            "DEEPSEEK_API_KEY": "test-value-never-log"}


def trial_environment(application="capstone", **overrides):
    return environment(application) | {"CAPSTONE_RUNTIME_PROFILE": "capstone-dev-trial-v1"} | overrides


@pytest.mark.parametrize("application,command", [("capstone", "api"), ("pandapower", "worker"), ("pypsa", "worker")])
def test_local_trial_defaults_to_registry_deepseek(application, command):
    contract, _, _, selected = RUNTIME.select_runtime(ROOT, trial_environment(application), command)
    assert contract["profile"] == "capstone-dev-trial-v1"
    assert selected["CAPSTONE_PUBLIC_PROVIDER"] == "deepseek"
    assert selected["CAPSTONE_PUBLIC_MODEL"] == "deepseek-flash"


@pytest.mark.parametrize("application,command", [("capstone", "api"), ("pandapower", "worker"), ("pypsa", "worker")])
def test_local_trial_selects_openai_with_its_registered_default_model(application, command):
    import json
    registry = json.loads((ROOT / "configs/llm-providers.json").read_text())
    settings = trial_environment(application, CAPSTONE_PUBLIC_PROVIDER="openai", OPENAI_API_KEY="test-openai-never-log")
    selected = RUNTIME.select_runtime(ROOT, settings, command)[3]
    assert selected["CAPSTONE_PUBLIC_PROVIDER"] == "openai"
    assert selected["CAPSTONE_PUBLIC_MODEL"] == registry["providers"]["openai"]["default_model"]


def test_local_trial_requires_the_selected_key_not_another_provider_key():
    settings = trial_environment("pandapower", CAPSTONE_PUBLIC_PROVIDER="openai")
    with pytest.raises(ValueError, match="^OPENAI_API_KEY$"):
        RUNTIME.select_runtime(ROOT, settings, "worker")
    settings["CAPSTONE_HOSTED_APPLICATION"] = "capstone"
    RUNTIME.select_runtime(ROOT, settings, "api")


@pytest.mark.parametrize("key,value", [
    ("CAPSTONE_PUBLIC_PROVIDER", "unregistered-private-value"),
    ("CAPSTONE_PUBLIC_MODEL", "bad model private-value"),
    ("CAPSTONE_PUBLIC_MODEL", ""),
    ("CAPSTONE_DEPLOYMENT_STAGE", "cloud-development"),
    ("CAPSTONE_DEPLOYMENT_STAGE", "user-trial"),
    ("CAPSTONE_THREAD_CONTEXT_LIMIT", "4"),
])
def test_local_trial_keeps_other_contract_fields_and_selection_bounded(key, value):
    with pytest.raises(ValueError) as error:
        RUNTIME.select_runtime(ROOT, trial_environment(**{key: value}), "api")
    assert str(error.value) == key
    assert value not in str(error.value) or value == ""


def test_local_trial_can_choose_a_bounded_model_identifier_without_an_api_probe():
    settings = trial_environment("pandapower", CAPSTONE_PUBLIC_PROVIDER="openai",
                                 CAPSTONE_PUBLIC_MODEL="gpt-5-mini", OPENAI_API_KEY="test-never-log")
    assert RUNTIME.select_runtime(ROOT, settings, "worker")[3]["CAPSTONE_PUBLIC_MODEL"] == "gpt-5-mini"


def test_startup_logs_the_same_secret_free_receipt_saved_for_acceptance(tmp_path, monkeypatch, capsys):
    import json
    import os
    contract, role, spec, settings = RUNTIME.select_runtime(ROOT, environment("pandapower"), "worker")
    contract_path = tmp_path / "configs/runtime/host-runtime-v1.json"
    contract_path.parent.mkdir(parents=True)
    contract_path.write_bytes((ROOT / "configs/runtime/host-runtime-v1.json").read_bytes())
    monkeypatch.setattr(RUNTIME, "__file__", str(tmp_path / "deploy/launch_host_runtime.py"))
    monkeypatch.setattr(RUNTIME.sys, "argv", ["launch_host_runtime.py", "worker"])
    monkeypatch.setattr(RUNTIME, "select_runtime", lambda *args: (contract, role, spec, settings))
    monkeypatch.setattr(RUNTIME, "artifact_identity", lambda *args, **kwargs: "verified-artifact")

    class RuntimeStarted(Exception):
        pass

    def start(*args):
        raise RuntimeStarted

    monkeypatch.setattr(os, "execve", start)
    with pytest.raises(RuntimeStarted):
        RUNTIME.main()
    output = capsys.readouterr()
    line = next(line for line in output.err.splitlines() if line.startswith("Host runtime receipt: "))
    receipt = json.loads(line.removeprefix("Host runtime receipt: "))
    assert receipt == json.loads((tmp_path / ".capstone-agent/host-runtime.json").read_text())
    assert receipt["source_artifact_sha256"] == "verified-artifact"
    assert "test-value-never-log" not in output.err + output.out
    assert "DEEPSEEK_API_KEY" not in output.err + output.out


@pytest.mark.parametrize("application,command", [("capstone", "api"), ("pandapower", "worker"), ("pypsa", "worker")])
def test_local_and_cloud_select_same_runtime(application, command):
    local = RUNTIME.select_runtime(ROOT, environment(application), command)
    cloud = RUNTIME.select_runtime(ROOT, environment(application, "cloud-development"), command)
    assert local[:3] == cloud[:3]
    for key in local[0]["shared_environment"]:
        assert local[3][key] == cloud[3][key]
    assert local[2]["module"]


def test_model_context_retention_uses_memory_pressure_instead_of_short_idle_expiry():
    selected = RUNTIME.select_runtime(ROOT, environment('pandapower'), 'worker')[3]
    assert selected['CAPSTONE_THREAD_CONTEXT_IDLE_SECONDS'] == '0'
    assert int(selected['CAPSTONE_THREAD_CONTEXT_LIMIT']) > 4


def test_compose_does_not_duplicate_model_context_contract_defaults():
    compose = (ROOT / 'compose.yaml').read_text()
    assert 'CAPSTONE_THREAD_CONTEXT_LIMIT:' not in compose
    assert 'CAPSTONE_THREAD_CONTEXT_IDLE_SECONDS:' not in compose


@pytest.mark.parametrize("key,value", [
    ("CAPSTONE_PUBLIC_MODEL", "different-model"),
    ("CAPSTONE_FEDERATED_CATALOG_CONTEXT", "false"),
    ("CAPSTONE_DEPLOYMENT_STAGE", "production"),
    ("CAPSTONE_THREAD_VALIDATION", "m11"),
    ("GRID_AGENT_LLM_BASE_URL", "https://different.invalid"),
])
def test_runtime_rejects_configuration_drift_without_values(key, value):
    with pytest.raises(ValueError) as error:
        RUNTIME.select_runtime(ROOT, environment() | {key: value}, "api")
    assert str(error.value) == key
    assert value not in str(error.value)


def test_worker_requires_provider_but_api_does_not():
    selected = environment("pypsa")
    selected.pop("DEEPSEEK_API_KEY")
    with pytest.raises(ValueError, match="^DEEPSEEK_API_KEY$"):
        RUNTIME.select_runtime(ROOT, selected, "worker")
    selected["CAPSTONE_HOSTED_APPLICATION"] = "capstone"
    RUNTIME.select_runtime(ROOT, selected, "api")


@pytest.mark.parametrize("application,command", [("capstone", "api"), ("pandapower", "worker"), ("pypsa", "worker")])
def test_research_candidate_is_explicit_and_shared_by_host_roles(application, command):
    settings = environment(application)
    assert RUNTIME.select_runtime(ROOT, settings, command)[3]["CAPSTONE_AUTONOMOUS_RESEARCH"] == "0"
    assert RUNTIME.select_runtime(ROOT, settings | {"CAPSTONE_AUTONOMOUS_RESEARCH": "1"}, command)[3]["CAPSTONE_AUTONOMOUS_RESEARCH"] == "1"
    with pytest.raises(ValueError, match="^CAPSTONE_AUTONOMOUS_RESEARCH$"):
        RUNTIME.select_runtime(ROOT, settings | {"CAPSTONE_AUTONOMOUS_RESEARCH": "true"}, command)


def test_trial_promotion_can_select_the_same_runtime_without_source_changes():
    local = RUNTIME.select_runtime(ROOT, environment(), "api")
    trial = RUNTIME.select_runtime(ROOT, environment(stage="user-trial"), "api")
    assert local[:3] == trial[:3]
    assert local[3]["CAPSTONE_PUBLIC_MODEL"] == trial[3]["CAPSTONE_PUBLIC_MODEL"]


@pytest.mark.parametrize("application,command", [("capstone", "worker"), ("pandapower", "api"), ("api", "worker"), ("api", "api"), ("unknown", "worker")])
def test_runtime_rejects_unregistered_role_combinations(application, command):
    with pytest.raises(ValueError, match="CAPSTONE_HOSTED_APPLICATION/command"):
        RUNTIME.select_runtime(ROOT, environment(application), command)


def test_api_waits_for_both_workers_and_bounds_wait():
    contract = RUNTIME.select_runtime(ROOT, trial_environment(), "api")[0]
    settings = environment() | {"CAPSTONE_FAMILY_HEALTH_URLS": "pandapower=http://pp,pypsa=http://py"}
    elapsed = [0]
    seen = []

    def sleep(seconds):
        elapsed[0] += seconds

    def probe(url):
        seen.append(url)
        return url == "http://pp/health" or elapsed[0] >= 2

    RUNTIME.wait_for_workers(contract, settings, probe=probe, clock=lambda: elapsed[0], sleep=sleep)
    assert elapsed[0] == 2
    assert set(seen[-2:]) == {"http://pp/health", "http://py/health"}
    with pytest.raises(ValueError, match="startup deadline"):
        RUNTIME.wait_for_workers(contract, settings, probe=lambda url: False,
                                 clock=lambda: elapsed[0], sleep=sleep)
    assert elapsed[0] >= contract["startup"]["timeout_seconds"]


def test_api_wakes_both_cold_workers_concurrently():
    import threading
    contract = RUNTIME.select_runtime(ROOT, trial_environment(), 'api')[0]
    barrier = threading.Barrier(2)
    seen = []
    def probe(url):
        seen.append(url)
        barrier.wait(timeout=1)
        return True
    RUNTIME.wait_for_workers(contract,
        {'CAPSTONE_FAMILY_HEALTH_URLS': 'pandapower=http://pp,pypsa=http://py'}, probe=probe)
    assert set(seen) == {'http://pp/health', 'http://py/health'}


def test_workbench_native_conversation_does_not_wait_for_professional_authorities():
    contract, role, spec, selected = RUNTIME.select_runtime(ROOT, environment('native'), 'worker')
    assert role == 'native'
    assert spec['module'] == 'capstone_agent.native_hosted_worker'
    assert 'family' not in spec
    seen = []
    RUNTIME.wait_for_workers(contract, {'CAPSTONE_FAMILY_HEALTH_URLS':
        'native=http://native,pandapower=http://pp,pypsa=http://py'},
        probe=lambda url: seen.append(url) or url == 'http://native/health')
    assert seen == ['http://native/health']


def test_installed_catalog_payload_is_part_of_runtime_identity(tmp_path):
    import json
    (tmp_path / 'configs').mkdir()
    (tmp_path / 'packages').mkdir()
    (tmp_path / 'deploy').mkdir()
    for name in ['Dockerfile', 'deploy/entrypoint.sh', 'deploy/launch_host_runtime.py', 'deploy/bake_catalog_snapshot.py']:
        (tmp_path / name).write_text('fixed source')
    models = tmp_path / 'models'
    models.mkdir()
    for number in range(6):
        (models / f'{number}.nc').write_bytes(b'fixed asset')
    directory = tmp_path / '.capstone-agent'
    directory.mkdir()
    path = directory / 'federated-catalog.json'
    snapshot = {'schema': 'capstone-federated-catalog-snapshot/1', 'documents': [{'model': 'original'}]}
    path.write_text(json.dumps(snapshot))
    original = RUNTIME.artifact_identity(tmp_path, models)
    source = RUNTIME.artifact_identity(tmp_path, models, include_catalog=False)
    snapshot['artifact_sha256'] = original
    path.write_text(json.dumps(snapshot))
    assert RUNTIME.artifact_identity(tmp_path, models) == original
    snapshot['documents'][0]['model'] = 'changed'
    path.write_text(json.dumps(snapshot))
    assert RUNTIME.artifact_identity(tmp_path, models) != original
    assert RUNTIME.artifact_identity(tmp_path, models, include_catalog=False) == source


@pytest.mark.parametrize("origins", ["", "pandapower=http://pp", "pandapower=http://pp,pypsa=http://py,pypsa=http://other"])
def test_api_rejects_incomplete_or_duplicate_worker_bindings(origins):
    contract = RUNTIME.select_runtime(ROOT, environment(), "api")[0]
    with pytest.raises(ValueError, match="^CAPSTONE_FAMILY_HEALTH_URLS$"):
        RUNTIME.wait_for_workers(contract, {"CAPSTONE_FAMILY_HEALTH_URLS": origins})


def test_alignment_gate_rejects_cloud_artifact_and_stage_drift():
    spec = importlib.util.spec_from_file_location("runtime_gate", ROOT / "deploy/verify_host_runtime.py")
    assert spec and spec.loader
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    contract = RUNTIME.select_runtime(ROOT, environment(), "api")[0]
    def receipts(stage):
        return {role: {"schema": "capstone-host-runtime-receipt/1", "profile": contract["profile"],
                       "role": role, "application": value["application"], "stage": stage,
                       "dependencies_ready": True, "provider_configured": role != "api",
                       "contract_sha256": "same-contract", "artifact_sha256": "same-artifact",
                       "source_artifact_sha256": "same-source", "architecture": "aarch64"}
                for role, value in contract["roles"].items()}
    local, cloud = receipts("local"), receipts("cloud-development")
    gate.verify(local, cloud, contract, "same-contract")
    cloud["pypsa"]["artifact_sha256"] = "other-artifact"
    with pytest.raises(ValueError, match="artifact hashes differ"):
        gate.verify(local, cloud, contract, "same-contract")
    cloud = receipts("local")
    with pytest.raises(ValueError, match="receipt differs"):
        gate.verify(local, cloud, contract, "same-contract")
    with pytest.raises(ValueError, match="contract hashes differ"):
        gate.verify(local, receipts("cloud-development"), contract, "new-contract")
    cloud = receipts('cloud-development')
    for receipt in cloud.values():
        receipt.update(architecture='x86_64', artifact_sha256='cloud-installed-artifact')
    gate.verify(local, cloud, contract, 'same-contract')
    cloud['api']['source_artifact_sha256'] = 'changed-source'
    with pytest.raises(ValueError, match='source artifact hashes differ'):
        gate.verify(local, cloud, contract, 'same-contract')
