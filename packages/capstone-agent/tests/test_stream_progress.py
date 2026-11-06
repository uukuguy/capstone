from capstone_agent.stream_progress import TextDeltaBuffer


def test_preview_display_cadence_is_independent_from_durable_mode():
    from capstone_agent.stream_progress import thinking_delta_buffer
    now = [0.0]
    fast, durable = [], []
    display = thinking_delta_buffer(fast.append, preview=True, clock=lambda: now[0])
    buffered = thinking_delta_buffer(durable.append, preview=False, clock=lambda: now[0])
    for _ in range(1000):
        now[0] += .001
        display.push('片')
        buffered.push('片')
    display.flush()
    buffered.flush()
    assert 10 <= len(fast) <= 20
    assert max(map(len, fast)) <= 256
    assert len(durable) <= 3
    assert ''.join(fast) == ''.join(durable) == '片' * 1000
    assert display.interval == .075


def test_preview_idle_tail_flushes_on_short_display_deadline():
    from capstone_agent.stream_progress import thinking_delta_buffer
    now = [0.0]
    sent = []
    buffer = thinking_delta_buffer(sent.append, preview=True, clock=lambda: now[0])
    buffer.push('a')
    buffer.push('b')
    now[0] = .08
    buffer.flush_due()
    assert sent == ['a', 'b']


def test_first_text_is_immediate_and_later_text_is_bounded_without_loss():
    sent = []
    buffer = TextDeltaBuffer(sent.append, clock=lambda: 0, max_chars=8)
    buffer.push('甲')
    assert sent == ['甲']
    text = '乙丙丁戊己庚辛壬癸' * 5
    buffer.push(text)
    assert all(len(item) <= 8 for item in sent)
    buffer.flush()
    assert ''.join(sent) == '甲' + text
    assert all(len(item) <= 8 for item in sent)
    assert len(sent) < 10
    buffer.flush()
    assert ''.join(sent) == '甲' + text


def test_elapsed_interval_flushes_accumulated_text_and_explicit_boundary_flushes_tail():
    now = [0.0]
    sent = []
    buffer = TextDeltaBuffer(sent.append, clock=lambda: now[0], interval_seconds=.05)
    buffer.push('a')
    buffer.push('b')
    assert sent == ['a']
    now[0] = .051
    buffer.push('c')
    assert sent == ['a', 'bc']
    buffer.push('d')
    buffer.flush()
    assert sent == ['a', 'bc', 'd']


def test_default_buffer_coalesces_token_bursts_and_flushes_idle_progress():
    now = [0.0]
    sent = []
    buffer = TextDeltaBuffer(sent.append, clock=lambda: now[0])
    for _ in range(1000):
        now[0] += .0005
        buffer.push('片')
    assert len(sent) <= 2
    now[0] = 1.1
    buffer.flush_due()
    assert ''.join(sent) == '片' * 1000


def test_failed_write_keeps_pending_text_and_propagates_failure():
    import pytest
    calls = []
    def fail(text):
        calls.append(text)
        raise OSError('write failed')
    buffer = TextDeltaBuffer(fail)
    with pytest.raises(OSError, match='write failed'):
        buffer.push('retained')
    assert buffer.pending == 'retained'
    buffer.flush()
    assert calls == ['retained']
