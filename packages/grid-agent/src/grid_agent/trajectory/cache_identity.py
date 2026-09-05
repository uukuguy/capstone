"""Deterministic, non-authoritative identities for trajectory cache entries."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from capability_agent.trajectory.canonical import canonical_json_bytes
from capability_agent.trajectory.artifacts import ArtifactPointer
from capability_agent.trajectory.replay import ReplayEventLike


PROJECTION_SOURCE_VERSION = "projected-source/2.0"


@dataclass(frozen=True, slots=True)
class CacheIdentity:
    cache_key: str
    source_fingerprint: str
    cacheable: bool


def collect_native_dependencies(events: Sequence[ReplayEventLike], artifacts: object) -> tuple[dict[str, object], ...]:
    """Verify exactly the references current projection code may dereference."""
    references: set[str] = set()
    for event in events:
        references.update((*event.refs.produced, *event.refs.consumed, *event.refs.evidence))
        if event.event_type in {"context.projected", "context.injected"}:
            value = event.payload.get("artifact_ref")
            if isinstance(value, str) and value:
                references.add(value)
    verify = getattr(artifacts, "verify_reference", None)
    dependencies: list[dict[str, object]] = []
    for reference in sorted(references):
        try:
            pointer = verify(reference) if callable(verify) else None
        except Exception:
            pointer = None
        if isinstance(pointer, ArtifactPointer):
            dependencies.append({"ref": reference, "status": "verified", "kind": pointer.kind, "path": pointer.relative_path, "sha256": pointer.sha256, "size": pointer.size_bytes})
        else:
            dependencies.append({"ref": reference, "status": "unavailable"})
    return tuple(dependencies)


def build_identity(*, run_root: Path, analysis_id: str, events: Sequence[ReplayEventLike], failure: object | None, metadata_inputs: Sequence[dict[str, object]], dependencies: Sequence[dict[str, object]], source_kind: str, projection_schema: str, legacy_source_fingerprint: str | None = None, legacy_diagnostics: Sequence[object] = ()) -> CacheIdentity:
    public_payload: dict[str, Any] = {
        "version": PROJECTION_SOURCE_VERSION,
        "analysis_id": analysis_id,
        "source_kind": source_kind,
        "events": [_event_identity(event) for event in events],
        "trusted_length": len(events),
        "failure": None if failure is None else getattr(failure, "code", "uncacheable"),
        "metadata": list(metadata_inputs),
        "dependencies": list(dependencies),
        "legacy_source_fingerprint": legacy_source_fingerprint,
        "legacy_diagnostics": [
            {"code": getattr(item, "code", "unknown"), "message": getattr(item, "message", "")}
            for item in legacy_diagnostics
        ],
    }
    public_digest = hashlib.sha256(canonical_json_bytes(public_payload)).hexdigest()
    cache_digest = hashlib.sha256(canonical_json_bytes({"public": public_digest, "run_root": str(run_root.resolve()), "projection_schema": projection_schema})).hexdigest()
    return CacheIdentity(cache_key=cache_digest, source_fingerprint=f"{PROJECTION_SOURCE_VERSION}:{public_digest}", cacheable=failure is None)


def _event_identity(event: ReplayEventLike) -> object:
    dump = getattr(event, "model_dump", None)
    if not callable(dump):
        raise TypeError("replay event does not support canonical identity")
    return dump(mode="json")


__all__ = ["CacheIdentity", "PROJECTION_SOURCE_VERSION", "build_identity", "collect_native_dependencies"]
