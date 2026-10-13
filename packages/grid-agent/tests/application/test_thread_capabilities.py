from __future__ import annotations

import json
import sys
import shutil
from pathlib import Path
import pytest

from capstone_agent.model_capability import CapstoneModelCapabilityCatalog
from capstone_agent.model_capability_context import ModelCapabilityContextOwner
from capability_agent.runtime.environment import RuntimeHost
from capability_agent.runtime.models import ResolvedLLM, ResolvedLLMConfig, SecretValue
from capability_agent.runtime.lock import PiCommand, PiRuntimeIdentity
from capstone_agent.kernel_capability_preparation import (
    AuthorityModelBinding, KernelApplicationProfilePreparer,
)
from capstone_agent.thread_protocol import AttemptSnapshot, ModelContextSnapshot
from capstone_agent.thread_service import AttemptClaim
from capstone_agent.thread_service import InMemoryThreadService
from capstone_agent.thread_worker import run_pending_attempt
from capstone_model_capability_spi import ModelCapabilityRegistry
from capstone_model_capability_spi import ModelCapabilitySelection
from grid_agent.application.thread_capabilities import (
    PANDAPOWER_PROFILE_DESCRIPTOR,
    PreparedKernelPiRpcSessionBuilder,
    PreparedKernelPiSessionFactory,
    build_pandapower_thread_application,
    register_pandapower_capability,
)
from grid_simulator.engine import Pandapower340Engine
from grid_simulator.models import ModelRegistry


class _Session:
    def start(self) -> None:
        return None

    def prompt_and_wait(self, question: str, **kwargs: object) -> str:
        del question, kwargs
        return "answer"

    def stop(self) -> None:
        return None


def test_retained_model_workspace_reuses_real_results_after_resources_close(tmp_path):
    from grid_agent.application.profile import build_pandapower_application_profile
    revision = ModelRegistry(Pandapower340Engine()).trusted_revision_ref("ieee39")
    context = _claim(revision).model_context
    def bind(prepared, context):
        opened = prepared.bindings["grid"].runtime.executor.invoke("context.open", {"model_id": context.model_id})
        return AuthorityModelBinding("grid", context.model_id, opened["revision_ref"],
                                     context.implementation_family, opened["context_ref"])
    def prepare():
        return KernelApplicationProfilePreparer(workspace_root=tmp_path,
            model_binder=bind, retain_context_workspace=True)(build_pandapower_application_profile(), context)
    first = prepare()
    runtime = first.prepared_application.bindings["grid"].runtime
    calculated = runtime.executor.invoke("analysis.powerflow.ac.run", {"context_ref": first.model_binding.context_ref})
    original = runtime.authority.verify_result(calculated["result_ref"]).document
    first.close()
    second = prepare()
    try:
        assert second.workspace.root == first.workspace.root
        reopened = second.prepared_application.bindings["grid"].runtime
        assert reopened.authority.verify_result(calculated["result_ref"]).document == original
        evidence = reopened.executor.invoke("evidence.get", {"evidence_ref": calculated["evidence_refs"][0]})
        assert evidence["document"]["result_ref"] == calculated["result_ref"]
        assert reopened.authority.verify_result(calculated["result_ref"]).document == original
    finally:
        second.close()


