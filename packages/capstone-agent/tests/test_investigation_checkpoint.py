import pytest
from capstone_agent.general_pi_server import _checked_investigation_checkpoint


def test_checkpoint_requires_prepared_lineage_and_bounded_neutral_fields():
    record = {}
    event = {'type': 'investigation_checkpoint', 'schema': 'capstone-investigation-checkpoint/1',
             'checkpoint_id': 1, 'completed_leaf_calls': 12, 'state': 'context_prepared'}
    assert _checked_investigation_checkpoint(event, record)['state'] == 'context_prepared'
    assert _checked_investigation_checkpoint(event, record) == _checked_investigation_checkpoint(event, record)
    assert _checked_investigation_checkpoint({**event, 'state': 'response_received'}, record)['state'] == 'response_received'
    with pytest.raises(ValueError):
        _checked_investigation_checkpoint({**event, 'checkpoint_id': 2, 'state': 'response_received'}, record)
    with pytest.raises(ValueError):
        _checked_investigation_checkpoint({**event, 'completed_leaf_calls': True}, {})
    with pytest.raises(ValueError):
        _checked_investigation_checkpoint({**event, 'extra': 'unbounded text'}, {})
