from capstone_agent.stream_progress import TextDeltaBuffer


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