def test_real_derived_powerflow_reaches_thread_result_projection(tmp_path):
    from capstone_agent.kernel_pi_session import _verify_bound_attempt_references, _build_result_projections
    from capstone_agent.thread_service import _terminal_result_projections
    revision = ModelRegistry(Pandapower340Engine()).trusted_revision_ref("ieee39")
    claim = _claim(revision)
    def bind(prepared, context):
        opened = prepared.bindings["grid"].runtime.executor.invoke("context.open", {"model_id": context.model_id})
        return AuthorityModelBinding("grid", context.model_id, opened["revision_ref"],
                                     context.implementation_family, opened["context_ref"])
    registry = ModelCapabilityRegistry()
    catalog = CapstoneModelCapabilityCatalog(registry)
    owner = ModelCapabilityContextOwner(catalog)
    register_pandapower_capability(catalog, owner, prepare_profile=KernelApplicationProfilePreparer(
        workspace_root=tmp_path, model_binder=bind))
    registry.seal()
    owner.seal()
    try:
        prepared = owner.prepare(claim).contributions[0].prepared
        bindings = prepared.prepared_application.bindings
        executor = bindings["grid"].runtime.executor
        from grid_agent.thread_binding import bind_thread_tool_catalog
        from capability_agent.application.errors import CapabilityTransportError
        bind_thread_tool_catalog(bindings["grid"].runtime.tool_catalog_path, prepared.model_binding,
                                authority_workspace=bindings["grid"].runtime.authority.workspace_root)
        with pytest.raises(CapabilityTransportError):
            executor.invoke("context.open", {"model_id": "case9"})
        child = executor.invoke("model.revision.derive", {
            "context_ref": prepared.model_binding.context_ref,
            "patches": [{"operation": "scale", "kind": "load", "selector": {"indices": [0]},
                         "fields": ["p_mw", "q_mvar"], "factor": 1.1}],
        })
        calculation = executor.invoke("analysis.powerflow.ac.run", {"context_ref": child["context_ref"]})
        results = (calculation["result_ref"],)
        evidence = tuple(calculation["evidence_refs"])
        events = ({"binding_id": "grid", "ok": True, "capability": "analysis.powerflow.ac.run",
                   "context_ref": child["context_ref"], "model_revision": child["revision_ref"],
                   "result_refs": results, "evidence_refs": evidence},)
        _verify_bound_attempt_references((prepared,), bindings,
            {ref: "grid" for ref in (*results, *evidence)}, results, evidence, events)
        projections = _build_result_projections(claim, (prepared,), bindings, results, evidence, events)
        assert len(projections) == 1
        assert projections[0]["status"] != "unavailable"
        stored = _terminal_result_projections({"result_refs": list(results), "evidence_refs": list(evidence),
            "result_projections": list(projections),
            "admission": {"mode": "authority_backed", "assurance": "lineage_verified"}},
            claim=claim, phase="completed")
        assert stored[0].model_revision == child["revision_ref"] != revision
        assert stored[0].result_ref == results[0]
    finally:
        owner.close()


def _claim(revision: str = "revision:sha256:" + "a" * 64) -> AttemptClaim:
    context = ModelContextSnapshot(
        "ctx_grid", "ieee39", revision,
        "pandapower", "sel_1", (PANDAPOWER_PROFILE_DESCRIPTOR.reference,),
    )
    return AttemptClaim(
        "thr_grid", "run_grid", AttemptSnapshot("turn_1", "attempt_1", "running", "ctx_grid"),
        "send_professional", "inspect", "ctx_grid", "sel_1", "lease_1", context,
    )


def test_pandapower_migration_root_registers_existing_application_profile():
    registry = ModelCapabilityRegistry()
    catalog = CapstoneModelCapabilityCatalog(registry)
    owner = ModelCapabilityContextOwner(catalog)
    register_pandapower_capability(catalog, owner)
    registry.seal()
    owner.seal()
    context = owner.prepare(_claim())
    contribution = context.contributions[0]
    assert contribution.descriptor == PANDAPOWER_PROFILE_DESCRIPTOR
    assert contribution.profile.manifest.application_id == "pandapower-static-analysis"
    owner.close()


def test_pandapower_profile_prepares_real_grid_authority_before_context_activation(tmp_path):
    authority_models = ModelRegistry(Pandapower340Engine())
    revision = authority_models.trusted_revision_ref("ieee39")
    calls = []

    def bind(prepared, context):
        executor = prepared.bindings["grid"].runtime.executor
        opened = executor.invoke("context.open", {"model_id": context.model_id})
        calls.append(opened)
        return AuthorityModelBinding(
            "grid", context.model_id, opened["revision_ref"],
            context.implementation_family, opened["context_ref"],
        )

    preparer = KernelApplicationProfilePreparer(
        workspace_root=tmp_path, model_binder=bind,
    )
    registry = ModelCapabilityRegistry()
    catalog = CapstoneModelCapabilityCatalog(registry)
    owner = ModelCapabilityContextOwner(catalog)
    register_pandapower_capability(catalog, owner, prepare_profile=preparer)
    registry.seal()
    owner.seal()
    context = owner.prepare(_claim(revision))
    assert calls[0]["model"] == "ieee39"
    assert calls[0]["revision_ref"] == revision
    assert context.contributions[0].prepared.model_binding.model_revision == revision
    owner.close()


