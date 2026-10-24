"""Application overrides apply after consumer modules have been imported."""
from copy import deepcopy

import pytest

from capstone_agent.application_capacity import CapacityExceeded, current_capacity, initialize_capacity
from capstone_agent.network_diagram import normalize_network_diagram
from capstone_agent.result_projection import ResultProjection
from capstone_agent.thread_input import context_selection
from test_result_projection import valid_projection
from test_network_diagram import projection
from test_thread_postgres import postgres_thread_service


@pytest.fixture(autouse=True)
def restore_capacity():
    previous = current_capacity()
    yield
    initialize_capacity(previous)


def test_result_rows_follow_large_then_small_application_profile():
    document = valid_projection()
    row = document['tables'][0]['rows'][0]
    document['tables'][0]['rows'] = [dict(deepcopy(row), row_id=f'row_{i}') for i in range(129)]
    initialize_capacity({'ui_result_row_count': 130})
    assert len(ResultProjection.from_document(document).tables[0].rows) == 129
    initialize_capacity({'ui_result_row_count': 128})
    with pytest.raises(CapacityExceeded) as error:
        ResultProjection.from_document(document)
    assert error.value.dimension == 'ui_result_row_count'


def test_diagram_component_override_is_enforced_after_import():
    initialize_capacity({'ui_network_buses': 1})
    with pytest.raises(CapacityExceeded) as error:
        normalize_network_diagram(projection()['diagram'])
    assert error.value.dimension == 'ui_network_buses'


def test_context_reference_selection_does_not_keep_legacy_24_item_limit():
    refs = [f'context_{i}' for i in range(25)]
    initialize_capacity({'context_references': 25})
    assert context_selection({'include_refs': refs, 'exclude_refs': []})['include_refs'] == refs
    initialize_capacity({'context_references': 24})
    with pytest.raises(CapacityExceeded) as error:
        context_selection({'include_refs': refs, 'exclude_refs': []})
    assert error.value.dimension == 'context_references'


def test_command_override_applies_to_work_parser_after_import():
    from capstone_agent.thread_work import parse_command
    command = {'schema': 'capstone-command/2', 'command_id': 'cmd_capacity',
               'idempotency_key': 'key_capacity', 'thread_id': 'thr_capacity',
               'kind': 'work_message', 'target': {'kind': 'work', 'id': 'new', 'expected_revision': 0},
               'payload': {'text': 'x' * 70000}}
    initialize_capacity({'command_bytes': 100000})
    assert parse_command(command)['payload']['text'] == command['payload']['text']
    initialize_capacity({'command_bytes': 1000})
    with pytest.raises(CapacityExceeded) as error:
        parse_command(command)
    assert error.value.dimension == 'command_bytes'


def test_work_count_override_rejects_without_changing_the_original_snapshot():
    from capstone_agent.thread_work import apply_work
    from test_thread_http_api import _service
    snapshot = _service().snapshot('thr_demo_39')
    command = {'run_id': None, 'kind': 'work_message', 'payload': {'text': 'Read materials'},
               'target': {'kind': 'work', 'id': 'new', 'expected_revision': 0}}
    initialize_capacity({'work_count': 1})
    saved, reason, _ = apply_work(snapshot, command)
    assert reason is None and len(saved.works) == 1
    rejected, reason, _ = apply_work(saved, command)
    assert reason == 'work_limit_reached' and rejected == saved
    initialize_capacity({'work_count': 2})
    saved, reason, _ = apply_work(saved, command)
    assert reason is None and len(saved.works) == 2


def test_previous_instruction_excerpt_reports_truncation_and_preserves_saved_text():
    from capstone_agent.thread_service import _previous_instruction_from_events
    from test_thread_result_projection import _service, _claim_and_projection, _complete, RESULT_ONE, EVIDENCE_ONE
    service = _service()
    claim, projection = _claim_and_projection(service, 1, RESULT_ONE, EVIDENCE_ONE)
    _complete(service, claim, projection, RESULT_ONE, EVIDENCE_ONE)
    original = service._attempts[claim.attempt.attempt_id]['instruction']
    initialize_capacity({'previous_instruction_chars': 3})
    previous = _previous_instruction_from_events(service._events, service._attempts, claim.model_context)
    assert previous.instruction == original[:3] and previous.instruction_truncated
    assert previous.answer == 'rea' and previous.answer_truncated
    assert service._attempts[claim.attempt.attempt_id]['instruction'] == original


def test_postgres_capacity_window_survives_reopen_and_keeps_full_history(postgres_thread_service):
    from dataclasses import replace
    from capstone_agent.thread_service import PostgresThreadService, _previous_instruction_from_postgres
    from test_thread_result_projection import _service
    service, thread_id = postgres_thread_service
    initialize_capacity({'ui_result_projection_count': 1})
    service.create_thread(replace(_service().snapshot('thr_projection'), thread_id=thread_id))
    for ordinal in (1, 2):
        snapshot = service.snapshot(thread_id)
        command = {'schema': 'capstone-command/1', 'thread_id': thread_id,
            'command_id': f'cmd_capacity_{ordinal}', 'idempotency_key': f'key_capacity_{ordinal}',
            'run_id': snapshot.run.run_id, 'kind': 'send_ordinary',
            'expected_event_seq': snapshot.last_event_seq, 'payload': {'text': f'capacity {ordinal}'}}
        assert service.submit_command(command).status == 'accepted'
        claim = service.claim_attempt('capacity_worker', lease_seconds=30)
        assert claim is not None
        item = valid_projection()
        item.update(result_id=f'projection_{ordinal}', thread_id=thread_id, run_id=claim.run_id,
                    attempt_id=claim.attempt.attempt_id, turn_id=claim.attempt.turn_id,
                    model_context_id=claim.model_context.id, model_revision=claim.model_context.model_revision,
                    result_ref='result:sha256:' + f'{ordinal:064x}',
                    tables=[], element_refs=[], overlay=None)
        service.finish_attempt(claim, phase='completed', payload={'answer': 'answer complete',
            'result_projections': [item], 'result_refs': [item['result_ref']], 'evidence_refs': item['evidence_refs']})
    service = PostgresThreadService(service.dsn)
    snapshot = service.snapshot(thread_id)
    assert [item.result_id for item in snapshot.result_projections] == ['projection_2']
    assert snapshot.application_state['result_projection_history']['omitted_count'] == 1
    history = service.read_history(thread_id)
    assert any(item['event_type'] == 'attempt_completed' and
               item['payload']['result_projections'][0]['result_id'] == 'projection_1'
               for item in history['events'])
    initialize_capacity({'ui_result_projection_count': 1, 'previous_instruction_chars': 3})
    with service._connect() as connection:
        previous = _previous_instruction_from_postgres(connection, thread_id, snapshot.active_model_context)
    assert previous.instruction == 'cap' and previous.instruction_truncated
    assert previous.answer == 'ans' and previous.answer_truncated


