"""Installed-wheel two-binding reference handoff with a test-only receiver."""

from __future__ import annotations

import copy
import sys
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from capability_agent.application.composition import prepare_application
from capability_agent.application.context_store import ApplicationContextStore
from capability_agent.application.manifest import ApplicationManifest
from capability_agent.application.output import JsonOutputRenderer
from capability_agent.application.profile import (
    ApplicationProfile, CredentialScope, DataSharingPolicy, DomainBinding,
    ReferenceGrant,
)
from capability_agent.application.reference_handoff import ReferenceHandoffService
from capability_agent.application.registry import DomainRegistry
from capability_agent.application.reporting import GenericReportShell
from capability_agent.application.workspace import ApplicationWorkspace
from pypsa_model_authority.references import verify_evidence, verify_result
from pypsa_network_modeling.authority import PypsaModelArtifactAuthority
from pypsa_network_modeling.execution import ModelctlExecutor
from pypsa_network_modeling.profile import build_pypsa_network_modeling_profile


class ReceiverExecutor:
    def __init__(self, source_workspace: Path) -> None:
        self.source = ModelctlExecutor(
            executable=Path(sys.executable).parent / "pypsamodelctl",
            workspace=source_workspace,
        )

    def invoke(self, capability: str, arguments: dict[str, object]) -> dict[str, object]:
        if capability == "environment.describe":
            return {
                "protocol": "pypsa-model-capability", "protocol_version": "1.0",
                "executable_capabilities": [{"id": "reference.inspect"}],
            }
        if capability != "reference.inspect" or set(arguments) != {"reference", "handoff_ref"}:
            raise ValueError("receiver accepts only an admitted model reference")
        if not str(arguments["handoff_ref"]).startswith("handoff:sha256:"):
            raise ValueError("receiver requires an application receipt")
        return self.source.invoke("model.inspect", {"model_ref": arguments["reference"]})


class ReceiverProvisioner:
    def prepare(self, *, binding, workspace, credentials):
        if credentials.credentials or binding.binding_id != "receiver":
            raise ValueError("receiver preparation is invalid")
        return SimpleNamespace(
            executor=ReceiverExecutor(workspace.parent / "model"),
            metadata={"binding_id": binding.binding_id},
            close=lambda: None,
        )


class EmptyCredentials:
    def issue(self, *, binding_id, scope):
        return SimpleNamespace(scope_id=scope.scope_id, credentials={})


def main() -> None:
    model = build_pypsa_network_modeling_profile()
    inspect = next(item for item in model.contract_source.load() if item["id"] == "model.inspect")
    receiver_contract = copy.deepcopy(inspect)
    receiver_contract["id"] = "reference.inspect"
    receiver_contract["tool_name"] = "pypsa_receive_inspect"
    receiver_contract["input_schema"] = {
        "type": "object", "additionalProperties": False,
        "required": ["reference", "handoff_ref"],
        "properties": {
            "reference": {"type": "string", "minLength": 1},
            "handoff_ref": {"type": "string", "minLength": 1},
        },
    }
    receiver = replace(
        model,
        manifest=replace(
            model.manifest, domain_id="pypsa-test-receiver",
            display_name="PyPSA test receiver", tool_name_prefix="pypsa_receive_",
        ),
        contract_source=SimpleNamespace(load=lambda: (receiver_contract,)),
        provisioner=ReceiverProvisioner(),
        authority_factory=PypsaModelArtifactAuthority,
    )
    registry = DomainRegistry()
    registry.register(model.manifest.domain_id, model.manifest.version, lambda: model)
    registry.register(receiver.manifest.domain_id, receiver.manifest.version, lambda: receiver)

    with TemporaryDirectory() as temporary:
        workspace = ApplicationWorkspace.create(
            Path(temporary).resolve() / "runs", run_id="installed-pypsa",
            binding_ids=("model", "receiver"),
        )
        profile = ApplicationProfile(
            manifest=ApplicationManifest(
                "pypsa-conformance", "1.0", "PyPSA installed conformance",
                "application-context/1.0", "application-result/1.0", "artifact/1.0", "agent_",
            ),
            domains=(
                DomainBinding("model", "pypsa_model_", model, CredentialScope(), DataSharingPolicy()),
                DomainBinding("receiver", "pypsa_receive_", receiver, CredentialScope(), DataSharingPolicy()),
            ),
            output_renderer=JsonOutputRenderer(),
            application_policy=SimpleNamespace(load=lambda: "Use registered capabilities only."),
            report_shell=GenericReportShell(),
            acceptance_profile=SimpleNamespace(cases=lambda: ()),
            reference_grants=(ReferenceGrant("model", "receiver", "model", "inspect", "reference"),),
        )
        prepared = prepare_application(
            profile, registry=registry, workspace=workspace.root,
            credentials=EmptyCredentials(),
        )
        assert set(prepared.bindings) == {"model", "receiver"}
        assert {item["id"] for item in prepared.bindings["receiver"].runtime.capability_documents} == {
            "reference.inspect"
        }
        store = ApplicationContextStore.initialize(workspace)
        source = prepared.bindings["model"]
        opened = source.endpoint.executor.invoke("model.open", {"catalog_id": "two-bus"})
        derived = source.endpoint.executor.invoke("model.derive", {
            "model_ref": opened["model_ref"], "load_id": "demand", "p_set_mw": 55.0,
        })
        assert source.runtime.authority.verify_model(derived["model_ref"]).document["parent_ref"] == opened["model_ref"]
        service = ReferenceHandoffService(profile, workspace, store, prepared.bindings)
        inspected, receipt = service.invoke_target(
            source_binding_id="model", target_binding_id="receiver",
            reference=derived["model_ref"], reference_kind="model",
            purpose="inspect", capability="reference.inspect", arguments={},
        )
        assert inspected["load_p_set_mw"] == {"demand": 55.0}
        assert verify_result(workspace.domain_roots["model"], workspace.run_id, inspected["result_ref"])
        assert verify_evidence(workspace.domain_roots["model"], workspace.run_id, inspected["evidence_refs"][0])
        assert service.verify_receipt(receipt) == receipt
        assert ApplicationContextStore.replay(workspace.context_events_path) == store.snapshot
        for binding in prepared.bindings.values():
            binding.endpoint.close()
    print("installed-pypsa-model-handoff: ok")


if __name__ == "__main__":
    main()
