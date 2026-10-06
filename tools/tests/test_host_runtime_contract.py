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


@pytest.mark.parametrize("application,command", [("capstone", "api"), ("pandapower", "worker"), ("pypsa", "worker")])
def test_local_and_cloud_select_same_runtime(application, command):
    local = RUNTIME.select_runtime(ROOT, environment(application), command)
    cloud = RUNTIME.select_runtime(ROOT, environment(application, "cloud-development"), command)
    assert local[:3] == cloud[:3]
    for key in local[0]["shared_environment"]:
        assert local[3][key] == cloud[3][key]
    assert local[2]["module"]


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
    contract = RUNTIME.select_runtime(ROOT, environment(), "api")[0]
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
    assert seen[-2:] == ["http://pp/health", "http://py/health"]
    with pytest.raises(ValueError, match="startup deadline"):
        RUNTIME.wait_for_workers(contract, settings, probe=lambda url: False,
                                 clock=lambda: elapsed[0], sleep=sleep)
    assert elapsed[0] >= contract["startup"]["timeout_seconds"]


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
                       "contract_sha256": "same-contract", "artifact_sha256": "same-artifact"}
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