def test_harness_answer_budget_is_bytes_and_dynamic():
    from capstone_agent.harness import AdmittedAttemptAnswer
    initialize_capacity({'answer_bytes': 70000})
    assert AdmittedAttemptAnswer('x' * 65000, 'offline_information', 'general_knowledge').answer
    initialize_capacity({'answer_bytes': 5})
    with pytest.raises(CapacityExceeded) as error:
        AdmittedAttemptAnswer('中文', 'offline_information', 'general_knowledge')
    assert error.value.dimension == 'answer_bytes' and error.value.actual == 6


def test_worker_frame_uses_current_control_document_budget():
    from capstone_agent.protocol import Frame
    frame = Frame('session-capacity', 1, 'turn', {'instruction': 'x' * 2000})
    initialize_capacity({'control_document_bytes': 4096})
    raw = frame.to_line()
    initialize_capacity({'control_document_bytes': 1024})
    for operation in (frame.to_line, lambda: Frame.from_line(raw)):
        with pytest.raises(CapacityExceeded) as error:
            operation()
        assert error.value.dimension == 'control_document_bytes'


def test_thread_http_client_preserves_capacity_details():
    from capstone_agent.thread_http import _decode, ThreadHttpError
    initialize_capacity({'control_document_bytes': 3})
    with pytest.raises(ThreadHttpError) as error:
        _decode(200, True, b'{"x":1}')
    assert error.value.status_code == 413
    assert error.value.body['detail']['code'] == 'capacity_exceeded'
    assert error.value.body['detail']['dimension'] == 'control_document_bytes'


def test_worker_input_reader_uses_profile_selected_after_import():
    import io
    from capstone_agent.worker import serve_application
    from capstone_agent.protocol import ProtocolError
    sizes = []
    class Source(io.BytesIO):
        def readline(self, size=-1):
            sizes.append(size)
            return super().readline(size)
    initialize_capacity({'control_document_bytes': 1024})
    with pytest.raises(ProtocolError):
        serve_application(lambda *args: pytest.fail('invalid frame cannot start an application'),
                          input_stream=Source(b'broken\n'), output_stream=io.BytesIO())
    assert sizes == [1025]


def test_session_reader_reports_capacity_and_wakes_waiters():
    import io
    from types import SimpleNamespace
    from capstone_agent.session import WorkerSession, WorkerSpec
    session = WorkerSession(WorkerSpec('capacity-app', ('unused',)), mode='scripted-demo')
    initialize_capacity({'control_document_bytes': 1024})
    session._process = SimpleNamespace(stdout=io.BytesIO(b'x' * 1025))
    session._read_events()
    assert session._failure_code == 'capacity_exceeded'
    assert 'capacity' in session._failure


@pytest.mark.parametrize('path,field,requested', [
    ('/api/v1/threads', 'history_page_items', 128),
    ('/api/v1/threads/thr_demo_39/history', 'history_page_items', 512),
    ('/api/v1/threads/thr_demo_39/products', 'history_page_items', 512),
    ('/api/v1/threads/thr_demo_39/deliveries', 'product_page_items', 128),
    ('/api/v1/threads/thr_demo_39/product-index', 'product_page_items', 128),
    ('/api/v1/threads/thr_demo_39/attempts/ATTEMPT/records', 'history_page_items', 512),
])
def test_http_page_limits_follow_live_profile_instead_of_static_query_caps(path, field, requested):
    from fastapi.testclient import TestClient
    from test_thread_http_api import _app, _auth, _service
    service = _service()
    if 'ATTEMPT' in path:
        from capstone_agent.thread_commands import ThreadCommandFactory
        command = ThreadCommandFactory('thr_demo_39').send_auto('Read materials', expected_event_seq=0,
            command_id='cmd_http_capacity', idempotency_key='key_http_capacity')
        assert service.submit_command(command).status == 'accepted'
        path = path.replace('ATTEMPT', service.snapshot('thr_demo_39').current_attempt.attempt_id)
    with TestClient(_app(service), base_url='http://localhost') as client:
        initialize_capacity({field: 512})
        response = client.get(path, params={'limit': requested}, headers=_auth())
        assert response.status_code == 200, response.text
        initialize_capacity({field: 64})
        response = client.get(path, params={'limit': requested}, headers=_auth())
        assert response.status_code == 413, response.text
        detail = response.json()['detail']
        assert detail['code'] == 'capacity_exceeded'
        assert detail['dimension'] == field and detail['actual'] == requested and detail['limit'] == 64