def test_prepared_kernel_pi_factory_exposes_only_prepared_profile_inputs(tmp_path):
    authority_models = ModelRegistry(Pandapower340Engine())
    revision = authority_models.trusted_revision_ref("ieee39")
    calls = []

    def bind(prepared, context):
        executor = prepared.bindings["grid"].runtime.executor
        opened = executor.invoke("context.open", {"model_id": context.model_id})
        return AuthorityModelBinding(
            "grid", context.model_id, opened["revision_ref"],
            context.implementation_family, opened["context_ref"],
        )

    def build_session(claim, context, profiles):
        calls.append((claim, context, profiles))
        assert len(profiles) == 1
        prepared = profiles[0]
        binding = prepared.prepared_application.bindings["grid"]
        assert binding.runtime.tool_catalog_path.is_file()
        assert binding.runtime.guide_index_path.is_file()
        assert prepared.model_binding.context_ref.startswith("context:")
        return _Session()

    assembly = build_pandapower_thread_application(
        default_model_id="ieee39",
        model_resolver=lambda model_id: {
            "model_id": model_id,
            "revision_ref": revision,
            "implementation_family": "pandapower",
        },
        workspace_root=tmp_path,
        model_binder=bind,
        session_builder=build_session,
        default_selection=ModelCapabilitySelection(
            (PANDAPOWER_PROFILE_DESCRIPTOR.reference,)
        ),
    )
    assert assembly.network_projection_factory is not None
    claim = _claim(revision)
    runtime = assembly.runtime_factory(claim)
    projection = runtime.network_projection(claim, (), (), ())
    assert projection is not None
    assert projection["diagram"]["model"] == {
        "id": "ieee39", "revision": revision, "source": "gridctl",
    }
    assert len(projection["diagram"]["buses"]) == 39
    runtime.start()
    assert runtime.prompt("inspect", on_event=lambda _event: None) == "answer"
    runtime.stop()
    assert calls[0][0].model_context == claim.model_context
    assembly.capability_context_owner.close()


@pytest.mark.parametrize("execute_pi", [False, True])
def test_kernel_pi_rpc_builder_materializes_descriptor_before_process_start(tmp_path, execute_pi):
    repo = Path(__file__).resolve().parents[4]
    command = ("pi",)
    if execute_pi:
        node = shutil.which("node")
        assert node is not None
        assert (repo / ".grid-agent/runtime/pi/source/packages/coding-agent/dist/core/sdk.js").is_file()
        driver = repo / "packages/capability-agent-kernel/tests/runtime/fixtures/pi_research_driver.mjs"
        command = (node, str(driver), str(repo), str(tmp_path))
    authority_models = ModelRegistry(Pandapower340Engine())
    revision = authority_models.trusted_revision_ref("ieee39")

    def bind(prepared, context):
        opened = prepared.bindings["grid"].runtime.executor.invoke(
            "context.open", {"model_id": context.model_id}
        )
        return AuthorityModelBinding(
            "grid", context.model_id, opened["revision_ref"],
            context.implementation_family, opened["context_ref"],
        )

    resolved = ResolvedLLM(
        config=ResolvedLLMConfig(
            provider="openai", model="gpt-5.5", base_url="https://api.openai.com/v1",
            auth_kind="api_key_env", credential_reference="OPENAI_API_KEY",
            timeout_seconds=60, max_retries=0, pi_provider="openai",
            compatibility_profile="openai-responses", descriptor_version="test",
            public_headers={}, field_sources={}, supports_tools=True,
        ),
        secret=SecretValue("test-secret"),
    )
    host = RuntimeHost(
        command=PiCommand(
            argv=command,
            identity=PiRuntimeIdentity(
                path=tmp_path / "pi", source="fixture", package_version="1.0",
                lock_sha256="fixture",
            ),
        ),
        project_pi_dir=tmp_path / "project-pi",
        extension_path=tmp_path / "extension.mjs",
    )
    host.extension_path.with_name("model-input-metrics.mjs").write_text("export default () => {}")
    assembly = build_pandapower_thread_application(
        default_model_id="ieee39",
        model_resolver=lambda model_id: {
            "model_id": model_id, "revision_ref": revision,
            "implementation_family": "pandapower",
        },
        workspace_root=tmp_path / "workspaces",
        model_binder=bind,
        session_builder=PreparedKernelPiRpcSessionBuilder(
            runtime_host=host, resolved_llm=resolved,
            base_environment={"PATH": "/bin", "HOME": "/tmp"},
            research_enabled=True,
            research_is_active=lambda claim: True,
        ),
        default_selection=ModelCapabilitySelection(
            (PANDAPOWER_PROFILE_DESCRIPTOR.reference,)
        ),
    )
    runtime = assembly.runtime_factory(_claim(revision))
    session = runtime._session  # type: ignore[attr-defined]
    assert session.command.argv[0] == command[0]
    assert "test-secret" not in session.command.argv
    assert session.command.environment["OPENAI_API_KEY"] == "test-secret"
    descriptor = next(
        (path for path in (tmp_path / "workspaces").rglob("runtime-descriptor.json")),
        None,
    )
    assert descriptor is not None and descriptor.is_file()
    import json
    document = json.loads(descriptor.read_text())
    channel = Path(document["core"]["researchChannelPath"])
    assert (channel / "binding.json").is_file()
    assert session._research is not None
    if execute_pi:
        events = []
        try:
            runtime.start()
            assert runtime.prompt("Study the selected model", on_event=events.append) == "Research saved."
            research_events = [event for event in events if event["event_type"] == "research_state_updated"]
            assert len(research_events) == 1
            assert research_events[0]["payload"]["baseline_model_context"]["model_id"] == "ieee39"
            assert session._research.controller.read().revision == 1
        finally:
            runtime.stop()
    runtime.stop()
    assert not session._research.channel.is_active()
    assembly.capability_context_owner.close()


