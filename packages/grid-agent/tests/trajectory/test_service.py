from __future__ import annotations

from typing import cast
import threading
import time

import pytest
from pydantic import ValidationError

from grid_agent.trajectory.events import EventSource, RunScope
from grid_agent.trajectory.projection_models import (
    ApplicationProjectionMetadata,
    AgentTrajectory,
    ArtifactIndex,
    ArtifactIndexRecord,
    BindingProjectionMetadata,
    BusinessNode,
    BusinessTrajectory,
    ContextCheckpoint,
    ContextFrame,
    ProjectionDiagnostic,
    ProjectedRun,
    ContextTimeline,
)
from grid_agent.trajectory.replay import ImportedRunEvent, SourceCoordinate
from grid_agent.trajectory.artifact_policy import GridArtifactPathPolicy
from grid_agent.trajectory.artifacts import ImmutableArtifactRegistry
from grid_agent.trajectory.service import ProjectionService, _NativeArtifacts
from grid_agent.trajectory.cache_identity import build_identity
from grid_agent.trajectory.materialize import PROJECTION_SCHEMA


def test_imported_event_keeps_null_time_and_importer_integrity_label() -> None:
    event = ImportedRunEvent(
        analysis_id="analysis-old",
        sequence=1,
        timestamp=None,
        event_type="turn.started",
        import_previous_hash="sha256:" + "0" * 64,
        import_hash="sha256:" + "1" * 64,
        source_coordinate=SourceCoordinate(
            path="context/context-events.jsonl", sequence=2, sha256="a" * 64
        ),
        scope=RunScope(turn_id="analysis-old-t001"),
        source=EventSource(
            kind="observed",
            producer="legacy-v0.2-importer",
            integrity="importer-integrity",
        ),
        payload={"ordinal": 1, "instruction_sha256": "b" * 64},
    )

    assert event.schema_version == "grid-run-import-event/1.0"
    assert event.timestamp is None
    assert event.source.integrity == "importer-integrity"


def test_projection_service_opens_legacy_run_without_writing_source(tmp_path) -> None:
    from .test_legacy_v02 import _fixture, _digests

    run = _fixture(tmp_path)
    before = _digests(run)
    projected = ProjectionService(tmp_path / ".grid-agent/trajectory-cache").open_run(run)
    assert projected.analysis_id == "analysis-old"
    assert _digests(run) == before


