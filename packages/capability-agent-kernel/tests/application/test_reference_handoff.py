"""A declared grant is required before a cross-binding reference is used."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from capability_agent.application.context_store import ApplicationContextStore
from capability_agent.application.profile import ReferenceGrant
from capability_agent.application.reference_handoff import (
    ReferenceHandoffError,
    ReferenceHandoffService,
    VerifiedTransferReference,
)
from capability_agent.application.workspace import ApplicationWorkspace


class SourceAuthority:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id

    def verify_transfer_reference(self, reference: str, kind: str) -> VerifiedTransferReference:
        if reference != "model:sha256:original" or kind != "model":
            raise ValueError("unknown model")
        return VerifiedTransferReference(reference, "original", self.run_id, "model-authority")


class TargetAuthority:
    def __init__(self) -> None:
        self.admitted = []

    def admit_handoff(self, receipt, *, source_workspace) -> None:
        assert source_workspace.name == "source"
        self.admitted.append(receipt)


class TargetExecutor:
    def __init__(self) -> None:
        self.calls = []

    def invoke(self, capability, arguments):
        self.calls.append((capability, arguments))
        return {"observed": True}


def _service(tmp_path, *, granted: bool):
    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="current", binding_ids=("source", "target")
    )
    store = ApplicationContextStore.initialize(workspace)
    source = SourceAuthority(workspace.run_id)
    target = TargetAuthority()
    executor = TargetExecutor()
    grant = ReferenceGrant("source", "target", "model", "inspect", "model.read")
    profile = SimpleNamespace(reference_grants=(grant,) if granted else ())
    bindings = {
        "source": SimpleNamespace(runtime=SimpleNamespace(authority=source)),
        "target": SimpleNamespace(
            runtime=SimpleNamespace(
                authority=target,
                capability_documents=({"id": "model.read.inspect"},),
            ),
            endpoint=SimpleNamespace(executor=executor),
        ),
    }
    return ReferenceHandoffService(profile, workspace, store, bindings), store, target, executor


def test_default_deny_has_no_target_call_or_decision(tmp_path) -> None:
    service, store, target, executor = _service(tmp_path, granted=False)

    with pytest.raises(ReferenceHandoffError, match="grant"):
        service.invoke_target(
            source_binding_id="source", target_binding_id="target",
            reference="model:sha256:original", reference_kind="model",
            purpose="inspect", capability="model.read.inspect", arguments={},
        )

    assert target.admitted == executor.calls == []
    assert store.snapshot.core.decisions == ()


def test_grant_records_receipt_before_target_and_replay_verifies_it(tmp_path) -> None:
    service, store, target, executor = _service(tmp_path, granted=True)

    result, receipt = service.invoke_target(
        source_binding_id="source", target_binding_id="target",
        reference="model:sha256:original", reference_kind="model",
        purpose="inspect", capability="model.read.inspect", arguments={"detail": "brief"},
    )

    assert result == {"observed": True}
    assert len(target.admitted) == len(executor.calls) == 1
    assert executor.calls[0][1] == {
        "detail": "brief", "reference": receipt.reference,
        "handoff_ref": receipt.receipt_ref,
    }
    assert store.snapshot.core.decisions[0]["receipt_ref"] == receipt.receipt_ref
    assert service.verify_receipt(receipt) == receipt
    with pytest.raises(ReferenceHandoffError):
        service.verify_receipt(replace(receipt, target_binding_id="other"))


def test_foreign_run_and_wrong_capability_fail_before_target(tmp_path) -> None:
    service, _store, target, executor = _service(tmp_path, granted=True)
    service.bindings["source"].runtime.authority.run_id = "other"

    with pytest.raises(ReferenceHandoffError, match="run"):
        service.invoke_target(
            source_binding_id="source", target_binding_id="target",
            reference="model:sha256:original", reference_kind="model",
            purpose="inspect", capability="model.read.inspect", arguments={},
        )
    with pytest.raises(ReferenceHandoffError, match="grant"):
        service.invoke_target(
            source_binding_id="source", target_binding_id="target",
            reference="model:sha256:original", reference_kind="model",
            purpose="inspect", capability="model.write.derive", arguments={},
        )
    assert target.admitted == executor.calls == []
