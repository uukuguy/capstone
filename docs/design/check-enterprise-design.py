"""Validate design contracts and external acceptance fixture arithmetic, not runtime."""
from pathlib import Path
from datetime import date, timedelta
import json
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent
schema = json.loads((ROOT / 'enterprise-contracts.schema.json').read_text())
Draft202012Validator.check_schema(schema)
def validator(name):
    return Draft202012Validator({**schema, '$ref': '#/$defs/' + name})

payloads = {
    'message': {'text': '分析资料', 'resource_refs': []},
    'goal.revise': {'text': '补充图表', 'resource_refs': []},
    'input.respond': {'request_id': 'q1', 'expected_goal_revision': 1, 'response': '使用版本2', 'resource_refs': []},
    'pause': {}, 'resume': {}, 'cancel': {'reason': '用户取消'},
    'action.resolve': {'action_id': 'a1', 'outcome': 'confirmed_not_executed', 'confirmation_ref': 'receipt1'},
    'budget.increase': {'policy_ref': 'approved-policy2'},
    'thread.rename': {'title': '月度分析'}, 'thread.archive': {'archived': True},
    'workspace.configure': {'profile_refs': ['general@1'], 'resource_grant_refs': ['grant1']},
}
for kind, payload in payloads.items():
    target = 'thread' if kind.startswith('thread.') else 'workspace' if kind.startswith('workspace.') else 'work'
    command = dict(schema='capstone-command/1', command_id='c1', target_kind=target,
                   target_id='target1', expected_revision=0, kind=kind, payload=payload)
    validator('command').validate(command)
    assert list(validator('command').iter_errors({**command, 'payload': {**payload, 'undeclared': True}}))
    assert list(validator('command').iter_errors({**command, 'expected_revision': -1}))
    assert list(validator('command').iter_errors({**command, 'target_kind': 'wrong'}))

matrix = json.loads((ROOT / 'enterprise-state-transitions.json').read_text())
transitions = {(t['from'], t['trigger']): t['to'] for t in matrix['transitions']}
assert len(transitions) == len(matrix['transitions'])
assert transitions['running', 'pause_requested'] == 'running'
assert transitions['running', 'pause_settled'] == 'paused'
assert transitions['cancelled', 'resume'] == 'queued'
assert ('paused', 'delivery_complete') not in transitions
assert 'all_required_satisfied' in matrix['guards']['delivery_complete']
assert 'inputs_ready' not in matrix['guards']['start']
assert 'no_viable_authorized_next_action' in matrix['guards']['missing_input']
assert 'no_viable_authorized_next_action' in matrix['guards']['need_input']
assert 'isolate_unknown_actions_and_conflicting_dependencies' in matrix['guards']['resume']
assert 'required_deliverables_persisted' in matrix['guards']['delivery_complete']
assert 'no_stale_delivery_dependencies' in matrix['guards']['delivery_complete']
assert 'usable_message_or_artifacts' in matrix['guards']['delivery_partial']
assert transitions['waiting_input', 'input_applied'] == 'queued'
assert transitions['paused', 'input_applied'] == 'paused'
assert transitions['running', 'input_applied'] == 'running'
assert ('cancelled', 'input_applied') not in transitions
assert transitions['paused', 'revise_goal'] == 'paused'
assert 'open_request_matches_goal' in matrix['guards']['input_applied']
assert 'response_persisted' in matrix['guards']['input_applied']
assert 'viable_authorized_next_action' not in matrix['guards']['input_applied']

# External synthetic business fixture: not a production tool or Kernel schema.
# Independent expected totals are frozen in enterprise-acceptance.json.
fixture = json.loads((ROOT / 'enterprise-acceptance.json').read_text())
start, end = date.fromisoformat(fixture['start']), date.fromisoformat(fixture['end_exclusive'])
rows = []
for offset in range((end-start).days):
    for region, pattern in fixture['patterns'].items():
        for slot in range(96):
            p = pattern[slot % 4]
            rows.append(dict(region=region, day=str(start+timedelta(days=offset)), slot=slot,
                             price=p[0], flow=p[1], limit=p[2], available=p[3], actual=p[4]))
assert len(rows) == fixture['expected']['rows']
for region, expected in fixture['expected']['regions'].items():
    all_rows = [r for r in rows if r['region'] == region]
    events = [r for r in all_rows if r['price'] < 0]
    observed = {
        'floor_rate': sum(r['price'] == -50 for r in all_rows)/len(all_rows),
        'negative_hours': len(events)/4,
        'event_channel_utilization': sum(r['flow'] for r in events)/sum(r['limit'] for r in events),
        'event_renewable_utilization': sum(r['actual'] for r in events)/sum(r['available'] for r in events),
    }
    for key, value in expected.items():
        assert abs(observed[key]-value) <= 1e-9, (region, key, observed[key], value)
print('PASS: 11 strict command variants; 33 negative cases; transition invariants; 11712 synthetic rows and frozen oracles.')