def test_projection_service_reuses_typed_cache_and_never_writes_inside_run(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from .test_legacy_v02 import _fixture

    run = _fixture(tmp_path)
    service = ProjectionService(tmp_path / ".grid-agent" / "trajectory-cache")
    calls = 0
    module = __import__("grid_agent.trajectory.service", fromlist=["project_agent"])
    real_project = module.project_agent

    def counted_project(events):
        nonlocal calls
        calls += 1
        return real_project(events)

    monkeypatch.setattr(module, "project_agent", counted_project)
    first = service.open_run(run)
    second = service.open_run(run)

    assert first == second
    assert calls == 1

    inside = ProjectionService(run / "cache")
    inside.open_run(run)
    assert not (run / "cache").exists()


def test_projection_service_merges_three_concurrent_cold_builds(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from .test_legacy_v02 import _fixture

    run = _fixture(tmp_path)
    service = ProjectionService(tmp_path / "cache")
    module = __import__("grid_agent.trajectory.service", fromlist=["project_agent"])
    real_project = module.project_agent
    started = threading.Event()
    calls = 0

    def blocked_project(events):
        nonlocal calls
        calls += 1
        started.set()
        time.sleep(0.05)
        return real_project(events)

    monkeypatch.setattr(module, "project_agent", blocked_project)
    results: list[ProjectedRun] = []
    threads = [threading.Thread(target=lambda: results.append(service.open_run(run))) for _ in range(3)]
    for thread in threads:
        thread.start()
    assert started.wait(1)
    for thread in threads:
        thread.join(1)
    assert len(results) == 3
    assert calls == 1
    assert results[0] == results[1] == results[2]


def test_projection_service_skips_cache_leaf_symlinked_into_run(tmp_path) -> None:
    from .test_legacy_v02 import _fixture

    run = _fixture(tmp_path)
    cache = tmp_path / "cache"
    service = ProjectionService(cache)
    service.open_run(run)
    leaf = next(cache.rglob("projected-run.json")).parent
    saved = tmp_path / "saved-cache-leaf"
    leaf.rename(saved)
    leaf.symlink_to(run, target_is_directory=True)

    service.open_run(run)

    assert not any(run.glob("projected-run.json"))
    assert not any(run.glob("agent.json"))


def test_projection_service_does_not_mkdir_through_cache_ancestor_symlink(tmp_path) -> None:
    from .test_legacy_v02 import _fixture

    run = _fixture(tmp_path)
    cache = tmp_path / "cache"
    (cache / "analysis-old").parent.mkdir(parents=True)
    (cache / "analysis-old").symlink_to(run, target_is_directory=True)

    ProjectionService(cache).open_run(run)

    assert not any(run.rglob("trajectory-projection"))


def test_projection_service_returns_projection_when_cache_write_fails(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from .test_legacy_v02 import _fixture
    from grid_agent.trajectory.materialize import ProjectionMaterializer

    run = _fixture(tmp_path)

    def fail_write(self, projected_run, source_fingerprint, *, cache_identity=None):
        raise OSError("read-only cache")

    monkeypatch.setattr(ProjectionMaterializer, "write", fail_write)
    projected = ProjectionService(tmp_path / "cache").open_run(run)

    assert projected.analysis_id == "analysis-old"
    assert any(item.code == "cache_write_unavailable" for item in projected.diagnostics)
    assert all(str(tmp_path) not in item.message for item in projected.diagnostics)


def test_cache_identity_separates_public_cursor_from_private_run_key(tmp_path) -> None:
    from .test_legacy_v02 import _fixture
    from grid_agent.trajectory.legacy_v02 import LegacyV02Importer

    run = _fixture(tmp_path)
    imported = LegacyV02Importer(run).import_run()
    first = build_identity(run_root=tmp_path / "one", analysis_id="analysis-old", events=imported.events, failure=None, metadata_inputs=(), dependencies=(), source_kind="legacy-v0.2", projection_schema=PROJECTION_SCHEMA, legacy_source_fingerprint=imported.source_fingerprint, legacy_diagnostics=imported.diagnostics)
    second = build_identity(run_root=tmp_path / "two", analysis_id="analysis-old", events=imported.events, failure=None, metadata_inputs=(), dependencies=(), source_kind="legacy-v0.2", projection_schema=PROJECTION_SCHEMA, legacy_source_fingerprint=imported.source_fingerprint, legacy_diagnostics=imported.diagnostics)

    assert first.source_fingerprint == second.source_fingerprint
    assert first.cache_key != second.cache_key


@pytest.mark.parametrize(
    ("metadata", "dependencies", "legacy_source"),
    [
        (({"path": "manifest.json", "status": "present", "sha256": "b" * 64},), (), "legacy-source"),
        (({"path": "domains/a/runtime/runtime-descriptor.json", "status": "present", "sha256": "a" * 64},), (), "legacy-source"),
        ((), ({"ref": "artifact:sha256:x", "status": "unavailable"},), "legacy-source"),
        ((), ({"ref": "artifact:sha256:x", "status": "verified", "sha256": "c" * 64},), "legacy-source"),
        ((), (), "changed-legacy-source"),
    ],
)
def test_cache_identity_invalidates_metadata_and_dependency_inputs(
    tmp_path, metadata, dependencies, legacy_source
) -> None:
    from .test_legacy_v02 import _fixture
    from grid_agent.trajectory.legacy_v02 import LegacyV02Importer

    run = _fixture(tmp_path)
    imported = LegacyV02Importer(run).import_run()
    base = build_identity(run_root=run, analysis_id="analysis-old", events=imported.events, failure=None, metadata_inputs=(), dependencies=(), source_kind="legacy-v0.2", projection_schema=PROJECTION_SCHEMA, legacy_source_fingerprint="legacy-source", legacy_diagnostics=imported.diagnostics)
    changed = build_identity(run_root=run, analysis_id="analysis-old", events=imported.events, failure=None, metadata_inputs=metadata, dependencies=dependencies, source_kind="legacy-v0.2", projection_schema=PROJECTION_SCHEMA, legacy_source_fingerprint=legacy_source, legacy_diagnostics=imported.diagnostics)

    assert changed.source_fingerprint != base.source_fingerprint


def test_cache_identity_invalidates_trusted_event_prefix(tmp_path) -> None:
    from .test_legacy_v02 import _fixture
    from grid_agent.trajectory.legacy_v02 import LegacyV02Importer

    imported = LegacyV02Importer(_fixture(tmp_path)).import_run()
    full = build_identity(run_root=tmp_path, analysis_id="analysis-old", events=imported.events, failure=None, metadata_inputs=(), dependencies=(), source_kind="legacy-v0.2", projection_schema=PROJECTION_SCHEMA, legacy_source_fingerprint=imported.source_fingerprint, legacy_diagnostics=imported.diagnostics)
    shortened = build_identity(run_root=tmp_path, analysis_id="analysis-old", events=imported.events[:-1], failure=None, metadata_inputs=(), dependencies=(), source_kind="legacy-v0.2", projection_schema=PROJECTION_SCHEMA, legacy_source_fingerprint=imported.source_fingerprint, legacy_diagnostics=imported.diagnostics)

    assert full.source_fingerprint != shortened.source_fingerprint


def test_projected_run_keeps_application_and_binding_identity_for_read_models() -> None:
    binding = BindingProjectionMetadata(
        binding_id="inventory",
        domain_id="inventory-readonly",
        domain_version="1.0.0",
        authority_id="inventory-api",
        schema_id="inventory-output/1.0",
    )
    metadata = ApplicationProjectionMetadata(
        application_id="inventory-review",
        application_version="2.0.0",
        bindings={"inventory": binding},
    )

    projected = ProjectedRun(
        analysis_id="run-inventory",
        source_fingerprint="source",
        application=metadata,
        agent=AgentTrajectory(analysis_id="run-inventory"),
        business=BusinessTrajectory(analysis_id="run-inventory"),
        context=ContextTimeline(analysis_id="run-inventory"),
        artifacts=ArtifactIndex(analysis_id="run-inventory"),
    )

    assert projected.application is not None
    assert projected.application.application_id == "inventory-review"
    assert projected.application.bindings["inventory"].authority_id == "inventory-api"


def test_projection_service_reads_generic_runtime_descriptor_metadata(tmp_path) -> None:
    run = tmp_path / "runs/run-inventory"
    descriptor = run / "domains/inventory/runtime/runtime-descriptor.json"
    descriptor.parent.mkdir(parents=True)
    descriptor.write_text(
        '{"schema":"capability-agent-runtime/1.0","application":{"applicationId":"inventory-review","applicationVersion":"2.0.0"},"domains":[{"bindingId":"inventory","domainId":"inventory-readonly","domainVersion":"1.0.0","authorityId":"inventory-api","schema":"inventory-output/1.0"}]}',
        encoding="utf-8",
    )
    (run / "manifest.json").write_text(
        '{"schema_version":"grid-agent-analysis-manifest/1.0","analysis_id":"run-inventory","status":"completed","events_path":"events/run-events.jsonl"}',
        encoding="utf-8",
    )
    # The projection itself is supplied by the catalog in this focused test;
    # metadata extraction must not require a grid-specific authority.
    service = ProjectionService(tmp_path / "cache")
    metadata = service.read_application_metadata(run)

    assert metadata is not None
    assert metadata.application_id == "inventory-review"
    assert metadata.bindings["inventory"].authority_id == "inventory-api"


def test_native_artifact_verifier_accepts_replayed_artifact_pointer(tmp_path, monkeypatch) -> None:
    run_root = tmp_path / "runs/analysis-native"
    registry = ImmutableArtifactRegistry(
        run_root,
        path_policy=GridArtifactPathPolicy(),
    )
    pointer = registry.write_json(
        "context-view",
        "analysis-native-r001",
        {"analysis_id": "analysis-native", "revision": 1, "state_hash": "sha256:" + "a" * 64},
    )
    verifier = _NativeArtifacts(run_root)

    replayed_pointer = verifier.verify_reference(pointer.ref)

    def forbid_whole_read(_):
        pytest.fail("native verification must reuse bounded registry reads")

    monkeypatch.setattr(type(run_root), "read_bytes", forbid_whole_read)
    assert verifier.verify(replayed_pointer) == run_root / pointer.relative_path


def test_imported_event_rejects_native_integrity_claim() -> None:
    with pytest.raises(ValidationError, match="importer-integrity"):
        ImportedRunEvent(
            analysis_id="analysis-old",
            sequence=1,
            timestamp=None,
            event_type="turn.started",
            import_previous_hash="sha256:" + "0" * 64,
            import_hash="sha256:" + "1" * 64,
            source_coordinate=SourceCoordinate(
                path="context/context-events.jsonl", sequence=2, sha256="a" * 64
            ),
            source=EventSource(kind="observed", integrity="verified"),
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"schema_version": "foreign-import/9.9"}, "grid imported event schema"),
        ({"source": EventSource(kind="observed", producer="foreign-importer", integrity="importer-integrity")}, "grid imported event producer"),
    ],
)
def test_imported_event_rejects_foreign_grid_identity(
    overrides: dict[str, object],
    message: str,
) -> None:
    arguments: dict[str, object] = {
        "analysis_id": "analysis-old",
        "sequence": 1,
        "timestamp": None,
        "event_type": "turn.started",
        "import_previous_hash": "sha256:" + "0" * 64,
        "import_hash": "sha256:" + "1" * 64,
        "source_coordinate": SourceCoordinate(
            path="context/context-events.jsonl", sequence=2, sha256="a" * 64
        ),
        "source": EventSource(
            kind="observed",
            producer="legacy-v0.2-importer",
            integrity="importer-integrity",
        ),
    }
    arguments.update(overrides)

    with pytest.raises(ValidationError, match=message):
        ImportedRunEvent.model_validate(arguments)


