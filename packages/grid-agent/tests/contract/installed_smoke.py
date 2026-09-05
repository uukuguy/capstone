from __future__ import annotations

import json
import shutil
import os
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from capability_agent.application.context_store import ApplicationContextStore
from capability_agent.application.manifest import ApplicationManifest
from capability_agent.application.output import JsonOutputRenderer
from capability_agent.application.profile import ApplicationProfile, CredentialScope, DataSharingPolicy, DomainBinding
from capability_agent.application.registry import DomainRegistry
from capability_agent.application.reporting import GenericReportShell
from capability_agent.application.runner import AgentApplication, ApplicationRequest
from capability_agent.application.workspace import ApplicationWorkspace

from capability_agent import DomainManifest, prepare_domain_runtime
from pandapower_domain import build_pandapower_profile
from inventory_domain import build_inventory_profile


class FakeExecutor:
    def __init__(self, environment: dict[str, object]) -> None:
        self.environment = environment
        self.calls: list[tuple[str, dict[str, object]]] = []

    def invoke(
        self, capability: str, arguments: dict[str, object]
    ) -> dict[str, object]:
        self.calls.append((capability, arguments))
        if capability != "environment.describe":
            raise AssertionError(f"unexpected simulator call: {capability}")
        if arguments:
            raise AssertionError(f"unexpected environment arguments: {arguments}")
        return self.environment


def inventory_application_smoke() -> None:
    """Exercise the public application SPI using only the fresh wheel install."""
    executable = Path(sys.executable).parent / ("inventoryctl.exe" if os.name == "nt" else "inventoryctl")
    assert executable.is_file(), "fresh interpreter must own inventoryctl"
    domain = build_inventory_profile()
    assert domain.missing_application_components() == ()
    assert domain.guide_provider is not None
    assert len(domain.guide_provider.load()) == 3

    class EmptyCredentials:
        def issue(self, *, binding_id, scope):
            assert binding_id == "inventory" and not scope.credential_names
            return SimpleNamespace(scope_id=scope.scope_id, credentials={})

    class Transport:
        def __init__(self, request, prepared, catalog):
            self.request = request
            self.binding = prepared.bindings["inventory"]
            self.tools = {tool.key.capability_id: tool for tool in catalog.domain_tools}
            self.effects = {doc["id"]: doc["context_effect"] for doc in self.binding.runtime.capability_documents}
            self.calls = []
            self.context_ref = None
            self.ordinal = 0
            self.sequence = 0
            self.started = self.stopped = False
            metadata = self.binding.endpoint.metadata
            local_script = Path(metadata["search_path"][0]) / metadata["executable"]
            assert local_script.read_bytes() == executable.read_bytes()

        def start(self):
            self.started = True

        def stop(self):
            self.stopped = True

        def prompt_and_wait(self, question, *, on_semantic_event, correlation_id, on_heartbeat):
            on_heartbeat()
            capabilities = ("catalog.open", "asset.list") if self.ordinal == 0 else ("stock.summary",)
            for capability in capabilities:
                arguments = {"catalog_id": "warehouse-a"} if capability == "catalog.open" else {"context_ref": self.context_ref}
                tool = self.tools[capability]
                identity = {
                    "call_id": f"installed-{len(self.calls) + 1}",
                    "run_id": self.request.run_id, "turn_id": correlation_id,
                    "tool_name": tool.name, "capability": capability,
                    "capability_key": {"binding_id": "inventory", "capability_id": capability},
                }
                self.sequence += 1
                on_semantic_event({**identity, "type": "tool_execution_start", "arguments": arguments}, self.sequence)
                result = self.binding.endpoint.executor.invoke(capability, arguments)
                self.calls.append((capability, result))
                self.context_ref = result["context_ref"]
                effect = self.effects[capability]
                self.sequence += 1
                on_semantic_event({
                    **identity, "type": "tool_result", "ok": True, "result": result,
                    "result_refs": [result["result_ref"]] if "result_ref" in result else [],
                    "evidence_refs": result.get("evidence_refs", []),
                    "projector_id": effect["projector"], "result_kind": effect["result_kind"],
                }, self.sequence)
            self.ordinal += 1
            return "The requested inventory operation has been processed."

    with tempfile.TemporaryDirectory(prefix="inventory-application-installed-") as scratch:
        workspace = ApplicationWorkspace.create(Path(scratch).resolve(), binding_ids=("inventory",))
        registry = DomainRegistry()
        registry.register(domain.manifest.domain_id, domain.manifest.version, lambda: domain)
        profile = ApplicationProfile(
            ApplicationManifest("inventory-installed", "1.0", "Installed inventory", "application-context/1.0", "application-result/1.0", "artifact/1.0", "agent_"),
            (DomainBinding("inventory", domain.manifest.tool_name_prefix, domain, CredentialScope(), DataSharingPolicy()),),
            JsonOutputRenderer(), SimpleNamespace(load=lambda: "Use the registered inventory authority."),
            GenericReportShell(), SimpleNamespace(cases=lambda: ()),
        )
        created = []

        def factory(*, request, profile, prepared_application, bindings, catalog):
            transport = Transport(request, prepared_application, catalog)
            created.append(transport)
            return transport

        outcome = AgentApplication(
            profile=profile, workspace=workspace, registry=registry,
            credentials=EmptyCredentials(), provider_factory=factory,
        ).run(ApplicationRequest(profile.manifest.application_id, ("List inventory assets.", "Summarize stock using the same context."), workspace.run_id))
        assert outcome.status == "completed", outcome.error
        assert outcome.completed_questions == 2
        transport, = created
        assert transport.started and transport.stopped
        assert [capability for capability, _ in transport.calls] == ["catalog.open", "asset.list", "stock.summary"]
        payload = json.loads(outcome.rendered)
        inventory = payload["domains"]["inventory"]["payload"]
        assert inventory["asset_result_refs"] == [transport.calls[1][1]["result_ref"]]
        assert inventory["stock_summary_refs"] == [transport.calls[2][1]["result_ref"]]
        assert inventory["report_artifact_ref"] == payload["core"]["report_ref"]
        assert len(payload["core"]["answer_refs"]) == 2
        assert outcome.report_path is not None
        report = outcome.report_path.read_text()
        assert "warehouse-a" in report and "Domain summary" in report
        assert str(transport.calls[2][1]["total_quantity_on_hand"]) in report
        assert ApplicationContextStore.replay(workspace).model_dump(mode="json") == json.loads(workspace.context_snapshot_path.read_text())


