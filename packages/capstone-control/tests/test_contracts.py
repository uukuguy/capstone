from copy import deepcopy

import pytest

from capstone_control.contracts import ContractError, validate_goal_request


def request():
    return {
        'schema': 'capstone-control-goal-create/1',
        'operation_id': 'create-1', 'objective': 'Prepare and verify a report',
        'acceptance_criteria': ['Verified original file and saved report'],
        'max_delegations': 2, 'deadline_at': '2099-01-01T00:00:00Z',
        'tasks': [
            {'task_id': 'draft', 'objective': 'Save an original draft',
             'delivery_requirements': ['draft.txt'], 'depends_on': [],
             'agent_id': 'capstone', 'mode': 'single', 'max_attempts': 1},
            {'task_id': 'verify', 'objective': 'Read original and verify',
             'delivery_requirements': ['report.md'], 'depends_on': ['draft'],
             'agent_id': 'capstone', 'mode': 'goal', 'max_attempts': 3},
        ],
    }


def test_valid_request_is_detached_and_preserves_exact_objectives():
    source = request()
    parsed = validate_goal_request(source)
    assert parsed == source
    parsed['tasks'][0]['depends_on'].append('changed')
    assert source['tasks'][0]['depends_on'] == []


@pytest.mark.parametrize('field,value', [
    ('max_delegations', True), ('max_delegations', 0),
    ('deadline_at', '2099-01-01T00:00:00'),
    ('objective', ''), ('acceptance_criteria', []),
    ('operation_id', '../unsafe'), ('unknown', 1),
])
def test_invalid_goal_contract(field, value):
    source = request()
    source[field] = value
    with pytest.raises(ContractError):
        validate_goal_request(source)


@pytest.mark.parametrize('mutate', [
    lambda x: x['tasks'][0].update(depends_on=['verify']),
    lambda x: x['tasks'][1].update(depends_on=['missing']),
    lambda x: x['tasks'][1].update(task_id='draft'),
    lambda x: x['tasks'][0].update(max_attempts=True),
    lambda x: x['tasks'][0].update(mode='single', max_attempts=2),
    lambda x: x['tasks'][0].update(agent_id=''),
    lambda x: x['tasks'][0].update(thread_id='caller-forged'),
])
def test_invalid_task_graph_or_execution_contract(mutate):
    source = deepcopy(request())
    mutate(source)
    with pytest.raises(ContractError):
        validate_goal_request(source)
