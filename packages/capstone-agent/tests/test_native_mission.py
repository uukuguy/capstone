import pytest
from jsonschema import ValidationError


def test_mission_calls_are_exact_bounded_and_receipts_are_idempotent():
    from capstone_agent.native_mission import MissionTaskChannel
    channel = MissionTaskChannel()
    call = dict(call_id='call-1',name='agent_mission_read',arguments={})
    assert channel.request(call) is None
    assert channel.request(call) is None
    assert channel.pending() == [call]
    with pytest.raises(ValueError):
        channel.request({**call, 'name':'agent_mission_ready', 'arguments':{'expected_revision':1}})
    with pytest.raises(ValidationError):
        channel.request(dict(call_id='other',name='agent_mission_read',arguments={'mission_id':'other'}))
    for action in ('verify_task', 'accept', 'delegate_next'):
        with pytest.raises(ValidationError):
            channel.request(dict(call_id='other',name='agent_mission_control',arguments={'expected_revision':1,'action':action}))
    receipt = dict(call_id='call-1',result={'mission_id':'goal_1'},is_error=False)
    channel.acknowledge([receipt]);channel.acknowledge([receipt])
    assert channel.request(call) == receipt
    assert channel.pending() == []
    with pytest.raises(ValueError):
        channel.acknowledge([{**receipt,'result':{}}])


def test_mission_binding_excludes_endpoints_and_credentials():
    from capstone_agent.native_mission import checked_binding, SCHEMA
    binding = dict(schema=SCHEMA,mission_id='goal_1',origin={'thread_id':'thread_1','work_id':'work_1'})
    assert checked_binding(binding) == binding
    with pytest.raises(ValueError):
        checked_binding({**binding, 'url':'https://caller.invalid'})


def test_equipment_narrows_current_grants_without_adding_tools():
    from capstone_agent.native_mission import equipment_tools
    selection = dict(schema='capstone-mission-tool-selection/1',allowed_tools=['read','not_registered'],denied_tools=[])
    with pytest.raises(ValueError):
        equipment_tools({'read','write'}, selection)
    selection['allowed_tools'] = ['read']
    assert equipment_tools({'read','write'}, selection) == {'read'}
    selection.update(allowed_tools=None,denied_tools=['write'])
    assert equipment_tools({'read','write'}, selection) == {'read'}
    with pytest.raises(ValueError):
        equipment_tools({'write'}, selection)


def test_gateway_selection_keeps_only_already_admitted_discovery_protocol_tools():
    from capstone_agent.native_mission import equipment_tools
    current = {'selected_gateway_read', 'unselected_gateway_write', 'agent_tool_search', 'agent_tool_load'}
    selection = dict(schema='capstone-mission-tool-selection/1',allowed_tools=['selected_gateway_read'],denied_tools=[])
    assert equipment_tools(current,selection,require_selected=False,
        protocol_tools={'agent_tool_search','agent_tool_load','unknown_helper'}) == {
            'selected_gateway_read','agent_tool_search','agent_tool_load'}
    selection['denied_tools'] = ['agent_tool_load']
    assert 'agent_tool_load' not in equipment_tools(current,selection,require_selected=False,
        protocol_tools={'agent_tool_search','agent_tool_load'})


def test_resource_protocol_helpers_require_frozen_resources_and_existing_publication():
    from capstone_agent.native_mission import resource_protocol_tools,equipment_tools
    current={'write','agent_resource_open','agent_resource_read','read','bash'}
    manifest=[{'resource_id':'resource_1'}]
    selection=dict(schema='capstone-mission-tool-selection/1',allowed_tools=['write'],denied_tools=[])
    protocol=resource_protocol_tools(current,manifest)
    assert protocol=={'agent_resource_open','agent_resource_read'}
    assert equipment_tools(current,selection,protocol_tools=protocol)=={'write','agent_resource_open','agent_resource_read'}
    assert resource_protocol_tools(current,[])==set()
    assert resource_protocol_tools({'write','agent_resource_open'},manifest)=={'agent_resource_open'}
    selection['denied_tools']=['agent_resource_open']
    assert equipment_tools(current,selection,protocol_tools=protocol)=={'write','agent_resource_read'}


