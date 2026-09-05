"""Real native input mutations must invalidate disposable projections."""

import json
import shutil
from unittest.mock import patch

import pytest

from grid_agent.trajectory import service as service_module
from grid_agent.trajectory.service import ProjectionService, _NativeArtifacts
from grid_agent.trajectory.cache_identity import collect_native_dependencies
from capability_agent.trajectory.reader import RunEventReader
from .api.test_app import write_native_run_with_simulator_artifacts


@pytest.mark.parametrize("mutation", ["tamper", "delete", "missing_then_present"])
def test_native_artifact_changes_invalidate_cached_verification(tmp_path, mutation):
    run, refs = write_native_run_with_simulator_artifacts(tmp_path / "runs")
    ref = refs["answer_ref"]
    path = run / _NativeArtifacts(run).verify_reference(ref).relative_path
    original = path.read_bytes()
    if mutation == "missing_then_present":
        path.unlink()
    service = ProjectionService(tmp_path / "cache")
    with patch.object(service_module, "project_agent", wraps=service_module.project_agent) as build:
        first = service.open_run(run)
        assert service.open_run(run) == first
        assert build.call_count == 1
        expected = "unavailable" if mutation == "missing_then_present" else "verified"
        assert first.artifacts.records[ref].verification_status == expected
        if mutation == "tamper":
            path.write_bytes(original + b" ")
        elif mutation == "delete":
            path.unlink()
        else:
            path.write_bytes(original)
        second = service.open_run(run)
        assert build.call_count == 2
        assert second.source_fingerprint != first.source_fingerprint
        expected = "verified" if mutation == "missing_then_present" else "unavailable"
        assert second.artifacts.records[ref].verification_status == expected


@pytest.mark.parametrize("relative", ["manifest.json", "runtime/runtime-descriptor.json", "core/runtime-descriptor.json", "domains/grid/runtime/runtime-descriptor.json"])
def test_metadata_creation_and_change_invalidate_cache(tmp_path, relative):
    run, _ = write_native_run_with_simulator_artifacts(tmp_path / "runs")
    path = run / relative
    service = ProjectionService(tmp_path / "cache")
    first = service.open_run(run)
    value = json.loads(path.read_text()) if path.exists() else {}
    path.parent.mkdir(parents=True, exist_ok=True)
    value["application_id"] = "cache-input-test"
    path.write_text(json.dumps(value), encoding="utf-8")
    second = service.open_run(run)
    assert second.source_fingerprint != first.source_fingerprint
    assert second.application.application_id == "cache-input-test"
    value["application_id"] = "cache-input-changed"
    path.write_text(json.dumps(value), encoding="utf-8")
    third = service.open_run(run)
    assert third.source_fingerprint != second.source_fingerprint
    assert third.application.application_id == "cache-input-changed"
    assert service.open_run(run) == third


def test_dependency_collector_covers_actual_projector_reads(tmp_path):
    run, _ = write_native_run_with_simulator_artifacts(tmp_path / "runs")
    events = RunEventReader(run / "events/run-events.jsonl").read_prefix().events
    # Context payload references are I/O dependencies even without event.refs.
    from grid_agent.trajectory.events import EventRefs
    events = tuple(event.model_copy(update={"refs": EventRefs()})
                   if event.event_type == "context.injected" else event for event in events)
    resolver = _NativeArtifacts(run)
    with patch.object(resolver, "verify_reference", wraps=resolver.verify_reference) as verify:
        dependencies = collect_native_dependencies(events, resolver)
        collected = {item["ref"] for item in dependencies}
        assert collected == {call.args[0] for call in verify.call_args_list}
        verify.reset_mock()
        service_module.project_business(events, resolver)
        service_module.project_artifacts(events, resolver)
        service_module.project_context(events, resolver)
        actual_reads = {call.args[0] for call in verify.call_args_list}
        assert actual_reads
        assert actual_reads <= collected
        context_ref = next(event.payload["artifact_ref"] for event in events
                           if event.event_type == "context.injected")
        assert context_ref in actual_reads


def test_cache_hit_reverifies_dependencies_without_rebuilding(tmp_path):
    run, refs = write_native_run_with_simulator_artifacts(tmp_path / "runs")
    service = ProjectionService(tmp_path / "cache")
    first = service.open_run(run)
    real_verify = _NativeArtifacts.verify_reference
    seen = []

    def tracking_verify(self, reference):
        seen.append(reference)
        return real_verify(self, reference)

    with patch.object(_NativeArtifacts, "verify_reference", tracking_verify), patch.object(
        service_module, "project_agent", wraps=service_module.project_agent
    ) as build:
        assert service.open_run(run) == first
        assert build.call_count == 0
    assert refs["answer_ref"] in seen
    assert refs["result_ref"] in seen
    assert refs["evidence_ref"] in seen


def test_same_analysis_id_in_two_roots_never_shares_cache_entry(tmp_path):
    run, _ = write_native_run_with_simulator_artifacts(tmp_path / "first")
    other = tmp_path / "second" / run.name
    shutil.copytree(run, other)
    cache = tmp_path / "cache"
    service = ProjectionService(cache)
    with patch.object(service_module, "project_agent", wraps=service_module.project_agent) as build:
        first = service.open_run(run)
        second = service.open_run(other)
        assert build.call_count == 2
        assert first.source_fingerprint == second.source_fingerprint
        assert service.open_run(run) == first
        assert service.open_run(other) == second
        assert build.call_count == 2
    assert len(tuple(cache.rglob("projected-run.json"))) == 2


def test_corrupt_native_prefix_is_never_cached(tmp_path):
    run, _ = write_native_run_with_simulator_artifacts(tmp_path / "runs")
    path = run / "events/run-events.jsonl"
    with path.open("ab") as stream:
        stream.write(b"{invalid-json}\n")
    cache = tmp_path / "cache"
    service = ProjectionService(cache)
    with patch.object(service_module, "project_agent", wraps=service_module.project_agent) as build:
        first = service.open_run(run)
        second = service.open_run(run)
        assert first == second
        assert build.call_count == 2
        assert first.diagnostics
    assert not tuple(cache.rglob("projected-run.json"))
