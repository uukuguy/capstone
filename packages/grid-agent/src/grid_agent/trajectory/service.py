"""Single read-only entry point for native and imported trajectory projections."""

from __future__ import annotations

import hashlib
import json
import math
import threading
from pathlib import Path
from types import SimpleNamespace
from dataclasses import dataclass
from collections.abc import Mapping, Sequence
from typing import Any, Literal, cast

from grid_agent.trajectory.agent_projection import project_agent
from grid_agent.trajectory.artifact_projection import project_artifacts
from grid_agent.trajectory.business_projection import project_business
from grid_agent.trajectory.context_projection import project_context
from grid_agent.trajectory.legacy_v02 import LegacyV02Importer
from pandapower_domain.authority import ContentReferenceVerifier
from capability_agent.trajectory.artifacts import ArtifactIntegrityError, ArtifactPointer, ImmutableArtifactRegistry
from grid_agent.trajectory.artifact_policy import GridArtifactPathPolicy
from grid_agent.trajectory.materialize import PROJECTION_SCHEMA, ProjectionMaterializer
from grid_agent.trajectory.cache_identity import build_identity, collect_native_dependencies
from grid_agent.trajectory.projection_models import (
    ApplicationProjectionMetadata,
    BindingProjectionMetadata,
    CoreTimelineItem,
    ProjectedRun,
    ProjectionDiagnostic,
)
from capability_agent.trajectory.reader import RunEventReader
from capability_agent.trajectory.replay import ReplayEventLike


class _HistoricalArtifacts:
    """Only admits v0.2 result/evidence references backed by their named file."""

    def __init__(self, run_root: Path) -> None:
        self.run_root = run_root

    def verify(self, reference: str) -> SimpleNamespace:
        if not (reference.startswith("result:sha256:") or reference.startswith("evidence:sha256:")):
            raise RuntimeError("historical artifact reference is unavailable")
        digest = reference.rsplit(":", 1)[-1]
        matches = tuple(self.run_root.glob("evidence/**/*.json"))
        for path in matches:
            # v0.2 references name a content-addressed domain record; the JSON
            # wrapper itself is not necessarily hashed as the reference payload.
            if digest in path.name:
                return SimpleNamespace(authority="gridctl", integrity="verified")
        raise RuntimeError("historical artifact digest is unavailable")

    def verify_reference(self, reference: str) -> object:
        raise RuntimeError("v0.2 references are not native artifact pointers")


