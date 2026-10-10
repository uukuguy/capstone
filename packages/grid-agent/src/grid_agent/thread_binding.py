"""Application-selected constraints for the immutable pandapower Thread model."""

from __future__ import annotations

import json
from pathlib import Path

from capability_agent._safe_files import write_bound_text
from capstone_agent.kernel_capability_preparation import AuthorityModelBinding


def bind_thread_tool_catalog(path: Path, binding: AuthorityModelBinding) -> None:
    """Restrict model-facing tools while preserving authority discovery tools."""
    document = json.loads(path.read_text(encoding="utf-8"))
    for tool in document["tools"]:
        properties = tool["input_schema"].get("properties", {})
        if tool["capability"] == "context.open":
            properties["model_id"]["enum"] = [binding.model_id]
        if "context_ref" in properties:
            # gridctl enforces the exact root and verified descendants. A static
            # enum would prevent the SDK from calling a legitimate scenario.
            if binding.context_identity_verifier is None:
                properties["context_ref"]["enum"] = [binding.context_ref]
            else:
                properties["context_ref"].pop('enum', None)
    write_bound_text(path, json.dumps(document, ensure_ascii=False, indent=2) + "\n")
