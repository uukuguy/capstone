"""Pinned Pi execution, compaction and disk restore; no live Provider calls."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from capability_agent.application import ApplicationContextStore, ContextEventDraft, ResearchController
from capability_agent.application.workspace import ApplicationWorkspace
from capability_agent.application.projector import ApplicationInvocationProjector
from capability_agent.tools.catalog import CompositeToolCatalog, CoreToolCatalog
from capability_agent.runtime.descriptor import descriptor_from_endpoint, write_runtime_descriptor
from capability_agent.runtime.environment import PiLaunch
from capability_agent.runtime.research_channel import ResearchRequestChannel
from capability_agent.runtime.rpc import PiCaptureIntegrityError, PiRpcClient
from capability_agent.runtime.trace import JsonlTraceWriter


class _Workspace:
    def __init__(self, path):
        self.root_path = path


def _runtime(tmp_path):
    repo = Path(__file__).resolve().parents[4]
    sdk = repo / ".grid-agent/runtime/pi/source/packages/coding-agent/dist/core/sdk.js"
    if not sdk.is_file():
        pytest.skip("run make setup, make install-pi and make doctor for managed Pi integration")
    node = shutil.which("node")
    assert node is not None
    workspace = ApplicationWorkspace.create(tmp_path / "runs", run_id="run-1", binding_ids=("fixture",))
    store = ApplicationContextStore.initialize(workspace, domains={"fixture": "fixture-state/1.0"})
    store.append(ContextEventDraft(event_type="turn.started", turn_id="turn-1", payload={"ordinal": 1}))
    research = ResearchController(store, research_id="research-1", turn_id="turn-1", admit_reference=lambda _: False)
    channel = ResearchRequestChannel(research, attempt_id="attempt-1", is_active=lambda: True)
    domain = workspace.root / "domains/fixture"
    guides = domain / "guides"
    guides.mkdir()
    catalog, index = domain / "catalog.json", domain / "index.json"
    catalog.write_text(json.dumps({"tools": []}))
    index.write_text(json.dumps({"protocol": "fixture-guide-index", "version": "1.0", "root": str(guides), "resources": {}}))
    descriptor = descriptor_from_endpoint(
        binding_id="fixture", workspace=domain, application_workspace_path=workspace.root,
        endpoint={"executable": "fixturectl"}, protocol="fixture-capability", protocol_version="1.0", authority_id="fixture",
        tool_catalog_path=catalog, guide_index_path=index, guide_root_path=guides,
        application_id="research-fixture", run_id="run-1", research_channel_path=channel.root,
    )
    descriptor_path = tmp_path / "runtime.json"
    write_runtime_descriptor(descriptor_path, descriptor)
    driver = Path(__file__).parent / "fixtures/pi_research_driver.mjs"
    trace = JsonlTraceWriter(tmp_path / "trace.jsonl")
    environment = {"PATH": os.defpath, "PI_OFFLINE": "1", "CAPABILITY_AGENT_RUNTIME_DESCRIPTOR": str(descriptor_path)}
    client = PiRpcClient(PiLaunch(argv=(node, str(driver), str(repo), str(tmp_path)), environment=environment),
                         _Workspace(tmp_path), trace, timeout_seconds=20)
    return store, research, channel, client, trace


def test_pinned_pi_updates_research_and_reads_it_after_compaction_and_disk_restore(tmp_path):
    store, research, channel, client, trace = _runtime(tmp_path)
    catalog = CompositeToolCatalog(core_tools=CoreToolCatalog.default(include_research=True).tools, domain_tools=())
    projector = ApplicationInvocationProjector(store, catalog, {"fixture": SimpleNamespace(binding_id="fixture")})
    events = []
    def observe(event, sequence):
        events.append(event)
        projector.observe(event, turn_id="turn-1", trace_sequence=sequence)
    client.start()
    try:
        first = client.prompt_and_wait("Start this research", on_control_requests=channel.drain, on_semantic_event=observe)
        assert first == "Research saved."
        assert research.read().revision == 1
        assert research.read().goal == "Verify persistent research state"
        assert client.prompt_and_wait("Check the current research", on_control_requests=channel.drain) == "Research saved."
        assert json.loads((tmp_path / "compaction.json").read_text())["compacted"] is True
        research.update({"request_id": "host-followup", "expected_revision": 1,
                         "changes": {"goal": "Current goal after durable recovery"}})
        channel.publish_view()
        assert client.prompt_and_wait("Resume the saved session", on_control_requests=channel.drain) == "Research saved."
    finally:
        client.stop()
        trace.close()
    requests = [json.loads(path.read_text()) for path in sorted(tmp_path.glob("request-*.json"))]
    agent_requests = [item for item in requests if item["phase"] == "agent"]
    def research_texts(item):
        return [part["text"] for message in item["context"]["messages"] if message["role"] == "user"
                for part in (message["content"] if isinstance(message["content"], list) else [])
                if part.get("type") == "text" and part["text"].startswith("Committed research state")]
    assert research_texts(agent_requests[0]) == []  # no mandatory Research creation
    assert all(len(research_texts(item)) == 1 for item in agent_requests[1:])
    assert "Current goal after durable recovery" in research_texts(agent_requests[-1])[0]
    assert any(item["phase"] == "compaction" for item in requests)
    assert store.verify_materialized_snapshot() == store.snapshot
    assert any(event.get("type") == "tool_result" and event.get("capability") == "agent_research_update" for event in events)
    depth = [event for event in events if event.get("type") == "tool_result"
             and event.get("capability") == "agent_research_depth"]
    assert len(depth) == 1
    assert depth[0]["ok"] is True
    assert depth[0]["result"]["requested_level"] == depth[0]["result"]["applied_level"] == "high"
    assert depth[0]["evidence_refs"] == []
    assert store.snapshot.domains["fixture"].revision == 0
    assert store.snapshot.core.result_refs == store.snapshot.core.evidence_refs == ()


def test_actual_pi_blocks_provider_request_if_a_later_hook_removes_research_context(tmp_path):
    store, research, channel, client, trace = _runtime(tmp_path)
    (tmp_path / "drop-context").write_text("enable the test-only drop hook")
    client.start()
    try:
        with pytest.raises(PiCaptureIntegrityError):
            client.prompt_and_wait("Start this research", on_control_requests=channel.drain)
    finally:
        client.stop()
        trace.close()
    assert research.read().revision == 1
    assert len(list(tmp_path.glob("request-*.json"))) == 1
    assert store.verify_materialized_snapshot() == store.snapshot
