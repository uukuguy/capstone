import pytest
from capability_agent.runtime.process_stream import ProcessStream


def test_failed_commit_is_not_replayed_during_cleanup():
    attempts = []
    def failing(payload):
        attempts.append(payload)
        raise RuntimeError('commit failed')
    stream = ProcessStream(failing, .1)
    stream.emit({'type': 'assistant_process_delta', 'text': 'retained'}, ordinal=1, received=0)
    with pytest.raises(RuntimeError, match='commit failed'):
        stream.flush()
    stream.flush()
    assert len(attempts) == 1


def test_large_text_batches_preserve_every_character_and_fragment():
    stored = []
    stream = ProcessStream(stored.append, .1)
    for ordinal, text in enumerate(['前' * 10000, '后' * 8000]):
        stream.emit({'type': 'assistant_process_delta', 'text': text}, ordinal=ordinal, received=ordinal)
    stream.flush()
    assert ''.join(event['text'] for event in stored) == '前' * 10000 + '后' * 8000
    assert all(len(event['text']) <= 16384 for event in stored)
    assert sum(len(event['delta_records']) for event in stored) == 2