def test_thread_worker_uses_prepared_kernel_pi_rpc_transport(tmp_path):
    authority_models = ModelRegistry(Pandapower340Engine())
    revision = authority_models.trusted_revision_ref("ieee39")
    fake_pi = tmp_path / "fake-pi.py"
    fake_pi.write_text(
        "import json,sys\n"
        "for line in sys.stdin:\n"
        " request=json.loads(line)\n"
        " correlation=request.get('request_id')\n"
        " print(json.dumps({'type':'prompt_ack','ok':True,'request_id':correlation}),flush=True)\n"
        " print(json.dumps({'type':'text_delta','text':'prepared answer','request_id':correlation}),flush=True)\n"
        " print(json.dumps({'type':'agent_end','request_id':correlation}),flush=True)\n",
        encoding="utf-8",
    )

    def bind(prepared, context):
        opened = prepared.bindings["grid"].runtime.executor.invoke(
            "context.open", {"model_id": context.model_id}
        )
        return AuthorityModelBinding(
            "grid", context.model_id, opened["revision_ref"],
            context.implementation_family, opened["context_ref"],
        )

    resolved = ResolvedLLM(
        config=ResolvedLLMConfig(
            provider="openai", model="fixture", base_url="https://api.openai.com/v1",
            auth_kind="api_key_env", credential_reference="OPENAI_API_KEY",
            timeout_seconds=60, max_retries=0, pi_provider="openai",
            compatibility_profile="openai-responses", descriptor_version="test",
            public_headers={}, field_sources={}, supports_tools=True,
        ),
        secret=None,
    )
    host = RuntimeHost(
        command=PiCommand(
            argv=(sys.executable, str(fake_pi)),
            identity=PiRuntimeIdentity(
                path=fake_pi, source="fixture", package_version="1.0",
                lock_sha256="fixture",
            ),
        ),
        project_pi_dir=tmp_path / "project-pi",
        extension_path=tmp_path / "extension.mjs",
    )
    assembly = build_pandapower_thread_application(
        default_model_id="ieee39",
        model_resolver=lambda model_id: {
            "model_id": model_id, "revision_ref": revision,
            "implementation_family": "pandapower",
        },
        workspace_root=tmp_path / "workspaces",
        model_binder=bind,
        session_builder=PreparedKernelPiRpcSessionBuilder(
            runtime_host=host, resolved_llm=resolved,
        ),
        default_selection=ModelCapabilitySelection(
            (PANDAPOWER_PROFILE_DESCRIPTOR.reference,)
        ),
    )
    service = InMemoryThreadService.from_document({
        "schema": "capstone-thread-snapshot/1", "thread_id": "thr_grid",
        "run": {"run_id": "run_grid", "state": "open"},
        "active_model_context": _claim(revision).model_context.to_document(),
        "active_grid_page_id": "page_ieee39", "current_attempt": None,
        "last_event_seq": 0, "base_event_seq": 0,
    })
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_1",
        "idempotency_key": "idem_1", "thread_id": "thr_grid",
        "run_id": "run_grid", "kind": "send_ordinary", "expected_event_seq": 0,
        "payload": {"text": "inspect"},
    })
    result = run_pending_attempt(service, assembly.runtime_factory, worker_id="fixture-worker")
    assert result is not None and result.status == "completed"
    assert result.answer == "prepared answer"
    events = service.read_events("thr_grid", 0).events
    assert events[-1].event_type == "attempt_completed"
    assert events[-1].payload["answer"] == "prepared answer"
    assembly.capability_context_owner.close()
