"""Application-selected constraints for the immutable pandapower Thread model."""

from __future__ import annotations

import json
from pathlib import Path

from capability_agent._safe_files import write_bound_text
from capstone_agent.kernel_capability_preparation import AuthorityModelBinding


def bind_thread_tool_catalog(path: Path, binding: AuthorityModelBinding) -> None:
    """Restrict model opening; retain registered scenario derivation contracts.

    Current-run admission verifies each derived context against frozen patches.
    A base-only context enum would reject those legitimate scenarios before
    their Authority calculation can run.
    """
    document = json.loads(path.read_text(encoding="utf-8"))
    for tool in document["tools"]:
        properties = tool["input_schema"].get("properties", {})
        if tool["capability"] == "context.open":
            properties["model_id"]["enum"] = [binding.model_id]
    write_bound_text(path, json.dumps(document, ensure_ascii=False, indent=2) + "\n")
