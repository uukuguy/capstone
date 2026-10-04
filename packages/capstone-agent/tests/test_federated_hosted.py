from __future__ import annotations

import json
import pytest

from capstone_agent.federated_hosted import load_federated_catalog_documents


def _manifest(family: str, model_id: str, profile_id: str) -> dict[str, object]:
    return {
        "schema": "capstone-federated-catalog/1",
        "default_model_id": model_id,
        "models": [{
            "model_id": model_id,
            "authority_model_ref": f"{family}:{model_id}",
            "display_name": model_id,
            "diagram_provider_id": family,
            "implementation_family": family,
            "revision_ref": "revision:sha256:" + ("a" if family == "pandapower" else "b") * 64,
        }],
        "profiles": [{
            "profile_id": profile_id,
            "profile_version": "1.0.0",
            "display_name": profile_id,
            "implementation_families": [family],
            "default": True,
        }],
    }


def test_load_federated_catalog_documents_uses_fixed_family_exporters(monkeypatch, tmp_path) -> None:
    manifests = {
        "pandapower": _manifest("pandapower", "ieee39", "pandapower-static-analysis"),
        "pypsa": _manifest("pypsa", "regional-six-bus", "pypsa-business-cases"),
    }
    calls: list[tuple[object, ...]] = []

    class FakeProcess:
        returncode = 0

        def __init__(self, command, **kwargs):
            calls.append(tuple(command))
            family = "pandapower" if "grid_agent" in " ".join(command) else "pypsa"
            kwargs["stdout"].write(json.dumps(manifests[family]).encode())

        def communicate(self, timeout=None):
            return b"", b""

        def poll(self):
            return self.returncode

        def kill(self):
            self.returncode = -9

        def wait(self):
            return self.returncode

    def fake_popen(command, **kwargs):
        return FakeProcess(command, **kwargs)

    monkeypatch.setattr("capstone_agent.federated_hosted.subprocess.Popen", fake_popen)
    documents = load_federated_catalog_documents(tmp_path)
    assert [document["default_model_id"] for document in documents] == ["ieee39", "regional-six-bus"]
    assert len(calls) == 2
    assert all("--shell" not in call for call in calls)


def test_load_federated_catalog_documents_rejects_failed_or_oversized_export(monkeypatch, tmp_path) -> None:
    class FailedProcess:
        returncode = 1
        def __init__(self, *args, **kwargs): pass
        def communicate(self, timeout=None): return b"", b"failure"
        def poll(self): return self.returncode
        def kill(self): pass
        def wait(self): return self.returncode

    monkeypatch.setattr("capstone_agent.federated_hosted.subprocess.Popen", FailedProcess)
    with pytest.raises(RuntimeError, match="catalog exporter failed"):
        load_federated_catalog_documents(tmp_path)

    class OversizedProcess(FailedProcess):
        returncode = 0
        def __init__(self, *args, **kwargs): kwargs["stdout"].write(b"x" * (512 * 1024 + 1))

    monkeypatch.setattr("capstone_agent.federated_hosted.subprocess.Popen", OversizedProcess)
    with pytest.raises(RuntimeError, match="too large"):
        load_federated_catalog_documents(tmp_path)
