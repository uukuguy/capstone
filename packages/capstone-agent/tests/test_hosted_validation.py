from __future__ import annotations

import pytest


def test_validation_is_opt_in_and_requires_cloud_development():
    from capstone_agent.hosted_validation import validation_mode, select_validation_builder

    assert select_validation_builder({}, "pypsa") is None
    assert validation_mode({}) == "normal"
    for environment in (
        {"CAPSTONE_THREAD_VALIDATION": "unknown"},
        {"CAPSTONE_THREAD_VALIDATION": "m11"},
        {"CAPSTONE_THREAD_VALIDATION": "m11", "CAPSTONE_DEPLOYMENT_STAGE": "user-trial"},
    ):
        with pytest.raises(ValueError):
            select_validation_builder(environment, "pypsa")
    with pytest.raises(ValueError):
        select_validation_builder({"CAPSTONE_THREAD_VALIDATION": "m11",
                                   "CAPSTONE_DEPLOYMENT_STAGE": "cloud-development"}, "other")


def test_validation_preflight_requires_both_worker_identities(monkeypatch):
    import json
    from io import BytesIO
    import capstone_agent.hosted_validation as validation

    env = {"CAPSTONE_THREAD_VALIDATION": "m11", "CAPSTONE_DEPLOYMENT_STAGE": "cloud-development",
           "CAPSTONE_FAMILY_HEALTH_URLS": "pandapower=http://worker:8080,pypsa=http://worker-pypsa:8080"}
    mode = "m11-provider-free"
    family_override = None

    def response(url, *, timeout):
        assert timeout == 2
        family = "pypsa" if "worker-pypsa" in url else "pandapower"
        return BytesIO(json.dumps({"status": "ready", "runtime_mode": mode,
                                   "implementation_family": family_override or family}).encode())

    monkeypatch.setattr(validation, "urlopen", response)
    status = validation.build_validation_status(env)
    assert status is not None
    assert status()["families"] == ["pandapower", "pypsa"]
    mode = "normal"
    with pytest.raises(ValueError):
        status()
    mode = "m11-provider-free"
    family_override = "pandapower"
    with pytest.raises(ValueError):
        status()
    assert validation.build_validation_status({}) is None


def test_validation_preflight_is_private_and_fails_closed():
    from fastapi.testclient import TestClient
    from capstone_agent.host_api import create_host_app
    from capstone_agent.session import WorkerRegistry

    def unavailable():
        raise ValueError("worker mode mismatch")

    app = create_host_app(object(), WorkerRegistry(()), operator_token="test-secret",
                          allowed_hosts={"testserver"}, allowed_origins={"http://testserver"},
                          public_demo=True, validation_status=unavailable)
    with TestClient(app) as client:
        token = client.get("/api/v1/demo-credential").json()["token"]
        assert client.get("/api/v1/validation/m11", headers={"Authorization": f"Bearer {token}"}).status_code == 404
        assert client.get("/api/v1/validation/m11", headers={"Authorization": "Bearer test-secret"}).status_code == 503
