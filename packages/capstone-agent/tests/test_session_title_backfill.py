from dataclasses import replace

from capstone_agent.session_title import SessionTitle
from capstone_agent.thread_service import InMemoryThreadService
from test_thread_postgres import _snapshot, postgres_thread_service


def add_event(service, thread_id, kind, payload, attempt_id=None):
    if hasattr(service, '_lock'):
        event = service._append_control_event(event_type=kind, payload=payload)
        service._events[-1] = replace(event, attempt_id=attempt_id)
        service._snapshot = replace(service._snapshot, last_event_seq=event.event_seq)
    else:
        from capstone_agent.thread_protocol import EventEnvelope
        from capstone_agent.thread_service import _now
        import secrets
        with service._connect() as connection:
            row = connection.execute('SELECT * FROM capstone_threads WHERE thread_id=%s FOR UPDATE', (thread_id,)).fetchone()
            event = EventEnvelope('evt_' + secrets.token_hex(8), row['last_event_seq'] + 1,
                kind, 1, thread_id, row['run_id'], None, attempt_id, None, None, _now(), 'public', payload)
            service._insert_event(connection, event)
            connection.execute('UPDATE capstone_threads SET last_event_seq=%s WHERE thread_id=%s', (event.event_seq, thread_id))


def complete(service, thread_id, identity, text, status='attempt_completed', work_id=None):
    add_event(service, thread_id, 'command_accepted', {'payload': {'text': text}, 'work_id': work_id}, identity)
    add_event(service, thread_id, status, {}, identity)


def exercise(service, thread_id):
    complete(service, thread_id, 'att_rainbow', '为什么天空会出现彩虹？')
    complete(service, thread_id, 'att_grid', '分析电网负荷变化及电压越限风险')
    complete(service, thread_id, 'att_thanks', '谢谢')
    complete(service, thread_id, 'att_failed', '这项失败输入不能命名', 'attempt_failed')
    snapshot = service.snapshot(thread_id)
    assert snapshot.session_title.source == 'automatic'
    assert snapshot.session_title.text == '分析电网负荷变化及电压越限风险'
    assert 'att_grid' in snapshot.session_title.source_ref
    assert service.snapshot(thread_id) == snapshot
    listed = service.list_threads()['threads']
    assert next(row for row in listed if row['thread_id'] == thread_id)['session_title'] == snapshot.session_title.to_document()
    assert service.snapshot(thread_id).last_event_seq == snapshot.last_event_seq


def test_memory_latest_completed_meaningful_input_and_idempotent_reads():
    service = InMemoryThreadService(_snapshot('thr_backfill'))
    exercise(service, 'thr_backfill')


def test_postgres_latest_completed_meaningful_input_and_restore(postgres_thread_service):
    service, thread_id = postgres_thread_service
    service.create_thread(_snapshot(thread_id))
    exercise(service, thread_id)
    from capstone_agent.thread_service import PostgresThreadService
    assert PostgresThreadService(service.dsn).snapshot(thread_id) == service.snapshot(thread_id)


def test_empty_historical_default_uses_creation_time_without_changing_cursor():
    service = InMemoryThreadService(_snapshot('thr_empty'))
    service._created_at = '2024-01-02T03:04:05+00:00'
    title = service.snapshot('thr_empty').session_title
    assert title.text.endswith('2024-01-02T03:04:05Z')
    assert title.source == 'default'
    assert service.snapshot('thr_empty').last_event_seq == 0


def test_manual_title_and_nested_reads_never_mutate():
    service = InMemoryThreadService(replace(_snapshot('thr_manual'), session_title=SessionTitle('我的标题', 'user', 3)))
    complete(service, 'thr_manual', 'att_grid', '分析电网负荷变化')
    assert service.snapshot('thr_manual').session_title == SessionTitle('我的标题', 'user', 3)
    other = InMemoryThreadService(_snapshot('thr_nested'))
    complete(other, 'thr_nested', 'att_grid', '分析电网负荷变化')
    with other._lock:
        assert other.snapshot('thr_nested').session_title is None
    assert other.snapshot('thr_nested').session_title.source == 'automatic'


def test_newer_completed_interaction_outweighs_old_delivery():
    service = InMemoryThreadService(_snapshot('thr_delivery_title'))
    add_event(service, 'thr_delivery_title', 'delivery_published', {'delivery': {
        'title': '旧报告', 'generation_status': 'completed', 'artifact_id': 'delivery_old', 'revision': 1}})
    complete(service, 'thr_delivery_title', 'att_new', '分析新的负荷情景', work_id='work_new')
    assert service.snapshot('thr_delivery_title').session_title.text == '分析新的负荷情景'
    add_event(service, 'thr_delivery_title', 'delivery_published', {'delivery': {
        'title': '最新交付报告', 'generation_status': 'completed', 'artifact_id': 'delivery_new', 'revision': 1}})
    assert service.snapshot('thr_delivery_title').session_title.text == '最新交付报告'


