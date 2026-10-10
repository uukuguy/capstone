"""Registered model browsing through the fixed PyPSA Authority contract."""

from pathlib import Path
from tempfile import TemporaryDirectory
from capstone_agent.application import EmptyCredentialBroker

from capstone_agent.model_identity import validate_model_id
from .profile import build_profile


def model_diagram(model_id: str, revision: str) -> dict[str, object]:
    validate_model_id(model_id)
    from .hosted import RegisteredPyPSAThreadCatalog
    if RegisteredPyPSAThreadCatalog().resolve(model_id).model_revision != revision:
        raise ValueError("exact registered model revision is unavailable")
    binding = next(binding for binding in build_profile().domains if binding.binding_id == "source")
    provisioner = binding.profile.provisioner
    if provisioner is None:
        raise RuntimeError("model diagram provisioner is unavailable")
    with TemporaryDirectory(prefix="capstone-pypsa-view-") as directory:
        endpoint = provisioner.prepare(binding=binding, workspace=Path(directory).resolve() / "model-view" / "domains" / "source",
            credentials=EmptyCredentialBroker().issue(binding_id=binding.binding_id, scope=binding.credential_scope))
        try:
            opened = endpoint.executor.invoke("model.open", {"catalog_id": model_id})
            model_ref = opened["model_ref"]
            topology = endpoint.executor.invoke("operator.diagram", {"model_ref": model_ref})
            if topology.get("model_ref") != model_ref:
                raise ValueError("model diagram identity mismatch")
            return {"schema": "capstone-network-diagram/1.0",
                "model": {"id": model_id, "revision": revision, "source": "pypsa"},
                "coordinate_system": topology["coordinate_system"], "buses": topology["buses"], "branches": topology["branches"]}
        finally:
            endpoint.close()
