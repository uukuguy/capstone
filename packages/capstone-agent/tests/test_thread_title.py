from dataclasses import replace

import pytest

from capstone_agent.session_title import SessionTitle
from capstone_agent.thread_protocol import ThreadSnapshot
from capstone_agent.thread_service import InMemoryThreadService
from test_thread_postgres import _snapshot, postgres_thread_service


def rename(thread_id, revision=0, key='title_1', text='电网运行研究'):
    return {'schema': 'capstone-command/2', 'command_id': key,
            'idempotency_key': key, 'thread_id': thread_id, 'kind': 'rename_session',
            'target': {'kind': 'session_title', 'id': thread_id, 'expected_revision': revision},
            'payload': {'text': text}}


def exercise(service, snapshot):
    command = rename(snapshot.thread_id)
    receipt = service.submit_command(command)
    assert receipt.status == 'accepted'
    assert service.submit_command(command) == receipt
    saved = service.snapshot(snapshot.thread_id)
    assert saved.session_title == SessionTitle('电网运行研究', 'user', 1)
    assert saved.current_attempt == snapshot.current_attempt
    assert saved.works == snapshot.works
    assert ThreadSnapshot.from_document(saved.to_document()).session_title == saved.session_title
    assert service.list_threads()['threads'][0]['session_title'] == saved.session_title.to_document()
    stale = service.submit_command(rename(snapshot.thread_id, key='title_2'))
    assert stale.rejection == 'title_revision_conflict'
    assert service.snapshot(snapshot.thread_id).session_title == saved.session_title


def test_memory_rename_persists_without_creating_work():
    snapshot = _snapshot('thr_title_test')
    exercise(InMemoryThreadService(snapshot), snapshot)


def test_postgres_rename_persists(postgres_thread_service):
    service, thread_id = postgres_thread_service
    snapshot = _snapshot(thread_id)
    service.create_thread(snapshot)
    exercise(service, snapshot)


@pytest.mark.parametrize('model_free', [False, True])
def test_snapshot_title_roundtrip(model_free):
    snapshot = replace(_snapshot('thr_title'), session_title=SessionTitle('研究'))
    if model_free:
        snapshot = replace(snapshot, active_model_context=None, active_grid_page_id=None, minimum_protocol_version=2)
    assert ThreadSnapshot.from_document(snapshot.to_document()).session_title == snapshot.session_title


def test_rename_rejects_wrong_target_and_invalid_text():
    snapshot = _snapshot('thr_title')
    service = InMemoryThreadService(snapshot)
    wrong = rename(snapshot.thread_id)
    wrong['target']['id'] = 'thr_other'
    assert service.submit_command(wrong).rejection == 'title_target_mismatch'
    assert service.submit_command(rename(snapshot.thread_id, key='blank', text=' ')).rejection == 'invalid_session_title'


def test_model_free_rename_and_archived_session():
    snapshot = replace(_snapshot('thr_title_free'), active_model_context=None,
                       active_grid_page_id=None, minimum_protocol_version=2)
    service = InMemoryThreadService(snapshot)
    exercise(service, snapshot)
    service.set_archived(snapshot.thread_id, True)
    assert service.submit_command(rename(snapshot.thread_id, revision=1, key='archived')).rejection == 'thread_archived'


def test_postgres_initial_title_and_new_service_restore(postgres_thread_service):
    service, thread_id = postgres_thread_service
    from capstone_agent.thread_service import PostgresThreadService
    snapshot = replace(_snapshot(thread_id), active_model_context=None,
                       active_grid_page_id=None, minimum_protocol_version=2,
                       session_title=SessionTitle('企业研究与分析'))
    service.create_thread(snapshot)
    restored = PostgresThreadService(service.dsn).snapshot(thread_id).session_title
    assert restored.source == 'default'
    assert restored.text.startswith('企业研究与分析 · ')
    assert restored.revision == 0
    exercise(service, snapshot)
    assert PostgresThreadService(service.dsn).snapshot(thread_id).session_title.source == 'user'
