from copy import deepcopy
from hashlib import sha256

import pytest

from capstone_agent.native_model_request_pool import MODEL_REQUEST_POOL_POLICY, checked_model_request_pool
from capstone_agent.native_llm_pool import LLM_CALL_POOL_POLICY
from capstone_agent.general_pi_executor import _NativeUsage


def setup():
    return ({'deep_research': False, 'policy': {'allowed_tools': []}},
            {'model_request_pool': deepcopy(MODEL_REQUEST_POOL_POLICY)}, {})


def event(status='queued', number=1, **fields):
    return {'type': 'model_request_pool', 'schema': MODEL_REQUEST_POOL_POLICY['schema'],
        'request_id': f'request-{number}', 'chain_id': 'main', 'kind': 'main',
        'depends_on': [], 'status': status, 'queued_at_ms': 100, **fields}


def test_main_requires_no_semantic_tool_grant_and_terminal_replay_is_exact():
    args = setup()
    for row in [event(), event('running', started_at_ms=110),
                event('completed', started_at_ms=110, finished_at_ms=120)]:
        assert checked_model_request_pool(row, *args) == row
    assert checked_model_request_pool(row, *args) == row
    with pytest.raises(ValueError):
        checked_model_request_pool({**row, 'finished_at_ms': 121}, *args)


@pytest.mark.parametrize('fields', [{'answer': 'private'}, {'usage': []}, {'queued_at_ms': True},
    {'status': 'queued', 'started_at_ms': 110}, {'status': 'running'},
    {'depends_on': ['request-2']}, {'request_id': 'request-0'}, {'kind': 'analysis'},
    {'chain_id': 'other'}, {'finished_at_ms': 120}])
def test_invalid_frames_do_not_mutate_state(fields):
    native, capability, record = setup()
    with pytest.raises(ValueError):
        checked_model_request_pool(event(**fields), native, capability, record)
    assert not record.get('model_request_pool_bindings')


def test_dr_and_unpublished_policy_rejected():
    for research in [True, None, 0]:
        native, capability, record = setup()
        native['deep_research'] = research
        with pytest.raises(ValueError):checked_model_request_pool(event(), native, capability, record)
    native, capability, record = setup()
    capability['model_request_pool']['concurrency'] = True
    with pytest.raises(ValueError):checked_model_request_pool(event(), native, capability, record)


def test_analysis_requires_semantic_grant_and_observed_submit():
    native, capability, record = setup()
    row = event(kind='analysis', chain_id='analysis:'+sha256(b'child').hexdigest(), child_id='child', parent_tool_call_id='submit')
    with pytest.raises(ValueError):checked_model_request_pool(row, native, capability, record)
    native.update(llm_call_pool=deepcopy(LLM_CALL_POOL_POLICY))
    native['policy']['allowed_tools'] = ['agent_llm_submit']
    capability['llm_call_pool'] = deepcopy(LLM_CALL_POOL_POLICY)
    with pytest.raises(ValueError):checked_model_request_pool(row, native, capability, record)
    record['llm_pool_submit_calls'] = {'submit'}
    assert checked_model_request_pool(row, native, capability, record) == row


def test_dependencies_and_chain_are_bound_until_settled():
    args = setup()
    checked_model_request_pool(event(), *args)
    checked_model_request_pool(event('running', started_at_ms=110), *args)
    row = event(number=2, depends_on=['request-1'])
    checked_model_request_pool(row, *args)
    with pytest.raises(ValueError):checked_model_request_pool({**row, 'status':'running','started_at_ms':111}, *args)
    checked_model_request_pool(event('failed', started_at_ms=110, finished_at_ms=120), *args)
    checked_model_request_pool({**row, 'status':'running','started_at_ms':121}, *args)
    with pytest.raises(ValueError):checked_model_request_pool(event(number=3), *args)


def test_cancelling_reserves_concurrency_and_rejected_updates_are_atomic():
    native, capability, record = setup()
    native.update(llm_call_pool=deepcopy(LLM_CALL_POOL_POLICY))
    native['policy']['allowed_tools'] = ['agent_llm_submit']
    capability['llm_call_pool'] = deepcopy(LLM_CALL_POOL_POLICY)
    record['llm_pool_submit_calls'] = {'submit'}
    rows = [event(number=i, kind='analysis', chain_id='analysis:'+sha256(f'c{i}'.encode()).hexdigest(), child_id=f'c{i}', parent_tool_call_id='submit') for i in range(1,4)]
    for row in rows:checked_model_request_pool(row, native, capability, record)
    for row in rows[:2]:checked_model_request_pool({**row,'status':'running','started_at_ms':110}, native, capability, record)
    checked_model_request_pool({**rows[0],'status':'cancelling','started_at_ms':110,'cancel_reason':'timeout'}, native, capability, record)
    before = deepcopy(record)
    with pytest.raises(ValueError):checked_model_request_pool({**rows[2],'status':'running','started_at_ms':111}, native, capability, record)
    assert record == before
    checked_model_request_pool({**rows[0],'status':'cancelled','started_at_ms':110,'finished_at_ms':120,'cancel_reason':'timeout'}, native, capability, record)
    checked_model_request_pool({**rows[2],'status':'running','started_at_ms':121}, native, capability, record)