class _NativeArtifacts:
    """Verify native artifact pointers by their digest, never legacy filenames."""

    def __init__(self, run_root: Path) -> None:
        self.run_root = run_root

    def verify_reference(self, reference: str) -> ArtifactPointer:
        if reference.startswith("artifact:sha256:"):
            for kind, identity, path in self._artifact_ref_candidates():
                pointer = self._register_existing(kind, identity, path)
                if pointer is not None and pointer.ref == reference:
                    return pointer
            raise RuntimeError("native artifact digest is unavailable")
        if reference.startswith("result:sha256:"):
            verified = ContentReferenceVerifier(self.run_root).verify_result(reference)
            pointer = self._register_existing("result", reference, verified.path)
            if pointer is not None:
                return ArtifactPointer(
                    ref=reference,
                    kind=pointer.kind,
                    relative_path=pointer.relative_path,
                    sha256=pointer.sha256,
                    size_bytes=pointer.size_bytes,
                )
            raise RuntimeError("native result artifact is unavailable")
        if reference.startswith("evidence:sha256:"):
            verified = ContentReferenceVerifier(self.run_root).verify_evidence(reference)
            pointer = self._register_existing("evidence", reference, verified.path)
            if pointer is not None:
                return ArtifactPointer(
                    ref=reference,
                    kind=pointer.kind,
                    relative_path=pointer.relative_path,
                    sha256=pointer.sha256,
                    size_bytes=pointer.size_bytes,
                )
            raise RuntimeError("native evidence artifact is unavailable")
        raise RuntimeError("native artifact digest is unavailable")

    def verify(self, reference: str | ArtifactPointer) -> Path | SimpleNamespace:
        if isinstance(reference, str) and reference.startswith(("result:sha256:", "evidence:sha256:")):
            self.verify_reference(reference)
            return SimpleNamespace(authority="gridctl", integrity="verified")
        pointer = self.verify_reference(reference) if isinstance(reference, str) else reference
        if not isinstance(pointer, ArtifactPointer):
            raise RuntimeError("native artifact pointer is unavailable")
        if pointer.ref.startswith(("result:sha256:", "evidence:sha256:")):
            self.verify_reference(pointer.ref)
            return SimpleNamespace(authority="gridctl", integrity="verified")
        if pointer.ref != f"artifact:sha256:{pointer.sha256}":
            raise RuntimeError("native artifact pointer has an invalid reference")
        path = self.run_root / pointer.relative_path
        try:
            path.resolve(strict=True).relative_to(self.run_root.resolve(strict=True))
        except (OSError, ValueError) as exc:
            raise RuntimeError("native artifact pointer escapes the run root") from exc
        value = path.read_bytes()
        if len(value) != pointer.size_bytes:
            raise RuntimeError("native artifact size does not match its pointer")
        if hashlib.sha256(value).hexdigest() != pointer.sha256:
            raise RuntimeError("native artifact digest does not match its pointer")
        return path

    def _register_existing(
        self, kind: str, identity: str, path: Path
    ) -> ArtifactPointer | None:
        try:
            return ImmutableArtifactRegistry(
                self.run_root,
                path_policy=GridArtifactPathPolicy(),
            ).register_existing(kind, identity, path)
        except (ArtifactIntegrityError, OSError):
            return None

    def _artifact_ref_candidates(self) -> tuple[tuple[str, str, Path], ...]:
        candidates: list[tuple[str, str, Path]] = []
        for path in sorted(self.run_root.glob("requests/*/input.json")):
            candidates.append(("request-input", path.parent.name, path))
        for path in sorted(self.run_root.glob("requests/*/response.json")):
            candidates.append(("model-response", path.parent.name, path))
        for path in sorted(self.run_root.glob("turns/*/answer.json")):
            candidates.append(("answer", path.parent.name, path))
        for path in sorted(self.run_root.glob("context/views/*/view.json")):
            candidates.append(("context-view", path.parent.name, path))
        for path in sorted(self.run_root.glob("tool-results/*/*.json")):
            candidates.append(("tool-result", f"{path.parent.name}:{path.stem}", path))
        return tuple(candidates)


