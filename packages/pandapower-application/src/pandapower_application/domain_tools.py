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
    binding = checked_management(management)
    if 'work_scope' in binding:
        return binding['work_scope']
    model = binding['model']
    canonical = json.dumps(model, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return 'model-' + hashlib.sha256(canonical.encode()).hexdigest()[:40]


class PandapowerDomainToolService(PandapowerToolService):
    """Select the application workspace before entering domain execution."""

    def project_task_diagram(self, document: dict) -> dict:
        """Project the one exact authority context used by an admitted answer."""
        from pandapower_domain.authority import PandapowerArtifactAuthority
        from pandapower_domain.network_annotations import project_base_disconnections

        owner = domain_workspace_id({'task_id': 'diagram', 'management': document['management']})
        authority = PandapowerArtifactAuthority(self._root / owner)
        contexts = set()
        for receipt in document['references']:
            if receipt['authority_id'] != authority.authority_id:
                continue
            contexts.update(receipt.get('context_refs', ()))
            for reference in receipt['result_refs']:
                contexts.add(authority.verify_result(reference).document['context_ref'])
            for reference in receipt['evidence_refs']:
                contexts.add(authority.verify_evidence(reference).document['context_ref'])
        if len(contexts) != 1:
            raise ValueError('task has no unique diagram context')
        context_ref = contexts.pop()
        context = authority.verify_context(context_ref).document
        topology = self._executor(owner).invoke('operator.diagram.get', {'context_ref': context_ref})
        if (topology.get('context_ref') != context_ref
                or topology.get('revision_ref') != context['revision_ref']):
            raise ValueError('task diagram context changed')
        return {'schema': 'capstone-network-diagram/1.0',
                'model': {'id': context['model_id'], 'revision': context['revision_ref'], 'source': authority.authority_id},
                'coordinate_system': topology['coordinate_system'], 'buses': topology['buses'],
                'branches': topology['branches'], 'disconnections': project_base_disconnections(topology)}

    def invoke(self, document: dict, *, workspace_id: str | None = None) -> dict:
        # The application derives workspace ownership from the admitted document.
        del workspace_id
        from capstone_agent.structural_context import checked_management

        target = domain_workspace_id(document)
        management = document.get('management')
        if management is not None:
            checked = checked_management(management)
            document = {**document, 'management': checked}
            inputs = [{**item, 'owner': item['owner'].get('legacy_task') or domain_workspace_id({
                'task_id': document['task_id'], 'management': {'schema': checked['schema'], **item['owner']}})}
                for item in checked.get('authority_inputs', ())]
        else:
            inputs = []
        if inputs:
            return super().invoke(document, workspace_id=target, authority_inputs=inputs)
        return super().invoke(document, workspace_id=target)