def test_dispatch_metadata_does_not_count_as_additional_model_usage():
    usage = _NativeUsage()
    before = usage.summary()
    usage.observe(event('completed', started_at_ms=110, finished_at_ms=120))
    assert usage.summary() == before


def test_request_budget_and_no_execution_timing_on_queued_cancellation():
    args = setup()
    for index in range(1, MODEL_REQUEST_POOL_POLICY['max_requests']+1):
        row = event(number=index, depends_on=[] if index==1 else [f'request-{index-1}'])
        checked_model_request_pool(row, *args)
        checked_model_request_pool({**row,'status':'cancelled','finished_at_ms':101,'cancel_reason':'cancelled'}, *args)
    with pytest.raises(ValueError):checked_model_request_pool(event(number=257,depends_on=['request-256']), *args)


def test_turn_number_and_title_bind_request_but_allow_same_turn_retry():
    args = setup()
    first = event(model_turn_number=2,title='Main analysis')
    checked_model_request_pool(first,*args)
    checked_model_request_pool({**first,'status':'cancelled','finished_at_ms':110},*args)
    second = event(number=2,depends_on=['request-1'],model_turn_number=2,title='Retry')
    checked_model_request_pool(second,*args)
    for extra in [{'model_turn_number':3},{'title':'Changed'}]:
        with pytest.raises(ValueError):checked_model_request_pool({**second,**extra},*args)
    with pytest.raises(ValueError):checked_model_request_pool(event(number=3,depends_on=['request-2'],model_turn_number=1),*args)


@pytest.mark.parametrize('fields',[{'model_turn_number':0},{'model_turn_number':True},{'title':'x'*121}])
def test_invalid_optional_turn_metadata(fields):
    with pytest.raises(ValueError):checked_model_request_pool(event(**fields),*setup())


def test_actual_host_publishes_main_dispatch_without_semantic_tool_grants(tmp_path):
    import time
    from capstone_agent.business_context import BusinessContext
    from capstone_agent.general_pi_server import GeneralPiHost
    from capstone_agent.pi_delegation import PiTaskRequest
    from capstone_agent.native_task_context import GENERAL_CHAT_POLICY_TEXT
    native = {'policy': {'schema': 'capstone-conversation-policy/1',
        'system_policy': GENERAL_CHAT_POLICY_TEXT, 'allowed_tools': [],
        'external_lookup_enabled': False}, 'selected_task_records': [], 'selected_task_source': None,
        'records_truncated': False, 'deep_research': False}
    def run(request, cancelled, emit):
        for row in [event(), event('running', started_at_ms=110),
                    event('completed', started_at_ms=110, finished_at_ms=120)]:emit(row)
        return 'Answer', {}
    run.experimental_llm_pool = True
    host = GeneralPiHost(root=tmp_path, identity={'engine':'pi'}, run_task=run)
    assert host.capability['model_request_pool'] == MODEL_REQUEST_POOL_POLICY
    request = PiTaskRequest('dispatch', 'attempt-a', 'direct', 'Explain', (), (), host.identity, 2,
        business_context=BusinessContext.empty('workspace', 0),
        resource_profile={'profile_id':'direct_pi','revision':'test'},
        input={'kind':'text','text':'Explain'}, native_context=native)
    host.submit(request)
    deadline = time.monotonic()+2
    while host.read(request.task_id)['status']=='running' and time.monotonic()<deadline:time.sleep(.005)
    result = host.read(request.task_id)
    assert result['status']=='completed'
    assert [row['model_request_pool']['status'] for row in result['events'] if 'model_request_pool' in row] == ['queued','running','completed']


def test_process_forwards_dispatch_metadata_without_accounting_it(tmp_path):
    import json
    import sys
    from capstone_agent.general_pi_executor import GeneralPiProcess
    rows = [event(), event('running',started_at_ms=110), event('completed',started_at_ms=110,finished_at_ms=120)]
    frames = rows + [{'type':'agent_end','messages':[{'role':'assistant','stopReason':'stop','content':[{'type':'text','text':'Answer'}]}]}]
    script = tmp_path/'dispatch.py'
    script.write_text('import sys\nsys.stdin.readline()\n'+'\n'.join('print('+repr(json.dumps(row))+',flush=True)' for row in frames))
    process = GeneralPiProcess((sys.executable,str(script)), {'PATH':'/usr/bin'},tmp_path)
    received=[]
    assert process.run('task',timeout=5,cancelled=lambda:False,on_event=received.append)=='Answer'
    assert [row for row in received if row['type']=='model_request_pool']==rows
