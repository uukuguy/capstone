"""Selection identity must bind ownership, index, location and bytes."""
import pytest

from capstone_agent.product_block_identity import selection_identity


def selection():
    return {'schema': 'capstone-local-product-selection/1',
        'parent_ref': {'schema': 'capstone-product-ref/1', 'thread_id': 'thr_one',
            'product_id': 'product_one', 'origin': 'native_file', 'scope': 'instruction',
            'event_seq': 1, 'revision': None, 'digest': 'a' * 64,
            'work_id': 'work_one', 'attempt_id': 'attempt_one', 'producer_attempt_id': None},
        'index_ref': 'b' * 64, 'block_id': 'block_0', 'content_digest': 'c' * 64,
        'purpose': 'historical-context'}


def test_identity_is_stable_and_distinguishes_repeated_paragraphs():
    value = selection()
    assert selection_identity(value) == selection_identity(dict(reversed(list(value.items()))))
    assert selection_identity(value) != selection_identity({**value, 'block_id': 'block_1'})


@pytest.mark.parametrize('field', ['index_ref', 'content_digest'])
def test_changed_index_or_content_changes_identity(field):
    value = selection()
    assert selection_identity(value) != selection_identity({**value, field: 'd' * 64})


def test_parent_ownership_is_part_of_identity():
    value = selection()
    other = {**value, 'parent_ref': {**value['parent_ref'], 'thread_id': 'thr_other'}}
    assert selection_identity(value) != selection_identity(other)


@pytest.mark.parametrize('patch', [
    {'purpose': 'authority-evidence'}, {'schema': 'unknown'}, {'index_ref': '../path'},
    {'block_id': '../path'}, {'content_digest': None}, {'text': 'untrusted replacement'},
])
def test_invalid_selection_is_rejected(patch):
    with pytest.raises(ValueError):
        selection_identity({**selection(), **patch})
