import pytest

from capstone_agent.goal_receipts import parse_goal_proposal


def test_terminal_disposition_drops_unused_continuation_reference_selection():
    value = proposal(disposition='complete', next_instruction=None, authority_refs=[
        'context:sha256:' + 'a' * 64])
    assert 'authority_refs' not in parse_goal_proposal(value)
    with pytest.raises(ValueError, match='authority references'):
        parse_goal_proposal(proposal(authority_refs=value['authority_refs']))


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


def test_progress_channel_rejects_duplicate_proposals():
    from capstone_agent.goal_receipts import GoalProposalCapture
    capture = GoalProposalCapture()
    assert capture.observe({'event_type': 'unrelated', 'payload': {}}) is False
    event = {'event_type': 'goal_progress_proposed', 'payload': proposal()}
    assert capture.observe(event) is True
    assert capture.proposal == proposal()
    with pytest.raises(ValueError):
        capture.observe(event)


def test_goal_response_envelope_preserves_answer_and_checks_proposal():
    import json
    from capstone_agent.goal_receipts import decode_goal_response
    answer, progress = decode_goal_response(json.dumps({'schema': 'capstone-goal-response/1',
        'answer': 'Saved draft', 'progress': proposal()}))
    assert answer == 'Saved draft'
    assert progress == proposal()
    with pytest.raises(ValueError):
        decode_goal_response('I completed everything')


def test_goal_runtime_adapter_returns_delivery_and_emits_progress():
    import json
    from capstone_agent.goal_receipts import prompt_goal_runtime
    events = []
    class Runtime:
        enabled = False
        def enable_goal_response(self):
            self.enabled = True
        def prompt(self, instruction, **kwargs):
            assert self.enabled
            assert 'capstone-goal-response/1' in instruction
            return json.dumps({'schema': 'capstone-goal-response/1',
                'answer': 'Saved draft', 'progress': proposal()})
    assert prompt_goal_runtime(Runtime(), 'Write report', on_event=events.append,
                               correlation_id='attempt_one', on_heartbeat=None) == 'Saved draft'
    assert events == [{'event_type': 'goal_progress_proposed', 'payload': proposal()}]


@pytest.mark.parametrize('refs', [['x'] * 65, [1], 'artifact'])
def test_product_references_are_bounded(refs):
    with pytest.raises(ValueError):
        parse_goal_proposal(proposal(product_refs=refs))


def test_saved_product_names_come_only_from_current_attempt_publications():
    from capstone_agent.goal_receipts import published_goal_refs
    events=[{'attempt_id':'attempt_one','event_type':'native_artifact_published',
        'payload':{'artifact':{'artifact_id':'artifact_one','file_name':'draft.md'}}},
        {'attempt_id':'other','event_type':'native_artifact_published',
        'payload':{'artifact':{'artifact_id':'other','file_name':'foreign.md'}}}]
    assert set(published_goal_refs(events,'attempt_one'))=={'artifact_one','draft.md'}