@pytest.mark.parametrize('rejection',[None,'conflict','contract','transition'])
def test_worker_services_mission_requests_with_its_bound_control_callback(monkeypatch,rejection):
    import time
    from capstone_agent.pi_delegation import HttpGeneralPiExecutor, PiTaskRequest
    from capstone_agent.request_intent import NodeControl
    from capstone_agent.native_execution_renewal import ExecutionRenewal
    from capstone_agent.native_execution_authority import SCHEMA as AUTHORITY
    from capstone_agent.native_task_context import POLICY_TEXT
    from test_pi_delegation import v2_document, result_document
    monkeypatch.setattr(ExecutionRenewal, 'start', lambda _: None)
    monkeypatch.setattr(ExecutionRenewal, 'close', lambda _: None)
    document = v2_document()
    document['native_context'] = dict(selected_task_records=[],selected_task_source=None,records_truncated=False,
        policy=dict(schema='capstone-conversation-policy/1',system_policy=POLICY_TEXT,allowed_tools=['agent_mission_read'],external_lookup_enabled=False),
        mission_binding=dict(schema='capstone-native-mission/1',mission_id='goal_1',origin={'thread_id':'thread1'}))
    request = PiTaskRequest.from_document(document)
    executor = HttpGeneralPiExecutor('http://127.0.0.1:1',identity=request.executor_identity,
        capability={'available':True,'execution_authority_schemas':[AUTHORITY],'mission_schemas':['capstone-native-mission/1']})
    acknowledged = []
    operations = []
    def call(method, path, **kwargs):
        if path == '/owned-tasks':
            return {'task_id':request.task_id}
        if path.endswith('/mission'):
            assert kwargs['document']['parent_attempt_id'] == request.parent_attempt_id
            if kwargs['document']['receipts']:
                acknowledged.extend(kwargs['document']['receipts'])
                return {'requests':[]}
            return {'requests':[dict(call_id='call-1',name='agent_mission_read',arguments={})]}
        if method == 'GET':
            return dict(status='completed' if acknowledged else 'running',events=[],result=result_document(request) if acknowledged else None)
        raise AssertionError(path)
    monkeypatch.setattr(executor, '_call', call)
    def operation(name, args, identity):
        operations.append((name,args,identity))
        if rejection:
            from capstone_control.contracts import ContractError
            from capstone_control.service import Conflict,InvalidTransition
            raise {'conflict':Conflict,'contract':ContractError,'transition':InvalidTransition}[rejection]('PRIVATE_REJECTION_DETAIL')
        return {'mission_id':'goal_1','state':'planning'}
    executor.execute(request,NodeControl(lambda:None,time.monotonic()+2,mission_operation=operation),lambda _:None)
    assert len(operations) == 1
    assert operations[0][:2] == ('agent_mission_read',{})
    if rejection:
        assert len(acknowledged)==1 and acknowledged[0]['is_error'] is True
        expected={'conflict':'mission_operation_conflict','contract':'mission_contract_invalid','transition':'mission_transition_invalid'}
        assert acknowledged[0]['result']['error']==expected[rejection]
        assert 'PRIVATE_REJECTION_DETAIL' not in str(acknowledged)
        if rejection=='conflict':
            assert 'expected_revision' in acknowledged[0]['result']['message']
            assert 'revision' in acknowledged[0]['result']['message'] and 'plan_revision' in acknowledged[0]['result']['message']
            assert 'saved' in acknowledged[0]['result']['message'] and 'references' in acknowledged[0]['result']['message']
    else:
        assert acknowledged == [dict(call_id='call-1',result={'mission_id':'goal_1','state':'planning'},is_error=False)]