def main() -> None:
    profile = build_pandapower_profile()
    profile.manifest.assert_resources_present()
    assert isinstance(profile.manifest, DomainManifest)
    assert profile.manifest.protocol == "grid-capability"
    assert profile.manifest.executable_name == "gridctl"

    capability_documents = profile.contract_source.load()
    environment = {
        "protocol": profile.manifest.protocol,
        "protocol_version": profile.manifest.protocol_version,
        "executable_capabilities": [
            {
                "id": document["id"],
                "availability": document["availability"],
                "context_effect": document["context_effect"],
            }
            for document in capability_documents
            if document["availability"] == "published"
        ],
    }
    executor = FakeExecutor(environment)
    profile = replace(
        profile,
        executor_factory=lambda executable, workspace, timeout: executor,
    )

    with tempfile.TemporaryDirectory(prefix="grid-installed-smoke-") as scratch:
        workspace = Path(scratch)
        prepared = prepare_domain_runtime(
            profile,
            executable=workspace / "bin/gridctl",
            workspace=workspace / "run",
            tool_catalog_path=workspace / "run/tool-catalog.json",
            guide_index_path=workspace / "run/guide-index.json",
        )

        catalog = json.loads(
            prepared.tool_catalog_path.read_text(encoding="utf-8")
        )
        guide_index = json.loads(
            prepared.guide_index_path.read_text(encoding="utf-8")
        )
        assert executor.calls == [("environment.describe", {})]
        assert catalog["protocol"] == "grid-tool-catalog"
        assert any(tool["name"] == "grid_environment_describe" for tool in catalog["tools"])
        assert guide_index["protocol"] == "grid-guide-index"
        assert "overview" in guide_index["resources"]

    inventory_profile = build_inventory_profile()
    inventory_profile.manifest.assert_resources_present()
    assert inventory_profile.manifest.protocol == "inventory-capability"
    inventoryctl = shutil.which("inventoryctl")
    assert inventoryctl is not None

    with tempfile.TemporaryDirectory(prefix="inventory-installed-smoke-") as scratch:
        workspace = Path(scratch) / "run"
        workspace.mkdir()
        prepared = prepare_domain_runtime(
            inventory_profile,
            executable=Path(inventoryctl),
            workspace=workspace,
            tool_catalog_path=workspace / "tool-catalog.json",
            guide_index_path=workspace / "guide-index.json",
        )
        tool_names = [
            tool["name"]
            for tool in json.loads(
                prepared.tool_catalog_path.read_text(encoding="utf-8")
            )["tools"]
        ]
        assert tool_names == [
            "inventory_asset_get",
            "inventory_asset_list",
            "inventory_catalog_open",
            "inventory_stock_summary",
        ]

        executor = inventory_profile.executor_factory(
            Path(inventoryctl), workspace, 60.0
        )
        opened = executor.invoke("catalog.open", {"catalog_id": "warehouse-a"})
        result = executor.invoke(
            "asset.list", {"context_ref": opened["context_ref"], "limit": 2}
        )
        admitted = prepared.authority.admit(
            "asset.list", result, tuple(result["evidence_refs"])
        )
        assert len(admitted.results) == 1
        assert len(admitted.evidence) == len(set(result["evidence_refs"]))
        assert admitted.evidence

    inventory_application_smoke()
    print("installed-smoke: ok")


if __name__ == "__main__":
    main()
