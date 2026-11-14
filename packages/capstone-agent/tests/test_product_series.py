import pytest

from capstone_agent.product_series import transition


def ref(name):
    return {'schema': 'capstone-product-ref/1', 'thread_id': 'thr_one',
        'product_id': name, 'origin': 'native_file', 'scope': 'instruction',
        'event_seq': 1, 'revision': None, 'digest': 'a'*64,
        'work_id': 'work_one', 'attempt_id': 'attempt_one',
        'producer_attempt_id': 'attempt_one'}


def test_membership_is_explicit_and_adoption_is_independent():
    original, revised = ref('original'), ref('revised')
    state = transition(None, thread_id='thr_one', series_id='series_one',
        expected_revision=0, operation='register', product=original)
    assert state['revision'] == 1 and state['adopted_ref'] is None
    with pytest.raises(ValueError, match='member'):
        transition(state, thread_id='thr_one', series_id='series_one',
            expected_revision=1, operation='adopt', product=revised)
    state = transition(state, thread_id='thr_one', series_id='series_one',
        expected_revision=1, operation='register', product=revised)
    adopted = transition(state, thread_id='thr_one', series_id='series_one',
        expected_revision=2, operation='adopt', product=revised)
    assert adopted['adopted_ref'] == revised
    assert state['adopted_ref'] is None
    cleared = transition(adopted, thread_id='thr_one', series_id='series_one',
        expected_revision=3, operation='clear', product=None)
    assert cleared['adopted_ref'] is None and cleared['members'] == [original, revised]


def test_conflicts_and_cross_thread_references_do_not_change_state():
    state = transition(None, thread_id='thr_one', series_id='series_one',
        expected_revision=0, operation='register', product=ref('original'))
    for changes, reason in [({'expected_revision': 0}, 'revision'),
                            ({'product': {**ref('other'), 'thread_id': 'thr_other'}}, 'scope')]:
        args = dict(thread_id='thr_one', series_id='series_one',
            expected_revision=1, operation='register', product=ref('revised'))
        with pytest.raises(ValueError, match=reason):
            transition(state, **{**args, **changes})
    assert state['revision'] == 1 and len(state['members']) == 1