class ProjectionService:
    def __init__(self, cache_root: Path) -> None:
        self.cache_root = Path(cache_root)
        self._locks: dict[str, tuple[threading.Lock, int]] = {}
        self._locks_guard = threading.Lock()

    def read_application_metadata(
        self, run_root: Path
    ) -> ApplicationProjectionMetadata | None:
        """Read controller-recorded application/binding labels for a run.

        New application runs persist identity in a manifest or runtime
        descriptor.  Older grid runs have neither and deliberately remain
        metadata-free rather than receiving an inferred ``gridctl`` label.
        Only fixed files within ``run_root`` are considered; arbitrary paths
        from a manifest are never opened.
        """

        return _metadata_from_snapshot(_metadata_snapshot(Path(run_root)))


    def open_run(self, run_root: Path) -> ProjectedRun:
        run_root = Path(run_root)
        lock_key = str(run_root.resolve())
        with self._locks_guard:
            lock, users = self._locks.get(lock_key, (threading.Lock(), 0))
            self._locks[lock_key] = (lock, users + 1)
        try:
            with lock:
                return self._open_run_locked(run_root)
        finally:
            with self._locks_guard:
                _, users = self._locks[lock_key]
                if users == 1:
                    self._locks.pop(lock_key, None)
                else:
                    self._locks[lock_key] = (lock, users - 1)

    def _open_run_locked(self, run_root: Path) -> ProjectedRun:
        native_path = run_root / "events/run-events.jsonl"
        legacy_source_fingerprint: str | None = None
        legacy_diagnostics: tuple[object, ...] = ()
        if native_path.is_file():
            prefix = RunEventReader(native_path).read_prefix()
            events = prefix.events
            extra = () if prefix.failure is None else (ProjectionDiagnostic(id="native-replay-failure", source_sequences=(max(1, len(events)),), rule_id="native-prefix-validation/v1", severity="error", code=prefix.failure.code, message=prefix.failure.message),)
            artifacts = _NativeArtifacts(run_root)
            source_kind = "native"
            failure = prefix.failure
        else:
            imported = LegacyV02Importer(run_root).import_run()
            events = imported.events
            extra = tuple(ProjectionDiagnostic(id=f"legacy:{item.code}", source_sequences=(1,), rule_id="legacy-import/v1", severity="warning", code=item.code, message=item.message) for item in imported.diagnostics)
            artifacts = _HistoricalArtifacts(run_root)
            source_kind = "legacy-v0.2"
            failure = None
            legacy_source_fingerprint = imported.source_fingerprint
            legacy_diagnostics = tuple(imported.diagnostics)
        replay_events = cast(Sequence[ReplayEventLike], events)
        metadata_snapshot = _metadata_snapshot(run_root)
        metadata = _metadata_from_snapshot(metadata_snapshot)
        dependencies = collect_native_dependencies(replay_events, artifacts)
        identity = build_identity(
            run_root=run_root,
            analysis_id=events[0].analysis_id if events else run_root.name,
            events=replay_events,
            failure=failure,
            metadata_inputs=metadata_snapshot.identity_inputs,
            dependencies=dependencies,
            source_kind=source_kind,
            projection_schema=PROJECTION_SCHEMA,
            legacy_source_fingerprint=legacy_source_fingerprint,
            legacy_diagnostics=legacy_diagnostics,
        )
        materializer = ProjectionMaterializer(self.cache_root)
        cache_allowed = _cache_root_is_outside_run(self.cache_root, run_root)
        if identity.cacheable and cache_allowed:
            cached = materializer.load_if_current(
                events[0].analysis_id if events else run_root.name,
                identity.source_fingerprint,
                cache_identity=identity.cache_key,
            )
            if cached is not None:
                return cached
        binding = (
            next(iter(metadata.bindings.values()))
            if metadata is not None and len(metadata.bindings) == 1
            else None
        )
        agent = project_agent(replay_events).model_copy(update={"binding": binding})
        business = project_business(
            replay_events,
            artifacts,
            application=metadata,
            binding=binding,
        )
        context = project_context(replay_events, artifacts, binding=binding)
        artifact_index = project_artifacts(replay_events, artifacts).model_copy(
            update={"binding": binding}
        )
        projected = ProjectedRun(
            analysis_id=events[0].analysis_id if events else run_root.name,
            source_fingerprint=identity.source_fingerprint,
            core_timeline=project_core_timeline(replay_events),
            application=metadata,
            agent=agent,
            business=business,
            context=context,
            artifacts=artifact_index,
            diagnostics=extra,
        )
        if identity.cacheable and cache_allowed:
            try:
                materializer.write(projected, identity.source_fingerprint, cache_identity=identity.cache_key)
            except OSError:
                projected = projected.model_copy(update={"diagnostics": (*projected.diagnostics, ProjectionDiagnostic(id="cache-write-unavailable", source_sequences=(1,), rule_id="trajectory-cache/v1", severity="warning", code="cache_write_unavailable", message="trajectory cache could not be written"))})
        return projected


@dataclass(frozen=True, slots=True)
class _MetadataSnapshot:
    manifest: Mapping[str, object] | None
    context: Mapping[str, object] | None
    descriptors: tuple[Mapping[str, object], ...]
    identity_inputs: tuple[dict[str, object], ...]


