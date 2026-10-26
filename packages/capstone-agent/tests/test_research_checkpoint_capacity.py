import threading

import pytest

from capstone_agent.application_capacity import initialize_capacity
from capstone_agent.general_pi_server import make_server
from capstone_agent.pi_delegation import HttpGeneralPiExecutor
from capability_agent.application import ContextStoreError
from test_native_research_bridge import research
from test_enterprise_normal_chat import native_executor


def test_research_exchange_uses_research_budgets_not_native_task_capacity():
    initialize_capacity({'native_task_bytes': 1024, 'native_context_bytes': 512,
                         'research_request_bytes': 8192, 'research_response_bytes': 16384})

    class Host:
        _run = None  # This control-only host has no registered gateway runner.
        def research_control(self, task, document):
            assert task == 'task-capacity'
            assert len(document['document']['text']) == 3000
            return {'status': 'accepted', 'view': 'x' * 4000}

    server = make_server(Host(), control_token='offline-private', address=('127.0.0.1', 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        registered = native_executor()
        executor = HttpGeneralPiExecutor('http://127.0.0.1:' + str(server.server_port),
                                         identity=registered.identity, capability=registered.capability,
                                         control_token='offline-private')
        result = executor._call('POST', '/tasks/task-capacity/research',
            document={'operation': 'acknowledge', 'document': {'text': 'x' * 3000}},
            timeout=2, total_timeout=3, research_transport=True)
        assert len(result['view']) == 4000
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        initialize_capacity()


def test_actual_reducer_appends_large_unicode_note_delta_and_preserves_immutable_history(tmp_path):
    initialize_capacity()
    owner = research(tmp_path)
    try:
        controller = owner.controller
        controller.update({'request_id': 'first', 'expected_revision': 0,
                           'changes': {'goal': 'Keep research history', 'notes': [
                               {'note_id': 'runtime.checkpoint.first', 'text': '研究😀' * 6000}]}})
        controller.update({'request_id': 'second', 'expected_revision': 1,
                           'changes': {'notes': [{'note_id': 'runtime.checkpoint.second', 'text': 'Next actual finding'}]}})
        state = controller.read()
        assert len(state.notes) == 2
        assert state.notes[0].text == '研究😀' * 6000
        with pytest.raises(ContextStoreError, match='note identity'):
            controller.update({'request_id': 'overwrite', 'expected_revision': 2,
                               'changes': {'notes': [{'note_id': 'runtime.checkpoint.first', 'text': 'Invalid replacement'}]}})
    finally:
        owner.close(failed=False)
