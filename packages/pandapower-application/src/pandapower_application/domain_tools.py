"""Application binding for the Pack-owned pandapower tool service."""

from __future__ import annotations

import hashlib
import json
import math
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
        return self.project_task_view(document)['diagram']

    def project_task_view(self, document: dict) -> dict:
        """Project the exact topology and attention of one admitted answer."""
        from pandapower_application.thread_network_view import project_endpoint_focus
        from pandapower_domain.authority import PandapowerArtifactAuthority
        from pandapower_domain.network_annotations import project_base_disconnections
        from pandapower_domain.execution import SimulatorCapabilityError

        owner = domain_workspace_id({'task_id': 'diagram', 'management': document['management']})
        authority = PandapowerArtifactAuthority(self._root / owner)
        contexts = set()
        endpoint_evidence = []
        ranked_views = []
        saved_rank_results = {}
        for receipt in document['references']:
            if receipt['authority_id'] != authority.authority_id:
                continue
            contexts.update(receipt.get('context_refs', ()))
            if receipt.get('capability_id') == 'topology.branch.endpoints.get':
                endpoint_evidence.extend(receipt['evidence_refs'])
            for reference in receipt['result_refs']:
                result = authority.verify_result(reference).document
                contexts.add(result['context_ref'])
                if receipt.get('capability_id') == 'result.branches.rank':
                    saved_rank_results[reference] = result
                    if receipt.get('view_refs'):
                        ranked_views.append((reference, result, receipt['view_refs']))
            for reference in receipt['evidence_refs']:
                contexts.add(authority.verify_evidence(reference).document['context_ref'])
        if len(contexts) != 1:
            raise ValueError('task has no unique diagram context')
        context_ref = contexts.pop()
        context = authority.verify_context(context_ref).document
        executor = self._executor(owner)
        topology = executor.invoke('operator.diagram.get', {'context_ref': context_ref})
        if (topology.get('context_ref') != context_ref
                or topology.get('revision_ref') != context['revision_ref']):
            raise ValueError('task diagram context changed')
        diagram = {'schema': 'capstone-network-diagram/1.0',
                'model': {'id': context['model_id'], 'revision': context['revision_ref'], 'source': authority.authority_id},
                'coordinate_system': topology['coordinate_system'], 'buses': topology['buses'],
                'branches': topology['branches'], 'disconnections': project_base_disconnections(topology)}

        focus = project_endpoint_focus(topology, endpoint_evidence, authority, executor,
                                       context_ref, context['revision_ref'])
        if not ranked_views and saved_rank_results:
            for call in reversed(document.get('tool_calls', ())):
                arguments = call['arguments']
                reference = arguments.get('result_ref')
                if (self._capabilities.get(call['name']) != 'result.branches.rank' or not isinstance(reference, str)
                        or reference not in saved_rank_results):
                    continue
                try:
                    ranked = executor.invoke('result.branches.rank', arguments)
                except (SimulatorCapabilityError, ValueError):
                    continue
                if (ranked.get('result_ref') == reference and ranked.get('context_ref') == context_ref
                        and ranked.get('revision_ref') == context['revision_ref']):
                    selected = [row['branch_ref'] for row in ranked['branches'][:20]]
                    ranked_views.append((reference, saved_rank_results[reference], selected))
                    break

        overlay = None
        known = {branch['id'] for branch in topology['branches']}
        for reference, result, selected in reversed(ranked_views):
            if result.get('revision_ref') != context['revision_ref']:
                continue
            rows = {row['branch_ref']: row for row in result.get('branch_results', ())}
            if any(ref not in rows for ref in selected):
                continue
            ranked_focus = []
            values = []
            for ref in selected:
                row = rows[ref]
                kind = row['element_kind']
                identifier = f"{kind}:{row['pandapower_index']}"
                ids = [identifier + ':mv', identifier + ':lv'] if kind == 'trafo3w' else [identifier]
                ranked_focus.extend(item for item in ids if item in known)
                value = row.get('loading_percent')
                if kind == 'line' and identifier in known and type(value) in (int, float) and math.isfinite(value):
                    values.append({'id': identifier, 'value': value})
            if ranked_focus:
                focus = list(dict.fromkeys([*ranked_focus, *focus]))[:20]
                if values:
                    overlay = {'metric': 'loading_percent', 'unit': '%',
                               'source_ref': reference, 'values': values}
                break
        return {'schema': 'capstone-network-view/2.0', 'ordinal': 1, 'diagram': diagram,
                'layer': {'focus_ids': focus, 'next_focus_ids': [], 'overlay': overlay}}

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