def _metadata_snapshot(root: Path) -> _MetadataSnapshot:
    paths = (Path("manifest.json"), Path("core/context.json"), *_descriptor_paths(root))
    parsed: list[Mapping[str, object] | None] = []
    identity: list[dict[str, object]] = []
    for relative in paths:
        path = root / relative
        try:
            if path.is_symlink() or not path.is_file():
                parsed.append(None); identity.append({"path": relative.as_posix(), "status": "missing"}); continue
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(root.resolve(strict=True)):
                parsed.append(None); identity.append({"path": relative.as_posix(), "status": "unsafe"}); continue
            raw = resolved.read_bytes(); value = json.loads(raw)
            parsed.append(value if isinstance(value, Mapping) else None)
            identity.append({"path": relative.as_posix(), "status": "present", "sha256": hashlib.sha256(raw).hexdigest()})
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
            parsed.append(None); identity.append({"path": relative.as_posix(), "status": "unavailable"})
    return _MetadataSnapshot(parsed[0], parsed[1], tuple(item for item in parsed[2:] if item is not None), tuple(identity))


def _metadata_from_snapshot(snapshot: _MetadataSnapshot) -> ApplicationProjectionMetadata | None:
    app_id, app_version = _application_identity(snapshot.manifest, snapshot.context, snapshot.descriptors)
    merged: dict[str, dict[str, object]] = {}
    for descriptor in snapshot.descriptors:
        _merge_binding_records(merged, _binding_records(descriptor))
    _merge_binding_records(merged, _binding_records(snapshot.manifest))
    _merge_binding_records(merged, _context_binding_records(snapshot.context))
    if app_id is None and not merged:
        return None
    return ApplicationProjectionMetadata(application_id=app_id or "unknown-application", application_version=app_version or "unknown", bindings={binding_id: BindingProjectionMetadata(binding_id=binding_id, domain_id=str(values.get("domain_id") or binding_id), domain_version=str(values.get("domain_version") or "unknown"), authority_id=str(values.get("authority_id") or "unknown"), schema_id=str(values.get("schema") or "unknown"), presentation=cast(Mapping[str, Any], _safe_mapping(values.get("presentation")))) for binding_id, values in sorted(merged.items())})


def project_core_timeline(
    events: Sequence[ReplayEventLike],
) -> tuple[CoreTimelineItem, ...]:
    """Project recorded framework lifecycle events without domain semantics.

    Business declaration events are owned by the selected domain projection and
    intentionally remain out of this timeline.  Every other event is carried by
    its recorded sequence and type; statuses are a neutral lifecycle label, not
    a recalculation of any domain result.
    """

    return tuple(
        CoreTimelineItem(
            id=f"core:{event.sequence}",
            source_sequence=event.sequence,
            event_type=event.event_type,
            label=event.event_type,
            status=_core_event_status(event.event_type),
        )
        for event in events
        if not event.event_type.startswith("business.")
    )


def _core_event_status(event_type: str) -> Literal["running", "completed", "failed", "interrupted", "unavailable"]:
    if event_type.endswith((".failed", ".rejected", ".exhausted")):
        return "failed"
    if event_type.endswith((".completed", ".submitted", ".projected", ".injected")):
        return "completed"
    if event_type.endswith((".started", ".scheduled")):
        return "running"
    return "unavailable"


def _descriptor_paths(root: Path) -> tuple[Path, ...]:
    paths = [Path("runtime/runtime-descriptor.json"), Path("core/runtime-descriptor.json")]
    domains = root / "domains"
    try:
        children = sorted(domains.iterdir()) if domains.is_dir() and not domains.is_symlink() else ()
    except OSError:
        children = ()
    paths.extend(
        child.relative_to(root) / "runtime/runtime-descriptor.json"
        for child in children
        if child.is_dir() and not child.is_symlink()
    )
    return tuple(paths)


def _cache_root_is_outside_run(cache_root: Path, run_root: Path) -> bool:
    try:
        return not Path(cache_root).resolve().is_relative_to(Path(run_root).resolve(strict=True))
    except OSError:
        return False


def _read_json_file(root: Path, relative_path: str) -> Mapping[str, object] | None:
    return _read_json_path(root, Path(relative_path))


def _read_json_path(root: Path, relative_path: Path) -> Mapping[str, object] | None:
    path = root / relative_path
    try:
        if path.is_symlink() or not path.is_file():
            return None
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root.resolve(strict=True)):
            return None
        value = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return value if isinstance(value, Mapping) else None


