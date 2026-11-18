from pandapower_application.domain_tools import PandapowerDomainToolService
import json
import pytest


def test_application_workspace_cannot_be_replaced_by_caller(tmp_path, monkeypatch):
    from pandapower_domain.tool_service import PandapowerToolService

    workspaces = []
    monkeypatch.setattr(PandapowerToolService, 'invoke',
        lambda self, document, *, workspace_id: workspaces.append(workspace_id) or {})
    service = PandapowerDomainToolService(workspace_root=tmp_path)
    service.invoke({'task_id': 'owned'}, workspace_id='other')
    assert workspaces == ['owned']


def test_open_model_management_selects_one_pack_workspace():
    from pandapower_application.domain_tools import domain_workspace_id
    model = {
        'model_context_id': 'ctx_ieee39', 'model_id': 'ieee39',
        'model_revision': 'revision:sha256:' + 'a' * 64,
        'implementation_family': 'pandapower', 'selection_revision': 'sel_ieee39',
        'enabled_profiles': [{'profile_id': 'pandapower-static-analysis', 'profile_version': '1.0.0'}],
    }
    management = {'schema': 'capstone-structural-context/1', 'model': model}
    first = domain_workspace_id({'task_id': 'pi-1', 'management': management})
    second = domain_workspace_id({'task_id': 'pi-2', 'management': management})
    assert first == second and first.startswith('model-')
    assert domain_workspace_id({'task_id': 'task'}) == 'task'
    with pytest.raises(ValueError, match='structural context'):
        domain_workspace_id({'task_id': 'task', 'management': {**management, 'model': {**model, 'buses': []}}})


def test_host_frozen_model_free_work_scope_survives_attempt_changes():
    from pandapower_application.domain_tools import domain_workspace_id

    scope = 'work-' + 'a' * 40
    assert domain_workspace_id({'task_id': 'pi-one', 'management': {
        'schema': 'capstone-structural-context/1', 'work_scope': scope}}) == scope
    assert domain_workspace_id({'task_id': 'pi-two', 'management': {
        'schema': 'capstone-structural-context/1', 'work_scope': scope}}) == scope
    with pytest.raises(ValueError, match='structural context'):
        domain_workspace_id({'task_id': 'pi-two', 'management': {
            'schema': 'capstone-structural-context/1', 'work_scope': '../other'}})


