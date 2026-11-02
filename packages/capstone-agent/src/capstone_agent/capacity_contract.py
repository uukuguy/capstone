"""Resolve application capacity disclosure from the selected runtime profile.

This module discloses policy; it does not replace consumer enforcement.
"""
import json
from pathlib import Path

from capstone_agent.application_capacity import CapacityProfile, current_capacity
from capstone_agent.model_context_policy import checked_context_policy


SCHEMA = 'capstone-capacity-contract/1'
POLICY_SCHEMA = 'capstone-capacity-policy/1'


def load_capacity_policy(path: Path | None = None) -> dict:
    """Load explicit metadata, from a checkout or the backend image."""
    candidates = ([Path(path)] if path is not None else
                  [parent / 'configs/runtime/capacity-policy.json'
                   for parent in Path(__file__).resolve().parents] +
                  [Path('/opt/general/configs/runtime/capacity-policy.json')])
    for candidate in candidates:
        if candidate.is_file():
            policy = json.loads(candidate.read_text(encoding='utf-8'))
            if policy.get('schema') != POLICY_SCHEMA:
                raise ValueError('capacity policy schema is invalid')
            return policy
    raise FileNotFoundError('capacity-policy.json is required for capacity disclosure')


def capacity_contract(profile: CapacityProfile | None = None, *, policy: dict | None = None,
                      context_policy: dict | None = None) -> dict:
    """Return exact effective values with exhaustive, disjoint policy coverage."""
    selected = current_capacity() if profile is None else profile
    metadata = load_capacity_policy() if policy is None else policy
    if metadata.get('schema') != POLICY_SCHEMA:
        raise ValueError('capacity policy schema is invalid')
    dimensions = {}
    required = {'category', 'scope', 'protected_resource', 'anomaly', 'recovery',
                'enforcement', 'model_visible', 'basis', 'review_needed'}
    for group in metadata['groups']:
        if not required <= group.keys():
            raise ValueError('capacity policy metadata is incomplete')
        for member in group['members']:
            if member in dimensions:
                raise ValueError(f'duplicate capacity policy member: {member}')
            dimensions[member] = {key: group[key] for key in required}
            dimensions[member]['policy_group'] = group['id']
    if set(dimensions) != set(selected.values) or set(metadata['units']) != set(selected.values):
        raise ValueError('capacity policy coverage does not match profile')
    for name, details in dimensions.items():
        details.update(effective=selected.values[name], unit=metadata['units'][name],
                       source='application_capacity')
        details['description'] = name.replace('_', ' ')
    document = {'schema': SCHEMA, 'profile_fingerprint': selected.fingerprint,
                'mode': selected.mode, 'dimensions': dimensions,
                'recovery_note': 'Effective values are current. Recovery notes describe the intended '
                    'policy, not proof that every consumer supports automatic recovery; review_needed '
                    'marks bounds whose resource sizing still requires validation.'}
    if context_policy is not None:
        context = checked_context_policy(context_policy)
        for name, field in (('model_context_tokens', 'context_window_tokens'),
                            ('model_output_tokens', 'max_output_tokens')):
            dimensions[name].update(effective=context[field], source='selected_model_context_policy')
        document['model_context'] = {
            **context, 'compression_threshold_tokens':
            context['context_window_tokens'] - context['compaction_reserve_tokens'],
            'source': 'selected_model_context_policy'}
    return document


def capacity_model_guidance(profile: CapacityProfile | None = None, *,
                            context_policy: dict | None = None) -> str:
    """Compact pre-call guidance; omit transport and browser housekeeping."""
    contract = capacity_contract(profile, context_policy=context_policy)
    groups = {}
    for name, details in contract['dimensions'].items():
        if details['model_visible']:
            groups.setdefault(details['policy_group'], []).append(
                f"{name}={details['effective']} {details['unit']}")
    intro = ('Capacity applies before tool calls. Independent requests queue in provider/gateway relays; '
             'concurrency is not a total-call or total-round ceiling. Follow returned page cursors. '
             'Use durable references and bounded reads; storage quotas are separate from context '
             'and processing budgets. Compact context and spill large outputs to products. '
             'The accepted task deadline below is the actual deployment ceiling; checkpoint before it. '
             'These are default design bounds, not measured resource limits; valid workloads '
             'may need operator review. mcp_call_count=0 means no total-call ceiling. '
             'research_round_count applies only to the research controller, not native LLM turns. '
             'The machine capacity contract contains all request and product limits. Effective limits:')
    guidance = intro + '\n' + '\n'.join(f'{group}: ' + ', '.join(items)
                                        for group, items in groups.items())
    if 'model_context' in contract:
        guidance += ('\nCompression threshold: ' +
                     str(contract['model_context']['compression_threshold_tokens']) +
                     ' tokens; source=selected_model_context_policy.')
    return guidance
