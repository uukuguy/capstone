import pytest

from capstone_agent.goal_receipts import parse_goal_proposal


def test_boundary_requires_exact_identity_and_saved_delivery():
    from datetime import datetime, timezone
    from capstone_agent.goal_receipts import settle_goal_proposal
    goal = {'schema': 'capstone-work-goal/1', 'objective': 'Report', 'objective_revision': 2,
        'generation': 3, 'state': 'running', 'reason': None, 'max_attempts': 3,
        'attempts_admitted': 1, 'deadline_at': '2099-01-01T00:00:00Z',
        'last_settled_attempt_id': None}
    args = dict(objective_revision=2, generation=3, attempt_id='attempt_one',
                now=datetime(2026, 11, 16, tzinfo=timezone.utc), saved_product_refs=(),
                delivery_saved=True)
    completed = settle_goal_proposal(goal, proposal(disposition='complete', next_instruction=None), **args)
    assert completed['state'] == 'completed'
    assert completed['last_settled_attempt_id'] == 'attempt_one'
    with pytest.raises(ValueError):
        settle_goal_proposal(goal, proposal(), **{**args, 'generation': 2})
    with pytest.raises(ValueError):
        settle_goal_proposal(goal, proposal(disposition='complete', next_instruction=None),
                             **{**args, 'delivery_saved': False})
    with pytest.raises(ValueError):
        settle_goal_proposal(goal, proposal(product_refs=['missing']), **args)


def test_boundary_pauses_at_budget_instead_of_continuing():
    from datetime import datetime, timezone
    from capstone_agent.goal_receipts import settle_goal_proposal
    goal = {'schema': 'capstone-work-goal/1', 'objective': 'Report', 'objective_revision': 1,
        'generation': 1, 'state': 'running', 'reason': None, 'max_attempts': 1,
        'attempts_admitted': 1, 'deadline_at': '2099-01-01T00:00:00Z',
        'last_settled_attempt_id': None}
    result = settle_goal_proposal(goal, proposal(), objective_revision=1, generation=1,
        attempt_id='attempt_one', now=datetime(2026, 11, 16, tzinfo=timezone.utc),
        saved_product_refs=(), delivery_saved=True)
    assert result['state'] == 'paused'
    assert result['reason'] == 'attempt_budget_exhausted'


def proposal(**changes):
    return {'schema': 'capstone-work-goal-proposal/1', 'disposition': 'continue',
            'summary': 'Draft saved', 'next_instruction': 'Review the draft',
            'waiting_reason': None, 'product_refs': [], **changes}


def test_continue_requires_instruction():
    with pytest.raises(ValueError):
        parse_goal_proposal(proposal(next_instruction=''))


def test_wait_requires_reason():
    with pytest.raises(ValueError):
        parse_goal_proposal(proposal(disposition='wait', next_instruction=None))


def test_model_cannot_supply_execution_identity():
    with pytest.raises(ValueError):
        parse_goal_proposal(proposal(attempt_id='attempt_forged'))


def test_complete_is_only_a_proposal():
    value = proposal(disposition='complete', next_instruction=None)
    assert parse_goal_proposal(value) == value


@pytest.mark.parametrize('refs', [['x'] * 65, [1], 'artifact'])
def test_product_references_are_bounded(refs):
    with pytest.raises(ValueError):
        parse_goal_proposal(proposal(product_refs=refs))
