"""Application binding for the Pack-owned pandapower tool service."""

from __future__ import annotations

import hashlib
import json
import re

from pandapower_domain.tool_service import PandapowerToolService

_TASK_ID = re.compile(r'^[A-Za-z0-9_-]{1,80}$')


def domain_workspace_id(document: dict) -> str:
    """Bind an admitted management identity to one Pack workspace."""
    task_id = document.get('task_id')
    if not isinstance(task_id, str) or not _TASK_ID.fullmatch(task_id):
        raise ValueError('domain tool call is invalid')
    management = document.get('management')
    if management is None:
        return task_id
    from capstone_agent.structural_context import checked_management
    model = checked_management(management)['model']
    canonical = json.dumps(model, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return 'model-' + hashlib.sha256(canonical.encode()).hexdigest()[:40]


class PandapowerDomainToolService(PandapowerToolService):
    """Select the application workspace before entering domain execution."""

    def invoke(self, document: dict) -> dict:
        return super().invoke(document, workspace_id=domain_workspace_id(document))
