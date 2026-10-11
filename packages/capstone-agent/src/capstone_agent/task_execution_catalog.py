"""Apply Pack-declared task restrictions to the registered semantic catalog."""

from __future__ import annotations

import json
from pathlib import Path

from capability_agent.tools.catalog import ToolCatalog, ToolDocument


def task_execution_catalog(claim, binding_id, runtime, source: Path, directory: Path) -> Path:
    goals = [goal for goal in claim.task_resolutions if goal.binding_id == binding_id and goal.execution_required]
    provider = getattr(runtime.profile, "task_provider", None)
    select = getattr(provider, "execution_capabilities", None)
    if not goals or not callable(select) or any(goal.status != "ready" for goal in goals):
        return source
    allowed = set()
    for goal in goals:
        capabilities = select(goal)
        if capabilities is None:
            return source
        if (not isinstance(capabilities, tuple) or len(capabilities) > 256
            or any(not isinstance(item, str) or not item or len(item) > 256 for item in capabilities)):
            raise ValueError("Pack task capabilities are invalid")
        allowed.update(capabilities)
    document = json.loads(source.read_text())
    tools = tuple(ToolDocument(**tool) for tool in document["tools"] if tool["capability"] in allowed)
    if not tools:
        raise ValueError("Pack task has no registered execution capabilities")
    path = directory / claim.attempt.attempt_id / binding_id / "tool-catalog.json"
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    return ToolCatalog(tools, protocol=document["protocol"]).materialize(path)
