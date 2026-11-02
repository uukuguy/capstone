import asyncio
import pytest
from test_data_gateway_mcp import gateway
from test_data_gateway_relay import access,request

CONTEXT={'task_id':'study-1','run_id':'revision-2','trace_id':'trace-2','parent_span_id':'step-3'}

def test_admitted_work_is_stable_across_revision_runs():
    from capstone_agent.gateway_diagnostics import research_diagnostics
    binding={'cycle_owner':{'work_id':'work-study'}}
    first=research_diagnostics(binding,'attempt-1')
    second=research_diagnostics(binding,'attempt-2')
    assert first['task_id']==second['task_id']=='work-study'
    assert first['run_id']!=second['run_id']
    assert first['trace_id']!=second['trace_id']
    assert research_diagnostics(binding,'attempt-1')==first
    assert research_diagnostics(None,'attempt-1') is None

def test_client_injects_meta_without_changing_business_arguments(tmp_path):
    client,session=gateway(tmp_path)
    original=session.call_tool
    captured=[]
    async def call(name,arguments,*,meta):
        captured.append(meta)
        return await original(name,arguments)
    session.call_tool=call
    catalog=asyncio.run(client.prepare())
    result=asyncio.run(client.call('data_gateway_discover_data_capabilities',{},catalog,diagnostics=CONTEXT))
    assert captured==[{'gateway/diagnostics':CONTEXT}]
    assert session.calls[0][1]=={}
    assert result['structuredContent']['provenance']['request_id']=='source-1'

def test_relay_host_context_spans_business_errors_and_transport_failure():
    relay=access();relay.revoke('task-1')
    relay.bind('task-1','attempt-1',set(relay.catalog['tools']),diagnostics=CONTEXT)
    captured=[]
    async def call(name,arguments,catalog,*,diagnostics):
        captured.append(diagnostics)
        return {'isError':True,'structuredContent':{'status':'error','provenance':{'request_id':'gateway-1','span_id':'gateway-span'}}}
    relay.client.call=call
    result=asyncio.run(relay.call('task-1',request()))
    assert captured==[CONTEXT]
    assert result['is_error'] is True
    first=relay.diagnostic_calls('task-1')[0]
    assert first['status']=='business_error' and first['request_id']=='gateway-1'
    assert first['gateway_span_id']=='gateway-span' and 'retry_of' not in first
    async def failed(*args,**kwargs):raise OSError('never persist this message')
    relay.client.call=failed
    with pytest.raises(OSError):asyncio.run(relay.call('task-1',{**request(),'call_id':'page-2'}))
    last=relay.diagnostic_calls('task-1')[-1]
    assert last['status']=='transport_error' and 'request_id' not in last
    assert last['span_id']!=first['span_id'] and 'retry_of' not in last
    assert 'never persist' not in str(last)

@pytest.mark.parametrize('change',[{'task_id':'bad text'},{'run_id':'x'*129},{'secret':'hidden'},{'trace_id':None}])
def test_invalid_context_is_rejected_before_binding(change):
    relay=access();relay.revoke('task-1')
    with pytest.raises(ValueError):relay.bind('task-1','attempt-1',set(relay.catalog['tools']),diagnostics={**CONTEXT,**change})

def test_parallel_pages_revisions_and_explicit_host_retry_remain_distinct():
    relay=access();relay.revoke('task-1')
    relay.bind('task-1','attempt-1',set(relay.catalog['tools']),diagnostics=CONTEXT)
    async def call(*args,diagnostics):
        await asyncio.sleep(0)
        return {'structuredContent':{'status':'partial','provenance':{'request_id':diagnostics['parent_span_id']}}}
    relay.client.call=call
    async def parallel():
        await asyncio.gather(*(relay.call('task-1',{**request(),'call_id':f'page-{i}'},diagnostics={**CONTEXT,'parent_span_id':f'step-{i}'}) for i in range(2)))
    asyncio.run(parallel())
    before=relay.diagnostic_calls('task-1')
    assert len({row['span_id'] for row in before})==2
    assert {row['request_id'] for row in before}=={'step-0','step-1'}
    asyncio.run(relay.call('task-1',{**request(),'call_id':'retry-1'},retry_of=before[0]['span_id']))
    assert relay.diagnostic_calls('task-1')[-1]['retry_of']==before[0]['span_id']
    with pytest.raises(ValueError):
        asyncio.run(relay.call('task-1',{**request(),'call_id':'forged-run'},diagnostics={**CONTEXT,'run_id':'other-run'}))
    relay.revoke('task-1')
    relay.bind('task-2','attempt-2',set(relay.catalog['tools']),diagnostics={**CONTEXT,'run_id':'revision-3'})
    asyncio.run(relay.call('task-2',request()))
    assert relay.diagnostic_calls('task-2')[0]['task_id']==CONTEXT['task_id']
    assert relay.diagnostic_calls('task-2')[0]['run_id']=='revision-3'