def test_projection_nodes_require_provenance_for_derived_source() -> None:
    with pytest.raises(ValidationError, match="derived node requires"):
        BusinessNode(
            id="node-1",
            source="derived",
            source_sequences=(),
            rule_id=None,
            status="completed",
            kind="context-change",
            title="Changed",
        )


@pytest.mark.parametrize(
    ("model", "kwargs"),
    [
        (
            ContextFrame,
            {
                "id": "context-1",
                "source_sequences": (1,),
                "source_sequence": 1,
                "before_revision": 0,
                "after_revision": 1,
                "before_state_hash": "sha256:" + "a" * 64,
                "after_state_hash": "sha256:" + "b" * 64,
                "before_state": {},
                "delta": {},
                "after_state": {},
                "request_artifact_ref": "artifact:request",
            },
        ),
        (
            ProjectionDiagnostic,
            {
                "id": "diagnostic-1",
                "source_sequences": (1,),
                "severity": "warning",
                "code": "missing",
                "message": "Unavailable",
            },
        ),
    ],
)
def test_default_derived_projection_nodes_require_nonempty_rule_id(
    model: type[object], kwargs: dict[str, object]
) -> None:
    with pytest.raises(ValidationError, match="rule_id"):
        model(**kwargs)  # type: ignore[operator]

    with pytest.raises(ValidationError, match="rule_id"):
        model(rule_id="", **kwargs)  # type: ignore[operator]


