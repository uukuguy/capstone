"""Registered model browsing through the fixed gridctl capability contract."""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from capstone_agent.model_identity import validate_model_id
from .application.profile import build_pandapower_application_profile


def model_diagram(model_id: str, revision: str) -> dict[str, object]:
    validate_model_id(model_id)
    binding = build_pandapower_application_profile().domains[0]
    with TemporaryDirectory(prefix="capstone-grid-view-") as directory:
        endpoint = binding.profile.provisioner.prepare(binding=binding, workspace=Path(directory).resolve() / "grid",
            credentials=SimpleNamespace(scope_id=binding.credential_scope.scope_id, credentials={}))
        try:
            opened = endpoint.executor.invoke("context.open", {"model_id": model_id})
            if opened.get("revision_ref") != revision:
                raise ValueError("exact model revision is unavailable")
            topology = endpoint.executor.invoke("operator.diagram.get", {"context_ref": opened["context_ref"]})
            if topology.get("revision_ref") != revision or topology.get("context_ref") != opened["context_ref"]:
                raise ValueError("model diagram identity mismatch")
            return {"schema": "capstone-network-diagram/1.0",
                "model": {"id": model_id, "revision": revision, "source": "gridctl"},
                "coordinate_system": topology["coordinate_system"], "buses": topology["buses"], "branches": topology["branches"]}
        finally:
            endpoint.close()
