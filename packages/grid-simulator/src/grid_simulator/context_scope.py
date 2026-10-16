"""Host-selected context ancestry limits for an isolated simulator workspace."""

from __future__ import annotations

import json
from pathlib import Path

from grid_simulator.models import ContextStore


SCOPE_FILE = "application-context-scope.json"


def require_context_scope(workspace: Path, store: ContextStore, capability: str, arguments: dict) -> None:
    path = workspace / SCOPE_FILE
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink():
        raise ValueError("context scope must be a regular host-owned file")
    scope = json.loads(path.read_text())
    if not isinstance(scope, dict) or set(scope) != {"schema", "root_context_ref"} or scope["schema"] != "grid-context-scope/1":
        raise ValueError("context scope is invalid")
    root = store.require(scope["root_context_ref"])
    if capability == "model.create":
        raise ValueError("new independent models are outside the selected context scope")
    if capability == "context.open" and arguments.get("model_id") != root.model_id:
        raise ValueError("model is outside the selected context scope")
    reference = arguments.get("context_ref")
    if reference is None:
        return
    seen: set[str] = set()
    for _ in range(256):
        if not isinstance(reference, str) or reference in seen:
            raise ValueError("context ancestry is invalid")
        seen.add(reference)
        current = store.require(reference)
        if current.model_id != root.model_id:
            raise ValueError("context ancestry crosses model identity")
        if current.context_ref == root.context_ref:
            return
        reference = current.parent_context_ref
    raise ValueError("context ancestry exceeds verification limit")