def test_context_frame_requires_ordered_revisions_and_reason_for_missing_request() -> None:
    with pytest.raises(ValidationError, match="before_revision"):
        ContextFrame(
            id="context-invalid-revision",
            source_sequences=(1,),
            rule_id="context-frame.v1",
            source_sequence=1,
            before_revision=2,
            after_revision=1,
            before_state_hash="sha256:" + "a" * 64,
            after_state_hash="sha256:" + "b" * 64,
            before_state={},
            delta={},
            after_state={},
        )

    with pytest.raises(ValidationError, match="unavailable_reason"):
        ContextFrame(
            id="context-missing-request",
            source_sequences=(1,),
            rule_id="context-frame.v1",
            source_sequence=1,
            before_revision=0,
            after_revision=1,
            before_state_hash="sha256:" + "a" * 64,
            after_state_hash="sha256:" + "b" * 64,
            before_state={},
            delta={},
            after_state={},
            request_artifact_ref=None,
        )


@pytest.mark.parametrize(
    ("model", "kwargs"),
    [
        (
            ContextFrame,
            {
                "source_sequence": 1,
                "before_revision": 0,
                "after_revision": 1,
                "before_state_hash": "sha256:" + "a" * 64,
                "after_state_hash": "sha256:" + "b" * 64,
                "before_state": {},
                "delta": {},
                "after_state": {},
                "request_artifact_ref": "artifact:request",
            },
        ),
        (
            ArtifactIndexRecord,
            {
                "reference": "artifact:request",
                "kind": "request",
                "relative_path": "requests/request/input.json",
                "sha256": "a" * 64,
                "verification_status": "verified",
            },
        ),
        (
            ProjectionDiagnostic,
            {"severity": "warning", "code": "missing", "message": "Unavailable"},
        ),
    ],
)
def test_node_like_projection_models_require_id_and_positive_provenance(
    model: type[object], kwargs: dict[str, object]
) -> None:
    with pytest.raises(ValidationError, match="id"):
        model(**kwargs)  # type: ignore[operator]

    with pytest.raises(ValidationError, match="source_sequences"):
        model(id="stable-id", source_sequences=(), **kwargs)  # type: ignore[operator]

    with pytest.raises(ValidationError, match="positive"):
        model(id="stable-id", source_sequences=(0,), **kwargs)  # type: ignore[operator]