def test_mission_tool_schemas_distinguish_current_object_revision_from_plan_revision():
    from capstone_agent.native_mission import CATALOG
    for schema in CATALOG.values():
        expected=schema['inputSchema']['properties'].get('expected_revision')
        if expected:
            assert 'Mission.revision' in expected['description']
            assert 'plan_revision' in expected['description']
    assert 'Mission.plan_revision' in CATALOG['agent_mission_conclude']['inputSchema']['properties']['plan_revision']['description']


@pytest.mark.parametrize('kind',['resource','skill'])
def test_task_model_schema_excludes_unimplemented_equipment_kinds(kind):
    from capstone_agent.native_mission import CATALOG
    from jsonschema import Draft202012Validator
    task=dict(task_id='task_2',objective='Use the authorized predecessor result',delivery_requirements=['Save a report'],
        depends_on=['task_1'],agent_id='capstone',mode='single',max_attempts=1,
        equipment=[dict(schema='capstone-mission-equipment-reference/1',kind=kind,id='source_input',revision='1')])
    for name,args in [('agent_mission_prepare_task',{'expected_revision':2,'task':task}),
                      ('agent_mission_update_plan',{'expected_revision':2,'acceptance_criteria':['Inspect report'],'tasks':[task]})]:
        with pytest.raises(ValidationError):
            Draft202012Validator(CATALOG[name]['inputSchema']).validate(args)


def test_mission_conclusion_schema_requires_typed_per_criterion_current_result_references():
    from capstone_agent.native_mission import CATALOG
    from jsonschema import Draft202012Validator
    validator=Draft202012Validator(CATALOG['agent_mission_conclude']['inputSchema'])
    base=dict(expected_revision=4,plan_revision=2,summary='Inspect results')
    with pytest.raises(ValidationError):
        validator.validate(base)
    verdict=dict(criterion_index=0,status='met',explanation='Verified saved result',evidence=[])
    with pytest.raises(ValidationError):
        validator.validate({**base,'criteria_verdicts':[verdict]})
    validator.validate({**base,'criteria_verdicts':[{**verdict,'evidence':[dict(kind='product',task_id='task_1',artifact_id='file_1',sha256='a'*64)]}]})
    validator.validate({**base,'criteria_verdicts':[{**verdict,'status':'unknown'}]})
    with pytest.raises(ValidationError):
        validator.validate({**base,'criteria_verdicts':[{**verdict,'evidence':[dict(kind='product',task_id='task_1',artifact_id='file_1',sha256='invented')]}]})


def test_host_mission_channel_requires_the_current_task_attempt_and_authority():
    from types import SimpleNamespace
    from threading import RLock, Event
    from capstone_agent.general_pi_server import GeneralPiHost
    from capstone_agent.native_mission import MissionTaskChannel
    from capstone_agent.native_execution_authority import ExecutionAuthority, SCHEMA
    host = object.__new__(GeneralPiHost)
    host._lock = RLock()
    grant = dict(schema=SCHEMA,generation='a'*64,capability='b'*64)
    record = dict(request=SimpleNamespace(parent_attempt_id='attempt_1',native_context={'policy':{'allowed_tools':['agent_mission_read']}}),status='running',cancel=Event(),
        execution_authority=ExecutionAuthority('a'*64,'b'*64,30),mission=MissionTaskChannel())
    host._tasks = {'task_1':record}
    call = dict(call_id='call_1|message_1',name='agent_mission_read',arguments={})
    assert host.mission_request('task_1',call) is None
    with pytest.raises(PermissionError):
        host.mission_request('task_1',dict(call_id='denied',name='agent_mission_control',arguments={'expected_revision':1,'action':'cancel'}))
    exchange = dict(parent_attempt_id='attempt_1',execution_authority=grant,receipts=[])
    assert host.mission_exchange('task_1',exchange) == {'requests':[call]}
    for changed in [{**exchange,'parent_attempt_id':'old'},{**exchange,'execution_authority':{**grant,'capability':'c'*64}}]:
        with pytest.raises(PermissionError):
            host.mission_exchange('task_1',changed)
    receipt = dict(call_id=call['call_id'],result={'state':'planning'},is_error=False)
    assert host.mission_exchange('task_1',{**exchange,'receipts':[receipt]}) == {'requests':[]}
    assert host.mission_request('task_1',call) == receipt
    record['cancel'].set()
    with pytest.raises(PermissionError):
        host.mission_request('task_1',call)