def _application_identity(
    manifest: Mapping[str, object] | None,
    context: Mapping[str, object] | None,
    descriptors: Sequence[Mapping[str, object]],
) -> tuple[str | None, str | None]:
    app_id: str | None = None
    app_version: str | None = None
    for value in (*descriptors, manifest or {}, context or {}):
        app = value.get("application")
        if isinstance(app, Mapping):
            app_id = app_id or _text(app, "application_id", "applicationId", "id")
            app_version = app_version or _text(
                app, "application_version", "applicationVersion", "version"
            )
        app_id = app_id or _text(value, "application_id", "applicationId")
        app_version = app_version or _text(
            value, "application_version", "applicationVersion", "version"
        )
        core = value.get("core")
        if isinstance(core, Mapping):
            core_input = core.get("input")
            if isinstance(core_input, Mapping):
                app_id = app_id or _text(core_input, "application_id", "applicationId")
                app_version = app_version or _text(
                    core_input, "application_version", "applicationVersion", "version"
                )
    return app_id, app_version


def _binding_records(value: Mapping[str, object] | None) -> tuple[tuple[str, Mapping[str, object]], ...]:
    if value is None:
        return ()
    records = value.get("bindings", value.get("domains"))
    if isinstance(records, Mapping):
        return tuple(
            (str(binding_id), record if isinstance(record, Mapping) else {})
            for binding_id, record in records.items()
            if isinstance(binding_id, str) and binding_id
        )
    if isinstance(records, (list, tuple)):
        return tuple(
            (binding_id, record)
            for record in records
            if isinstance(record, Mapping)
            if (binding_id := _text(record, "binding_id", "bindingId", "id")) is not None
        )
    direct_binding_id = _text(value, "binding_id", "bindingId")
    if direct_binding_id is not None:
        return ((direct_binding_id, value),)
    return ()


def _context_binding_records(
    value: Mapping[str, object] | None,
) -> tuple[tuple[str, Mapping[str, object]], ...]:
    if value is None:
        return ()
    domains = value.get("domains")
    if not isinstance(domains, Mapping):
        return ()
    records: list[tuple[str, Mapping[str, object]]] = []
    for binding_id, envelope in domains.items():
        if not isinstance(binding_id, str) or not binding_id:
            continue
        if isinstance(envelope, Mapping):
            records.append((binding_id, envelope))
        else:
            records.append((binding_id, {}))
    return tuple(records)


def _merge_binding_records(
    target: dict[str, dict[str, object]],
    records: Sequence[tuple[str, Mapping[str, object]]],
) -> None:
    for binding_id, record in records:
        current = target.setdefault(binding_id, {})
        current.update(
            {
                "domain_id": _text(record, "domain_id", "domainId") or current.get("domain_id"),
                "domain_version": _text(record, "domain_version", "domainVersion", "version") or current.get("domain_version"),
                "authority_id": _text(record, "authority_id", "authorityId") or current.get("authority_id"),
                "schema": _text(
                    record,
                    "schema",
                    "schema_id",
                    "schemaId",
                    "output_schema",
                    "outputSchema",
                    "domain_schema",
                    "domainSchema",
                    "result_schema",
                    "resultSchema",
                ) or current.get("schema"),
                "presentation": _safe_mapping(record.get("presentation", record.get("presentation_metadata")))
                or current.get("presentation", {}),
            }
        )


def _text(value: Mapping[str, object], *keys: str) -> str | None:
    for key in keys:
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _safe_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): _safe_value(item)
        for key, item in value.items()
        if isinstance(key, str)
    }


def _safe_value(value: object, *, depth: int = 0) -> object:
    if depth > 8:
        return None
    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float:
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {
            key: _safe_value(item, depth=depth + 1)
            for key, item in value.items()
            if isinstance(key, str)
        }
    if isinstance(value, (list, tuple)):
        return [_safe_value(item, depth=depth + 1) for item in value]
    return None


__all__ = ["ProjectionService", "project_core_timeline"]
