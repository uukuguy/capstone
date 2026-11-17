import time
import pytest
from capstone_agent.pi_delegation import HttpGeneralPiExecutor, PiTaskRequest
from capstone_agent.request_intent import NodeControl
from test_pi_delegation import request_document, result_document


@pytest.mark.parametrize('terminal_race', [False, True])
def test_transport_reserves_then_waits_for_actual_consumption(monkeypatch, terminal_race):
    from capstone_agent.native_execution_authority import SCHEMA
    from capstone_agent.native_execution_renewal import ExecutionRenewal
    monkeypatch.setattr(ExecutionRenewal, 'start', lambda self: None)
    monkeypatch.setattr(ExecutionRenewal, 'close', lambda self: None)
    request = PiTaskRequest.from_document(request_document())
    executor = HttpGeneralPiExecutor('http://127.0.0.1:1', identity=request.executor_identity,
        capability={'available': True, 'execution_authority_schemas':[SCHEMA],
                    'instruction_schemas':['capstone-native-instruction/1']})
    history = []
    item = dict(id='supplement', text='Change direction')
    def reserve(identity):
        history.append('reserved')
        return item
    def call(method, path, **kwargs):
        if path == '/owned-tasks':
            return {'task_id': request.task_id}
        if path.endswith('/instructions'):
            assert history == ['reserved']
            history.append('sent')
            assert kwargs['document']['text'] == item['text']
            if terminal_race:
                from capstone_agent.pi_delegation import PiHTTPFailure
                raise PiHTTPFailure(409, 'instruction_owner_rejected')
            return {'instruction_id':'supplement', 'state':'queued'}
        if method == 'GET':
            assert history == ['reserved', 'sent']
            return {'status':'completed','events':[] if terminal_race else [{'event_id':'receipt-1',
                'type':'general_pi_instruction_consumed','instruction_id':'supplement'}],
                'result':result_document(request)}
        raise AssertionError(path)
    monkeypatch.setattr(executor, '_call', call)
    control = NodeControl(lambda: None, time.monotonic()+5,
        instructions=lambda: (item,), reserve_instruction=reserve,
        acknowledge_instruction=lambda identity: history.append('consumed'))
    executor.execute(request, control, lambda event: None)
    assert history == (['reserved', 'sent'] if terminal_race else ['reserved', 'sent', 'consumed'])
