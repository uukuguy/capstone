"""A real model revision crosses only an application-granted read boundary."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_real_revision_is_admitted_by_target_authority(tmp_path) -> None:
    from capability_agent.application.context_store import ApplicationContextStore
    from capability_agent.application.profile import ReferenceGrant
    from capability_agent.application.reference_handoff import (
        ReferenceHandoffError, ReferenceHandoffService,
    )
    from capability_agent.application.workspace import ApplicationWorkspace
    from pypsa_model_authority.references import verify_model
    from pypsa_network_modeling.authority import PypsaModelArtifactAuthority
    from pypsa_network_modeling.execution import ModelctlExecutor

    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="real-handoff", binding_ids=("model", "receiver")
    )
    store = ApplicationContextStore.initialize(workspace)
    source_root = workspace.domain_roots["model"]
    target_root = workspace.domain_roots["receiver"]
    executable = Path(sys.executable).parent / "pypsamodelctl"
    source_executor = ModelctlExecutor(executable=executable, workspace=source_root)
    opened = source_executor.invoke("model.open", {"catalog_id": "two-bus"})

    class Receiver:
        def __init__(self) -> None:
            self.calls = 0

        def invoke(self, capability, arguments):
            self.calls += 1
            assert capability == "model.read.inspect"
            revision = verify_model(source_root, workspace.run_id, arguments["reference"])
            assert revision.document["catalog_id"] == "two-bus"
            return {"parent_ref": revision.document["parent_ref"]}

    receiver = Receiver()
    bindings = {
        "model": SimpleNamespace(runtime=SimpleNamespace(
            authority=PypsaModelArtifactAuthority(source_root)
        )),
        "receiver": SimpleNamespace(
            runtime=SimpleNamespace(
                authority=PypsaModelArtifactAuthority(target_root),
                capability_documents=({"id": "model.read.inspect"},),
            ),
            endpoint=SimpleNamespace(executor=receiver),
        ),
    }
    profile = SimpleNamespace(reference_grants=(
        ReferenceGrant("model", "receiver", "model", "inspect", "model.read"),
    ))
    service = ReferenceHandoffService(profile, workspace, store, bindings)
    result, receipt = service.invoke_target(
        source_binding_id="model", target_binding_id="receiver",
        reference=opened["model_ref"], reference_kind="model",
        purpose="inspect", capability="model.read.inspect", arguments={},
    )

    assert result == {"parent_ref": None}
    assert receipt.revision_digest == opened["model_ref"].split(":")[-1]
    assert receiver.calls == 1
    assert service.verify_receipt(receipt) == receipt
    with pytest.raises(ReferenceHandoffError, match="source authority"):
        service.invoke_target(
            source_binding_id="model", target_binding_id="receiver",
            reference="pypsa-model:sha256:" + "0" * 64,
            reference_kind="model", purpose="inspect",
            capability="model.read.inspect", arguments={},
        )
    assert receiver.calls == 1
