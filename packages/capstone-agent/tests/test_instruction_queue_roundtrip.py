"""Strict Work queue roundtrips preserve durable inputs and discard projections."""
from copy import deepcopy
from dataclasses import replace
import pytest

from capstone_agent.thread_protocol import ThreadSnapshot, ThreadProtocolError
from capstone_agent.thread_service import ThreadCreator, InMemoryThreadService
from capstone_agent.application_capacity import limits


def queued_snapshot():
    class Store:
        def create_thread(self, snapshot):
            return snapshot
    snapshot = ThreadCreator(Store(), None).create(model_free=True)
    store = InMemoryThreadService(snapshot)
    command = {'schema': 'capstone-command/2', 'command_id': 'cmd_initial',
        'idempotency_key': 'initial', 'thread_id': snapshot.thread_id, 'kind': 'work_message',
        'target': {'kind': 'work', 'id': 'new', 'expected_revision': 0}, 'payload': {'text': 'Initial intent'}}
    assert store.submit_command(command).status == 'accepted'
    snapshot = store.snapshot(snapshot.thread_id)
    work = deepcopy(snapshot.works[0])
    work['instruction_queue'] = [
        {'id': 'instruction_' + str(index), 'attempt_id': 'attempt_original', 'sequence': index + 1,
         'text': 'Direction ' + str(index), 'state': state}
        for index, state in enumerate(('pending', 'withdrawn', 'delivering', 'admitted', 'delivery_unknown'))]
    return replace(snapshot, works=(work,))


def test_queue_snapshot_roundtrip_preserves_all_states_and_strips_availability():
    snapshot = queued_snapshot()
    document = snapshot.to_document()
    assert document['works'][0]['instruction_queue_available'] is False
    restored = ThreadSnapshot.from_document(document)
    assert restored == snapshot
    assert 'instruction_queue_available' not in restored.works[0]
    assert restored.works[0]['instruction_queue'] == snapshot.works[0]['instruction_queue']
    document['works'][0]['instruction_queue'][0]['text'] = 'Caller mutation'
    assert restored.works[0]['instruction_queue'][0]['text'] == 'Direction 0'


@pytest.mark.parametrize('mutation', [
    lambda work: work.update(instruction_queue={}),
    lambda work: work.update(instruction_queue=[work['instruction_queue'][0]] * (limits.work_message_count + 1)),
    lambda work: work.update(instruction_queue_available='yes'),
    lambda work: work['instruction_queue'][0].update(state='consumed'),
    lambda work: work['instruction_queue'][0].update(state=[]),
    lambda work: work['instruction_queue'][0].update(sequence=True),
    lambda work: work['instruction_queue'][0].update(sequence=0),
    lambda work: work['instruction_queue'][1].update(sequence=1),
    lambda work: work['instruction_queue'][1].update(id='instruction_0'),
    lambda work: work['instruction_queue'][0].update(id='bad id'),
    lambda work: work['instruction_queue'][0].update(attempt_id=''),
    lambda work: work['instruction_queue'][0].update(text=' '),
    lambda work: work['instruction_queue'][0].update(text='x' * (limits.input_text_chars + 1)),
    lambda work: work['instruction_queue'][0].update(lease_token='must_not_cross'),
])
def test_queue_snapshot_rejects_invalid_entries(mutation):
    document = queued_snapshot().to_document()
    mutation(document['works'][0])
    with pytest.raises((ThreadProtocolError, ValueError)):
        ThreadSnapshot.from_document(document)