def test_inflight_attempt_defers_backfill_until_terminal():
    service = InMemoryThreadService(_snapshot('thr_busy'))
    complete(service, 'thr_busy', 'att_old', '上一项已经完成的工作')
    receipt = service.submit_command({'schema': 'capstone-command/1', 'command_id': 'cmd_busy',
        'idempotency_key': 'busy', 'thread_id': 'thr_busy', 'run_id': 'run_test_001',
        'kind': 'send_auto', 'expected_event_seq': 2, 'payload': {'text': '正在进行的新工作'}})
    assert receipt.status == 'accepted'
    assert service.snapshot('thr_busy').session_title is None
    claim = service.claim_attempt('title-test', 30)
    service.finish_attempt(claim, phase='completed', payload={'answer': '完成'})
    assert service.snapshot('thr_busy').session_title.text == '正在进行的新工作'


def test_postgres_locked_snapshot_and_historical_timestamp(postgres_thread_service):
    service, thread_id = postgres_thread_service
    service.create_thread(_snapshot(thread_id))
    with service._connect() as connection:
        connection.execute("UPDATE capstone_threads SET created_at='2020-02-03T04:05:06Z' WHERE thread_id=%s", (thread_id,))
        # The public reader can be used by artifact validation under a row lock.
        assert service.snapshot(thread_id).session_title is None
    title = service.snapshot(thread_id).session_title
    assert title.text.endswith('2020-02-03T04:05:06Z')
    assert service.snapshot(thread_id).last_event_seq == 0


def test_failed_delivery_and_active_case_do_not_replace_completed_source():
    service = InMemoryThreadService(_snapshot('thr_case_title'))
    complete(service, 'thr_case_title', 'att_good', '分析实际完成的负荷情景')
    add_event(service, 'thr_case_title', 'delivery_published', {'delivery': {
        'title': '不能当作完成的报告', 'generation_status': 'failed', 'artifact_id': 'delivery_failed', 'revision': 1}})
    service._snapshot = replace(service._snapshot, application_state={'case_execution': {'status': 'waiting_step'}})
    assert service.snapshot('thr_case_title').session_title is None
    service._snapshot = replace(service._snapshot, application_state={'case_execution': {'status': 'completed'}})
    assert service.snapshot('thr_case_title').session_title.text == '分析实际完成的负荷情景'


def test_postgres_backfills_only_returned_page_and_preserves_protocol(postgres_thread_service):
    service, thread_id = postgres_thread_service
    other = thread_id + '_older'
    service.create_thread(_snapshot(thread_id))
    other_snapshot = _snapshot(other)
    service.create_thread(replace(other_snapshot, run=replace(other_snapshot.run, run_id='run_' + other)))
    try:
        with service._connect() as connection:
            connection.execute("UPDATE capstone_threads SET created_at='2099-01-02T00:00:00Z' WHERE thread_id=%s", (thread_id,))
            connection.execute("UPDATE capstone_threads SET created_at='2099-01-01T00:00:00Z' WHERE thread_id=%s", (other,))
        complete(service, thread_id, 'att_page', '最新页面中的专业分析')
        complete(service, other, 'att_other', '下一页面中的其他分析')
        first = service.list_threads(limit=1)
        assert first['threads'][0]['thread_id'] == thread_id
        assert first['threads'][0]['session_title']['text'] == '最新页面中的专业分析'
        assert 'minimum_protocol_version' not in first['threads'][0]
        with service._connect() as connection:
            row = connection.execute('SELECT session_title FROM capstone_threads WHERE thread_id=%s', (other,)).fetchone()
            assert row['session_title'] is None
        second = service.list_threads(before=thread_id, limit=1)
        assert second['threads'][0]['session_title']['text'] == '下一页面中的其他分析'
    finally:
        with service._connect() as connection:
            connection.execute('DELETE FROM capstone_threads WHERE thread_id=%s', (other,))


def test_task_delivery_survives_same_work_and_unknown_followups():
    service = InMemoryThreadService(_snapshot('thr_followup'))
    add_event(service, 'thr_followup', 'delivery_published', {'delivery': {
        'title': '已接受任务报告', 'work_id': 'work_a', 'generation_status': 'completed',
        'artifact_id': 'delivery_task', 'revision': 1}})
    complete(service, 'thr_followup', 'att_followup', '进一步说明计算过程及方法', work_id='work_a')
    assert service.snapshot('thr_followup').session_title.text == '已接受任务报告'
    complete(service, 'thr_followup', 'att_unknown', '进一步说明其他相关问题')
    assert service.snapshot('thr_followup').session_title.text == '已接受任务报告'
    complete(service, 'thr_followup', 'att_newtask', '分析新任务中的运行风险', work_id='work_b')
    assert service.snapshot('thr_followup').session_title.text == '分析新任务中的运行风险'


def test_long_legacy_input_uses_short_fallback_without_model_calls():
    service = InMemoryThreadService(_snapshot('thr_long_title'))
    source = '分析工作中的具体要求' * 30
    complete(service, 'thr_long_title', 'att_long', source)
    assert service.snapshot('thr_long_title').session_title.text == '会话主题'


def test_local_revision_and_continuation_keep_session_topic():
    service = InMemoryThreadService(_snapshot('thr_topic_stable'))
    complete(service, 'thr_topic_stable', 'att_topic', '比较不同运输方案的成本与时间')
    original = service.snapshot('thr_topic_stable').session_title
    for i, text in enumerate(('只把上一版报告第一页的标题改成蓝色，其余不变', '继续完善上一版的排版', '谢谢，先这样', 'Please change only the font of the previous report')):
        complete(service, 'thr_topic_stable', f'att_edit_{i}', text)
        assert service.snapshot('thr_topic_stable').session_title == original
