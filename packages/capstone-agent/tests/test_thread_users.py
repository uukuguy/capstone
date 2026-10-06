from __future__ import annotations

import pytest
from capstone_agent.thread_protocol import ThreadSnapshot
from capstone_agent.thread_service import PostgresThreadService, ThreadNotFound
from test_thread_postgres import postgres_thread_service, _snapshot, _command
from test_thread_worker import _service


def test_thread_restores_its_user_without_browser_identity():
    service = _service()
    metadata = service.thread_metadata('thr_worker')
    assert metadata['user_id'].startswith('usr_')
    assert service.thread_metadata('thr_worker')['user_id'] == metadata['user_id']
    assert service.list_threads(current_thread_id='thr_worker')['threads'][0]['thread_id'] == 'thr_worker'
    with pytest.raises(ThreadNotFound):
        service.list_threads(current_thread_id='thr_another_user')


def test_postgres_new_dialogue_inherits_user_and_list_excludes_other_users(postgres_thread_service):
    service, first = postgres_thread_service
    ids = [first, first + '_next', first + '_other']
    try:
        for ordinal, thread_id in enumerate(ids):
            document = _snapshot(thread_id).to_document()
            document['run']['run_id'] = 'run_user_' + str(ordinal) + '_' + first[-16:]
            service.create_thread(ThreadSnapshot.from_document(document), parent_thread_id=first if ordinal == 1 else None)
        user = service.thread_metadata(first)['user_id']
        assert service.thread_metadata(ids[1])['user_id'] == user
        assert service.thread_metadata(ids[2])['user_id'] != user
        restarted = PostgresThreadService(service.dsn)
        assert restarted.thread_metadata(first)['user_id'] == user
        assert {row['thread_id'] for row in service.list_threads(current_thread_id=first)['threads']} == set(ids[:2])
        assert {row['thread_id'] for row in service.list_threads(current_thread_id=ids[2])['threads']} == {ids[2]}
        with pytest.raises(ThreadNotFound):
            service.list_threads(current_thread_id=first, before=ids[2])
        assert service.set_archived(ids[1], True)['archived'] is True
        assert [row['thread_id'] for row in service.list_threads(current_thread_id=first)['threads']] == [first]
        assert [row['thread_id'] for row in service.list_threads(current_thread_id=first, archived=True)['threads']] == [ids[1]]
    finally:
        with service._connect() as connection:
            connection.execute('DELETE FROM capstone_threads WHERE thread_id = ANY(%s)', (ids,))


def test_postgres_title_survives_service_restart(postgres_thread_service):
    service, thread_id = postgres_thread_service
    service.create_thread(_snapshot(thread_id))
    service.submit_command(_command(thread_id))
    claim = service.claim_attempt('title-test', 30)
    service.finish_attempt(claim, phase='completed', payload={'answer': '已完成', 'result_refs': [], 'evidence_refs': []})
    assert service.set_thread_title(thread_id, 'IEEE-39 潮流分析', claim.attempt.attempt_id) is True
    restarted = PostgresThreadService(service.dsn)
    assert restarted.thread_metadata(thread_id)['title'] == 'IEEE-39 潮流分析'
    assert restarted.set_thread_title(thread_id, '替换标题', claim.attempt.attempt_id) is False