def test_imported_event_payload_is_deeply_immutable_and_json_compatible() -> None:
    event = ImportedRunEvent(
        analysis_id="analysis-old",
        sequence=1,
        timestamp=None,
        event_type="turn.started",
        import_previous_hash="sha256:" + "0" * 64,
        import_hash="sha256:" + "1" * 64,
        source_coordinate=SourceCoordinate(
            path="context/context-events.jsonl", sequence=2, sha256="a" * 64
        ),
        source=EventSource(
            kind="observed",
            producer="legacy-v0.2-importer",
            integrity="importer-integrity",
        ),
        payload={"nested": {"values": ["original"]}},
    )

    with pytest.raises(TypeError):
        event.payload["nested"]["values"] += ("mutated",)
    with pytest.raises(AttributeError):
        event.payload["nested"]["values"].append("mutated")
    assert event.model_dump(mode="json")["payload"] == {
        "nested": {"values": ["original"]}
    }


def test_context_frame_states_are_deeply_immutable_and_json_compatible() -> None:
    frame = ContextFrame(
        id="context-1",
        source_sequences=(1,),
        rule_id="context-frame.v1",
        source_sequence=1,
        before_revision=0,
        after_revision=1,
        before_state_hash="sha256:" + "a" * 64,
        after_state_hash="sha256:" + "b" * 64,
        before_state={"nested": {"values": ["before"]}},
        delta={"nested": {"values": ["change"]}},
        after_state={"nested": {"values": ["after"]}},
        request_artifact_ref="artifact:request",
    )

    with pytest.raises(TypeError):
        frame.after_state["nested"]["values"] += ("mutated",)
    with pytest.raises(AttributeError):
        frame.before_state["nested"]["values"].append("mutated")
    assert frame.model_dump(mode="json")["after_state"] == {
        "nested": {"values": ["after"]}
    }


def test_artifact_index_records_are_deeply_immutable_and_json_compatible() -> None:
    record = ArtifactIndexRecord(
        id="artifact-record-1",
        source_sequences=(1,),
        reference="artifact:request",
        kind="request",
        relative_path="requests/request/input.json",
        sha256="a" * 64,
        verification_status="verified",
    )
    index = ArtifactIndex(analysis_id="analysis-1", records={record.reference: record})
    records = cast(dict[str, ArtifactIndexRecord], index.records)

    with pytest.raises(TypeError):
        records[record.reference] = record
    with pytest.raises(TypeError):
        records.update({"artifact:other": record})
    assert index.model_dump(mode="json")["records"] == {
        "artifact:request": record.model_dump(mode="json")
    }


def test_context_checkpoint_state_is_deeply_immutable_and_json_compatible() -> None:
    checkpoint = ContextCheckpoint(
        source_sequence=1,
        context_revision=1,
        state_hash="sha256:" + "a" * 64,
        state={"nested": {"values": ["checkpoint"]}},
    )

    with pytest.raises(TypeError):
        checkpoint.state["nested"]["values"] += ("mutated",)
    with pytest.raises(AttributeError):
        checkpoint.state["nested"]["values"].append("mutated")
    assert checkpoint.model_dump(mode="json")["state"] == {
        "nested": {"values": ["checkpoint"]}
    }