def test_authority_verifies_references_before_pack_publishes_them(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from pandapower_domain.authority import PandapowerArtifactAuthority

    service = PandapowerDomainToolService(workspace_root=tmp_path)
    service._capabilities = {'published': 'capability'}
    service._read_only = {'published': True}
    ref = 'result:sha256:' + 'a' * 64
    evidence_ref = 'evidence:sha256:' + 'b' * 64
    service._executors['task'] = SimpleNamespace(invoke=lambda *args, **kwargs: {'result_ref': ref})

    def admit(authority, capability, result, evidence):
        assert authority.workspace_root == tmp_path / 'task'
        assert (capability, result, evidence) == ('capability', {'result_ref': ref}, ())
        return SimpleNamespace(context=(), results=(SimpleNamespace(reference=ref),),
                               evidence=(SimpleNamespace(reference=evidence_ref),))

    monkeypatch.setattr(PandapowerArtifactAuthority, 'admit', admit)
    response = service.invoke({'task_id': 'task', 'call_id': 'call', 'name': 'published', 'arguments': {}})
    assert response['authority_references'] == {
        'authority_id': 'gridctl', 'capability_id': 'capability',
        'result_refs': [ref], 'evidence_refs': [evidence_ref]}


def test_missing_authority_content_cannot_mint_a_receipt(tmp_path):
    from types import SimpleNamespace

    service = PandapowerDomainToolService(workspace_root=tmp_path)
    service._capabilities = {'published': 'capability'}
    service._executors['task'] = SimpleNamespace(invoke=lambda *args, **kwargs: {
        'result_ref': 'result:sha256:' + 'a' * 64})
    response = service.invoke({'task_id': 'task', 'call_id': 'call', 'name': 'published', 'arguments': {}})
    assert response['ok'] is False
    assert 'authority_references' not in response


def test_readonly_tool_recovers_only_matching_verified_evidence(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from pandapower_domain.authority import PandapowerArtifactAuthority, SimulatorIntegrityError

    service = PandapowerDomainToolService(workspace_root=tmp_path)
    service._capabilities = {'published': 'capability'}
    ref = 'result:sha256:' + 'a' * 64
    linked, unrelated, missing = ('evidence:sha256:' + char * 64 for char in 'bcd')
    result = {'result_ref': ref, 'context_ref': 'ctx', 'revision_ref': 'rev'}
    service._executors['work-' + 'a' * 40] = SimpleNamespace(invoke=lambda *args, **kwargs: result)
    monkeypatch.setattr(PandapowerArtifactAuthority, 'admit', lambda *args:
        SimpleNamespace(context=(), results=(SimpleNamespace(reference=ref),), evidence=()))

    def verify(authority, reference):
        if reference == missing:
            raise SimulatorIntegrityError('missing content')
        return SimpleNamespace(reference=reference,
            document={**result, 'revision_ref': 'other' if reference == unrelated else 'rev'})

    monkeypatch.setattr(PandapowerArtifactAuthority, 'verify_evidence', verify)
    response = service.invoke({'task_id': 'task', 'call_id': 'call', 'name': 'published', 'arguments': {},
        'management': {'schema': 'capstone-structural-context/1', 'work_scope': 'work-' + 'a' * 40,
                       'prior_evidence_refs': [linked, unrelated, missing]}})
    assert response['ok'] is True
    assert response['authority_references']['evidence_refs'] == [linked]


def test_service_returns_owner_receipt_on_success_and_failure(tmp_path):
    service = PandapowerDomainToolService(workspace_root=tmp_path)
    service._capabilities = {'published': 'capability'}
    service._read_only = {'published': True}
    class Executor:
        def invoke(self, capability, arguments, *, execution_observer, execution_lease=None):
            execution_observer('execution_started')
            execution_observer('execution_ended')
            if arguments.get('fail'):
                raise RuntimeError('failed')
            return {'value': 1}
    service._executors['task'] = Executor()
    for failed in (False, True):
        result = service.invoke({'task_id': 'task', 'call_id': 'call', 'name': 'published', 'arguments': {'fail': failed}})
        assert result['ok'] is not failed
        receipt = result['execution_receipt']
        assert receipt['capacity'] == 8
        assert receipt['call_id'] == 'call'
        assert [e['phase'] for e in receipt['events']] == [
            'submitted','queued','acquired','execution_started','execution_ended','released']
    saved = list((tmp_path / 'task' / 'execution-receipts').glob('*.json'))
    assert len(saved) == 2  # Repeated task/call identity never overwrites an invocation.
    assert all(json.loads(path.read_text())['events'][-1]['phase'] == 'released' for path in saved)


def test_receipt_write_failure_is_fatal_and_releases_owner_capacity(tmp_path, monkeypatch):
    service = PandapowerDomainToolService(workspace_root=tmp_path)
    service._capabilities = {'published': 'capability'}
    def fail(*args, **kwargs): raise OSError('storage failed')
    monkeypatch.setattr('pandapower_domain.execution.os.replace', fail)
    with pytest.raises(RuntimeError, match='execution receipt persistence failed'):
        service.invoke({'task_id': 'task', 'call_id': 'call', 'name': 'published', 'arguments': {}})
    assert not service._queue._active


def test_owner_records_survive_without_a_response_consumer(tmp_path):
    service = PandapowerDomainToolService(workspace_root=tmp_path)
    service._capabilities = {'published': 'capability'}
    class Executor:
        def invoke(self, capability, arguments, *, execution_observer, execution_lease=None):
            execution_observer('execution_started')
            execution_observer('execution_ended')
            raise RuntimeError('source failed')
    service._executors['task'] = Executor()
    service.invoke({'task_id': 'task', 'call_id': 'call', 'name': 'published', 'arguments': {}})
    saved, = (tmp_path / 'task' / 'execution-receipts').glob('*.json')
    document = json.loads(saved.read_text())
    assert document['call_id'] == 'call'
    assert document['events'][-1]['phase'] == 'released'
    assert 'arguments' not in document


def test_receipt_storage_can_use_separate_persistent_root(tmp_path, monkeypatch):
    receipt_root = tmp_path / 'persistent'
    monkeypatch.setenv('CAPSTONE_DOMAIN_EXECUTION_RECEIPTS_ROOT', str(receipt_root))
    workspace = tmp_path / 'scratch'
    service = PandapowerDomainToolService(workspace_root=workspace)
    persist = service._receipt_writer('task')
    persist({'task_id': 'task', 'call_id': 'call', 'events': []})
    saved, = (receipt_root / 'task' / 'execution-receipts').glob('*.json')
    assert json.loads(saved.read_text())['call_id'] == 'call'
    assert not (workspace / 'task' / 'execution-receipts').exists()


def test_formal_and_service_execution_share_source_owner_budget(tmp_path, monkeypatch):
    from pandapower_domain.execution import GridctlExecutor
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, Lock
    from time import sleep
    service = PandapowerDomainToolService(workspace_root=tmp_path)
    service._capabilities = {'published': 'capability'}
    service._read_only = {'published': True}
    lock, filled, release = Lock(), Event(), Event()
    active, peak = 0, 0
    def run_bounded(self, request_bytes, *, output_limit, execution_observer=None):
        nonlocal active, peak
        request = json.loads(request_bytes)
        if execution_observer: execution_observer('execution_started')
        with lock:
            active += 1
            peak = max(peak, active)
            if active == 8: filled.set()
        assert release.wait(5)
        with lock: active -= 1
        if execution_observer: execution_observer('execution_ended')
        return 0, json.dumps({**request, 'ok': True, 'result': {}}).encode(), b'', False
    monkeypatch.setattr(GridctlExecutor, '_run_bounded', run_bounded)
    service._executors['task'] = GridctlExecutor(executable=tmp_path/'unused', workspace=tmp_path/'task')
    with ThreadPoolExecutor(max_workers=16) as pool:
        calls = [pool.submit(service.invoke, {'task_id': 'task', 'call_id': str(i),
            'name': 'published', 'arguments': {}}) for i in range(8)]
        calls += [pool.submit(GridctlExecutor(executable=tmp_path/'unused', workspace=tmp_path/str(i)).invoke,
            'capability', {}) for i in range(8)]
        try:
            assert filled.wait(3)
            sleep(.03)
            assert peak == 8
        finally:
            release.set()
            for call in calls: call.result()
    assert peak == 8


def test_mixed_entry_calls_use_one_owner_budget(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, Lock
    service = PandapowerDomainToolService(workspace_root=tmp_path)
    service._capabilities = {'a': 'one', 'b': 'two'}
    service._read_only = {'a': True, 'b': True}
    entered, release, lock = Event(), Event(), Lock()
    active, peak = 0, 0
    class Executor:
        def invoke(self, capability, arguments, *, execution_observer, execution_lease=None):
            nonlocal active, peak
            execution_observer('execution_started')
            with lock:
                active += 1
                peak = max(peak, active)
                if active == 8: entered.set()
            assert release.wait(5)
            with lock: active -= 1
            execution_observer('execution_ended')
            return {}
    service._executors['task'] = Executor()
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = [pool.submit(service.invoke, {'task_id': 'task', 'call_id': str(i),
            'name': 'a' if i % 2 else 'b', 'arguments': {}}) for i in range(16)]
        try:
            assert entered.wait(3)
            assert peak == 8
        finally:
            release.set()
        results = [f.result() for f in futures]
    assert all(r['ok'] for r in results)
    assert peak == 8
    assert len({r['execution_receipt']['owner_id'] for r in results}) == 1


def test_native_task_diagram_uses_verified_context_without_reopening(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from pandapower_domain.authority import PandapowerArtifactAuthority

    ref = 'context:sha256:' + 'a' * 64
    revision = 'revision:sha256:' + 'b' * 64
    service = PandapowerDomainToolService(workspace_root=tmp_path)
    monkeypatch.setattr(PandapowerArtifactAuthority, 'verify_context', lambda self, value:
        SimpleNamespace(document={'model_id': 'ieee39', 'revision_ref': revision}))
    calls = []
    def invoke(capability, arguments):
        calls.append((capability, arguments))
        return {'context_ref': ref, 'revision_ref': revision, 'coordinate_system': 'fixture',
                'buses': [], 'branches': [], 'branch_states': []}
    monkeypatch.setattr(service, '_executor', lambda owner: SimpleNamespace(invoke=invoke))
    diagram = service.project_task_diagram({'management': {'schema': 'capstone-structural-context/1',
        'work_scope': 'work-' + 'c' * 40}, 'references': [{'authority_id': 'gridctl',
        'context_refs': [ref], 'result_refs': [], 'evidence_refs': []}]})
    assert diagram['model']['revision'] == revision
    assert calls == [('operator.diagram.get', {'context_ref': ref})]


def test_native_task_view_focuses_verified_branch(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from pandapower_domain.authority import PandapowerArtifactAuthority

    ref, revision, evidence = ('context:one', 'revision:one', 'evidence:one')
    asset = 'asset:line:sha256:' + 'a' * 64
    service = PandapowerDomainToolService(workspace_root=tmp_path)
    monkeypatch.setattr(PandapowerArtifactAuthority, 'verify_context', lambda self, value:
        SimpleNamespace(document={'model_id': 'ieee39', 'revision_ref': revision}))
    monkeypatch.setattr(PandapowerArtifactAuthority, 'verify_evidence', lambda self, value:
        SimpleNamespace(document={'context_ref': ref, 'revision_ref': revision,
            'subject_ref': asset, 'evidence_type': 'network_fact',
            'capability_id': 'topology.branch.endpoints.get'}))

    def invoke(capability, arguments):
        if capability == 'operator.diagram.get':
            return {'context_ref': ref, 'revision_ref': revision, 'coordinate_system': 'fixture',
                    'buses': [], 'branches': [{'id': 'line:11'}], 'branch_states': []}
        assert capability == 'model.element.get' and arguments['identifier'] == asset
        return {'context_ref': ref, 'revision_ref': revision, 'asset_ref': asset,
                'element': {'asset_ref': asset, 'kind': 'line', 'index': 11}}

    monkeypatch.setattr(service, '_executor', lambda owner: SimpleNamespace(invoke=invoke))
    view = service.project_task_view({'management': {'schema': 'capstone-structural-context/1',
        'work_scope': 'work-' + 'c' * 40}, 'references': [{'authority_id': 'gridctl',
        'capability_id': 'topology.branch.endpoints.get', 'context_refs': [ref],
        'result_refs': [], 'evidence_refs': [evidence]}]})
    assert view['layer']['focus_ids'] == ['line:11']


def test_ranked_task_view_validates_selection_against_admitted_result(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from pandapower_domain.authority import PandapowerArtifactAuthority

    context = 'context:one'
    revision = 'revision:one'
    low, high = ('asset:line:sha256:' + char * 64 for char in 'ab')
    result = {'context_ref': context, 'revision_ref': revision, 'branch_results': [
        {'branch_ref': low, 'element_kind': 'line', 'pandapower_index': 2, 'loading_percent': 10},
        {'branch_ref': high, 'element_kind': 'line', 'pandapower_index': 11, 'loading_percent': 70},
    ]}
    service = PandapowerDomainToolService(workspace_root=tmp_path)
    monkeypatch.setattr(PandapowerArtifactAuthority, 'verify_context', lambda self, value:
        SimpleNamespace(document={'model_id': 'ieee39', 'revision_ref': revision}))
    monkeypatch.setattr(PandapowerArtifactAuthority, 'verify_result', lambda self, value:
        SimpleNamespace(document=result))
    monkeypatch.setattr(service, '_executor', lambda owner: SimpleNamespace(invoke=lambda *args: {
        'context_ref': context, 'revision_ref': revision, 'coordinate_system': 'fixture',
        'buses': [], 'branches': [{'id': 'line:2'}, {'id': 'line:11'}], 'branch_states': [],
    }))
    receipt = {'authority_id': 'gridctl', 'capability_id': 'result.branches.rank',
               'result_refs': ['result:one'], 'evidence_refs': [], 'view_refs': [high, low]}
    request = {'management': {'schema': 'capstone-structural-context/1',
               'work_scope': 'work-' + 'c' * 40}, 'references': [receipt]}
    layer = service.project_task_view(request)['layer']
    assert layer['focus_ids'] == ['line:11', 'line:2']
    assert layer['overlay']['values'] == [{'id': 'line:11', 'value': 70}, {'id': 'line:2', 'value': 10}]
    receipt['view_refs'] = ['asset:line:sha256:' + 'c' * 64]
    assert service.project_task_view(request)['layer']['focus_ids'] == []


def test_saved_rank_call_requires_matching_successful_receipt():
    from capstone_agent.thread_service import _saved_diagram_tool_calls

    task, call = 'task-one', 'call-one'
    shared = {'task_id': task, 'tool_call_id': call, 'tool_name': 'grid_result_branches_rank'}
    start = {**shared, 'native_type': 'tool_execution_start', 'activity': {
        'input_excerpt': '{"result_ref":"result:one","limit":3}',
    }}
    phases = ('submitted', 'queued', 'acquired', 'execution_started', 'execution_ended', 'released')
    receipt = {
        'schema': 'capstone-tool-execution/1', 'owner_id': 'owner', 'scope_id': 'scope',
        'task_id': task, 'call_id': call, 'policy_version': 'rolling/1', 'capacity': 8,
        'events': [{'phase': phase, 'at': '2026-11-19T00:00:00Z', 'elapsed_ms': index,
                    'provenance': 'authority_process' if phase.startswith('execution_') else 'owner_scheduler'}
                   for index, phase in enumerate(phases)],
    }
    end = {**shared, 'native_type': 'tool_execution_end', 'is_error': False,
           'activity': {'execution_receipt': receipt}}
    expected = [{'name': shared['tool_name'], 'arguments': {'result_ref': 'result:one', 'limit': 3}}]
    assert _saved_diagram_tool_calls([start, end]) == expected
    assert _saved_diagram_tool_calls([start, {**end, 'tool_call_id': 'another'}]) == []
    assert _saved_diagram_tool_calls([start, {**end, 'activity': {}}]) == []
    assert _saved_diagram_tool_calls([start, {**end, 'is_error': True}]) == []
