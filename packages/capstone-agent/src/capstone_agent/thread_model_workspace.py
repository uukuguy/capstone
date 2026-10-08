"""Application-owned opened models; execution Contexts remain immutable."""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .model_identity import validate_model_id
from .network_diagram import normalize_network_diagram
from .thread_protocol import ModelContextSnapshot, ThreadProtocolError, ThreadSnapshot

MODEL_COMMANDS = frozenset({"open_model", "activate_model", "close_model"})
MAX_OPEN_MODELS = 64
MAX_WORKSPACE_BYTES = 64 * 1024
_ENTRY_FIELDS = {"entry_id", "model_id", "model_revision", "implementation_family",
                 "authority_model_ref", "display_name", "diagram_provider_id", "last_active_seq"}


def model_entry(context: Any, seq: int, metadata: Any = None) -> dict[str, Any]:
    identity = f"{context.implementation_family}\0{context.model_id}\0{context.model_revision}"
    return {
        "entry_id": "mdl_" + hashlib.sha256(identity.encode()).hexdigest()[:24],
        "model_id": context.model_id, "model_revision": context.model_revision,
        "implementation_family": context.implementation_family,
        "authority_model_ref": getattr(metadata, "authority_model_ref", None),
        "display_name": getattr(metadata, "display_name", None) or context.model_id,
        "diagram_provider_id": getattr(metadata, "diagram_provider_id", None),
        "last_active_seq": seq,
    }


def validate_workspace(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"models", "current_entry_id"}:
        raise ThreadProtocolError("model workspace is invalid")
    models = value["models"]
    if not isinstance(models, list) or not 1 <= len(models) <= MAX_OPEN_MODELS:
        raise ThreadProtocolError("model workspace size is invalid")
    identifiers = set()
    for entry in models:
        if not isinstance(entry, dict) or set(entry) != _ENTRY_FIELDS:
            raise ThreadProtocolError("opened model is invalid")
        try:
            validate_model_id(entry["model_id"])
        except ValueError:
            raise ThreadProtocolError("opened model identity is invalid") from None
        for name in ("entry_id", "model_revision", "implementation_family", "display_name"):
            if not isinstance(entry[name], str) or not entry[name].strip() or len(entry[name]) > 256:
                raise ThreadProtocolError("opened model field is invalid")
        for name in ("authority_model_ref", "diagram_provider_id"):
            if entry[name] is not None and (not isinstance(entry[name], str) or not entry[name] or len(entry[name]) > 256):
                raise ThreadProtocolError("opened model reference is invalid")
        if type(entry["last_active_seq"]) is not int or entry["last_active_seq"] < 0 or entry["entry_id"] in identifiers:
            raise ThreadProtocolError("opened model sequence or identity is invalid")
        identifiers.add(entry["entry_id"])
    if value["current_entry_id"] not in identifiers:
        raise ThreadProtocolError("current model is not open")
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    if len(encoded.encode()) > MAX_WORKSPACE_BYTES:
        raise ThreadProtocolError("model workspace is too large")
    return json.loads(encoded)


def synchronize_workspace(value: Any, snapshot: ThreadSnapshot, catalog: Any = None) -> dict[str, Any]:
    """Migrate an active-only Thread and mirror legacy activation or rollback."""
    context = snapshot.active_model_context
    workspace = validate_workspace(value) if value is not None else None
    entry = model_entry(context, snapshot.last_event_seq)
    if workspace is not None and workspace["current_entry_id"] == entry["entry_id"]:
        return workspace
    existing = next((item for item in workspace["models"] if item["entry_id"] == entry["entry_id"]), None) if workspace is not None else None
    metadata = None
    if existing is None and catalog is not None:
        try:
            metadata = catalog.resolve(context.model_id)
        except (LookupError, TypeError, ValueError, RuntimeError):
            pass
    entry = model_entry(context, snapshot.last_event_seq, metadata)
    if workspace is None:
        return validate_workspace({"models": [entry], "current_entry_id": entry["entry_id"]})
    if existing is None:
        workspace["models"].append(entry)
    else:
        existing["last_active_seq"] = snapshot.last_event_seq
    workspace["current_entry_id"] = entry["entry_id"]
    return validate_workspace(workspace)