@pytest.mark.parametrize('setup_delay', [0, 4, 35])
def test_http_mission_poll_releases_real_relay_capacity_between_pending_and_receipt(tmp_path, monkeypatch, setup_delay):
    import time
    from types import SimpleNamespace
    from threading import Event, Thread
    import httpx
    from capstone_agent.general_pi_server import GeneralPiHost, make_server
    from capstone_agent.general_pi_relay import ProviderRelay
    from capstone_agent.native_execution_authority import ExecutionAuthority
    from capstone_agent.native_mission import MissionTaskChannel
    import capstone_agent.general_pi_relay as relay_module
    clock = [100.0]
    monkeypatch.setattr(relay_module, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    relay = ProviderRelay(gateway_per_task=1)
    host = GeneralPiHost(root=tmp_path,identity={},run_task=lambda *_:None)
    server = make_server(host,control_token='control-fixture',address=('127.0.0.1',0),runner=SimpleNamespace(relay=relay,gateway=None))
    thread = Thread(target=server.serve_forever,daemon=True)
    thread.start()
    clock[0] += setup_delay
    # Host setup is outside the grant lifetime; only authorized requests consume it.
    host._tasks['task_1'] = dict(request=SimpleNamespace(parent_attempt_id='attempt_1',
        native_context={'policy':{'allowed_tools':['agent_mission_read']}}),status='running',cancel=Event(),
        execution_authority=ExecutionAuthority('a'*64,'b'*64,30,clock=lambda: clock[0]),mission=MissionTaskChannel())
    relay.register('task_1','task-grant',clock[0]+3)
    call = dict(call_id='call_1',name='agent_mission_read',arguments={})
    url = 'http://127.0.0.1:'+str(server.server_address[1])+'/mission-tools/task_1'
    try:
        with httpx.Client(timeout=1) as client:
            response = client.post(url,headers={'Authorization':'Bearer task-grant'},json=call)
            assert response.status_code == 200 and response.json() == {'pending':True}
            # A pending response is not a long-lived gateway invocation.
            deadline = time.monotonic()+.5
            while relay.active and time.monotonic()<deadline:
                time.sleep(.01)
            assert not relay.active, 'Mission poll leaked the per-task relay lease'
            receipt = dict(call_id='call_1',result={'state':'planning'},is_error=False)
            host._tasks['task_1']['mission'].acknowledge([receipt])
            response = client.post(url,headers={'Authorization':'Bearer task-grant'},json=call)
            assert response.status_code == 200 and response.json() == receipt
            rejected = client.post(url,headers={'Authorization':'Bearer task-grant'},json={**call,'arguments':{'mission_id':'other'}})
            assert rejected.status_code == 409
            deadline = time.monotonic()+.5
            while relay.active and time.monotonic()<deadline:
                time.sleep(.01)
            assert not relay.active, 'Completed and rejected Mission polls must release relay capacity'
            unauthorized = client.post(url,headers={'Authorization':'Bearer wrong-fixture-grant'},json=call)
            assert unauthorized.status_code == 401 and not relay.active
            clock[0] += 4
            expired = client.post(url,headers={'Authorization':'Bearer task-grant'},json=call)
            assert expired.status_code == 401 and not relay.active
            relay.register('task_1','task-grant',clock[0]+60)
            clock[0] += 31
            expired_authority = client.post(url,headers={'Authorization':'Bearer task-grant'},json=call)
            assert expired_authority.status_code == 409 and not relay.active
    finally:
        relay.revoke('task_1')
        server.shutdown();server.server_close();thread.join(timeout=1)
