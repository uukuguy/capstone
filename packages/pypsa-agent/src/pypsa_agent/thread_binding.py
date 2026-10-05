"""Application-owned model lineage checks for an immutable PyPSA Thread."""

from collections.abc import Mapping
import json
from pathlib import Path

from capability_agent._safe_files import write_bound_text


def verify_bound_model_reference(authority: object, reference: str, *, model_id: str, base_ref: str) -> bool:
    """Accept only authority-verified descendants of the selected base revision."""
    verify = getattr(authority, "verify_model", None)
    if not callable(verify):
        return False
    seen: set[str] = set()
    for _ in range(64):
        if reference in seen:
            return False
        seen.add(reference)
        document = getattr(verify(reference), "document", None)
        if not isinstance(document, Mapping) or document.get("catalog_id") != model_id:
            return False
        if reference == base_ref:
            return True
        parent = document.get("parent_ref")
        if not isinstance(parent, str) or not parent:
            return False
        reference = parent
    return False


def bind_thread_tool_catalog(path: Path, model_id: str) -> None:
    """Keep model opening on the selected catalog; retain legitimate derivation."""
    document = json.loads(path.read_text(encoding="utf-8"))
    for tool in document["tools"]:
        if tool["capability"] == "model.open":
            tool["input_schema"]["properties"]["catalog_id"]["enum"] = [model_id]
    write_bound_text(path, json.dumps(document, ensure_ascii=False, indent=2) + "\n")