def workspace_projection(workspace: dict[str, Any], snapshot: ThreadSnapshot, blocked_reason: str | None) -> dict[str, Any]:
    return {"schema": "capstone-thread-model-workspace/1", "thread_id": snapshot.thread_id,
            "run_id": snapshot.run.run_id, "event_seq": snapshot.last_event_seq,
            **validate_workspace(workspace), "blocked_reason": blocked_reason}


def workspace_has_capacity(workspace: dict[str, Any], target: Any) -> bool:
    identity = model_entry(target, 0)["entry_id"]
    return len(workspace["models"]) < MAX_OPEN_MODELS or any(item["entry_id"] == identity for item in workspace["models"])


@dataclass(frozen=True)
class WorkspaceChange:
    workspace: dict[str, Any]
    context: ModelContextSnapshot | None = None
    diagram: Mapping[str, Any] | None = None
    changed: bool = True


def workspace_outcome(command: Mapping[str, Any], before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    current = next(item for item in after["models"] if item["entry_id"] == after["current_entry_id"])
    payload = {"command_id": command["command_id"], "kind": command["kind"], "current_model_name": current["display_name"]}
    if command["kind"] == "close_model":
        closed = next(item for item in before["models"] if item["entry_id"] == command["payload"]["entry_id"])
        payload["closed_model_name"] = closed["display_name"]
    return payload


def prepare_workspace_change(snapshot: ThreadSnapshot, workspace: dict[str, Any], command: Mapping[str, Any],
                             catalog: Any, family_available: Callable[[str], bool]) -> tuple[WorkspaceChange | None, str | None]:
    if snapshot.current_attempt is not None:
        return None, "attempt_in_progress"
    if snapshot.pending_model_switch is not None or snapshot.pending_selection is not None:
        return None, "context_change_pending"
    state = validate_workspace(workspace)
    kind, payload = command["kind"], command["payload"]
    target = None
    if kind == "open_model":
        if catalog is None:
            return None, "model_catalog_unavailable"
        expected_revision = payload.get("model_revision")
        if expected_revision is not None:
            target = next((item for item in state["models"] if item["model_id"] == payload["model_id"] and item["model_revision"] == expected_revision), None)
        try:
            descriptor = catalog.resolve(payload["model_id"])
            if not descriptor.available:
                return None, descriptor.unavailable_reason or "model_unavailable"
            if target is None:
                if expected_revision is not None and descriptor.model_revision != expected_revision:
                    return None, "model_revision_unavailable"
                target = model_entry(descriptor, snapshot.last_event_seq + 1, descriptor)
        except (LookupError, TypeError, ValueError, RuntimeError):
            return None, "model_unavailable"
        existing = next((item for item in state["models"] if item["entry_id"] == target["entry_id"]), None)
        if existing is not None:
            target = existing
        elif len(state["models"]) >= MAX_OPEN_MODELS:
            return None, "opened_model_limit"
        else:
            state["models"].append(target)
    else:
        target = next((item for item in state["models"] if item["entry_id"] == payload["entry_id"]), None)
        if target is None:
            return None, "model_not_open"
        if kind == "close_model":
            if len(state["models"]) == 1:
                return None, "last_model_required"
            state["models"] = [item for item in state["models"] if item["entry_id"] != target["entry_id"]]
            if target["entry_id"] != state["current_entry_id"]:
                return WorkspaceChange(validate_workspace(state)), None
            target = max(state["models"], key=lambda item: item["last_active_seq"])
    if target["entry_id"] == state["current_entry_id"]:
        return WorkspaceChange(state, changed=False), None
    if not family_available(target["implementation_family"]):
        return None, "worker_unavailable"
    context = ModelContextSnapshot(id="ctx_" + secrets.token_hex(10), model_id=target["model_id"],
                                   model_revision=target["model_revision"], implementation_family=target["implementation_family"],
                                   selection_revision="sel_0", enabled_profiles=())
    diagram = None
    if callable(getattr(catalog, "diagram", None)):
        try:
            diagram = normalize_network_diagram(catalog.diagram(context.model_id, context.model_revision))
            if diagram["model"]["id"] != context.model_id or diagram["model"]["revision"] != context.model_revision:
                return None, "model_preparation_failed"
        except (LookupError, TypeError, ValueError, RuntimeError, OSError):
            return None, "model_preparation_failed"
    target["last_active_seq"] = snapshot.last_event_seq + 1
    state["current_entry_id"] = target["entry_id"]
    return WorkspaceChange(validate_workspace(state), context, diagram), None
