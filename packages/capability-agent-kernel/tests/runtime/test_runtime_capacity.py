import json
from pathlib import Path
import subprocess
import shutil

import pytest


def test_debug_mode_raises_typed_soft_excess_without_changing_numeric_snapshots(monkeypatch):
    import capability_agent.runtime.capacity as capacity
    monkeypatch.setattr(capacity, '_initialized', capacity.DEFAULT_RUNTIME_LIMITS)
    monkeypatch.setattr(capacity, '_mode', 'normal', raising=False)
    limits = capacity.initialize_runtime_limits({'answer_summary_chars': 5}, mode='normal')
    assert capacity.observe_capacity('answer_summary_chars', 6, limits=limits, unit='characters', phase='summary') is True
    assert capacity.observe_capacity('answer_summary_chars', 5, limits=limits, unit='characters') is False
    capacity.initialize_runtime_limits({'answer_summary_chars': 5}, mode='debug')
    assert capacity.runtime_limit_mode() == 'debug'
    assert all(type(value) is int for value in capacity.runtime_limits().values())
    with pytest.raises(capacity.CapacityExceeded) as caught:
        capacity.observe_capacity('answer_summary_chars', 6, unit='characters', phase='summary')
    assert caught.value.document() == {'code': 'capacity_exceeded', 'dimension': 'answer_summary_chars',
        'actual': 6, 'limit': 5, 'unit': 'characters', 'phase': 'summary', 'retryable': False, 'mode': 'debug'}
    with pytest.raises(ValueError, match='mode'):
        capacity.initialize_runtime_limits(mode='silent')


def test_debug_reporting_does_not_silently_shorten_text(monkeypatch):
    import capability_agent.runtime.capacity as capacity
    from capability_agent.application.reporting import _bounded_text
    monkeypatch.setattr(capacity, '_initialized', capacity.DEFAULT_RUNTIME_LIMITS)
    monkeypatch.setattr(capacity, '_mode', 'normal', raising=False)
    capacity.initialize_runtime_limits({'answer_summary_chars': 5}, mode='normal')
    assert _bounded_text('abcdef') == 'abcd…'
    capacity.initialize_runtime_limits({'answer_summary_chars': 5}, mode='debug')
    with pytest.raises(capacity.CapacityExceeded):
        _bounded_text('abcdef')


def test_debug_segment_size_escapes_sanitizing_file_reader(tmp_path, monkeypatch):
    import capability_agent.runtime.capacity as capacity
    from capability_agent.application.context_segments import _read_path
    monkeypatch.setattr(capacity, '_mode', 'debug')
    path=tmp_path/'context-manifest.json'
    path.write_bytes(b'1234')
    with pytest.raises(capacity.CapacityExceeded) as caught:
        _read_path(path, max_bytes=3, mutable=False)
    assert caught.value.dimension == 'context_manifest_bytes'
    assert caught.value.actual == 4 and caught.value.limit == 3


def test_debug_workload_schemas_defer_only_capacity_maxima_to_typed_prechecks(monkeypatch):
    import capability_agent.runtime.capacity as capacity
    from capability_agent.application.research_models import research_tool_schemas, task_progress_tool_schema, precheck_research_capacity
    monkeypatch.setattr(capacity,'_mode','debug')
    limits={'research_page_records':1,'research_note_count':1,'research_progress_chars':2}
    read, update=research_tool_schemas(limits)
    assert 'maximum' not in read['properties']['limit']
    assert 'maxItems' not in update['$defs']['ResearchChanges']['properties']['notes']['anyOf'][0]
    assert update['$defs']['ResearchNote']['properties']['note_id']['maxLength']==128
    assert 'maxLength' not in task_progress_tool_schema(limits)['properties']['text']
    for value,kind,dimension in [({'limit':2},'read','research_page_records'),
        ({'kind':'goal','text':'long'},'progress','research_progress_chars'),
        ({'changes':{'notes':[{'note_id':'a','text':'a'},{'note_id':'b','text':'b'}]}},'update','research_note_count')]:
        with pytest.raises(capacity.CapacityExceeded) as caught:
            precheck_research_capacity(value,limits,kind=kind)
        assert caught.value.dimension==dimension and caught.value.mode=='debug'


def test_capacity_overrides_are_immutable_and_report_exact_boundary():
    from capability_agent.runtime.capacity import runtime_limits, check_capacity, CapacityExceeded
    source = {'research_request_bytes': 12345}
    limits = runtime_limits(source)
    source['research_request_bytes'] = 1
    assert limits['research_request_bytes'] == 12345
    check_capacity(limits, 'research_request_bytes', 12345, unit='bytes', phase='research')
    with pytest.raises(CapacityExceeded) as caught:
        check_capacity(limits, 'research_request_bytes', 12346, unit='bytes', phase='research')
    assert caught.value.document() == {'code': 'capacity_exceeded', 'dimension': 'research_request_bytes',
        'actual': 12346, 'limit': 12345, 'unit': 'bytes', 'phase': 'research', 'retryable': False}


def test_application_initialization_changes_library_defaults_without_mutating_snapshots(monkeypatch):
    import capability_agent.runtime.capacity as capacity
    monkeypatch.setattr(capacity,'_initialized',capacity.runtime_limits())
    frozen=capacity.runtime_limits()
    capacity.initialize_runtime_limits({'research_note_count':7})
    assert capacity.runtime_limits()['research_note_count']==7
    assert frozen['research_note_count']!=7


def test_python_and_javascript_neutral_defaults_match():
    from capability_agent.runtime.capacity import DEFAULT_RUNTIME_LIMITS
    module=Path(__file__).resolve().parents[4]/'packages/pi-capability-tools/src/runtime-limits.mjs'
    node=shutil.which('node')
    if node is None:
        pytest.skip('Node is required for the cross-language capacity contract')
    result=subprocess.run([node,'--input-type=module','-e',f"import {{DEFAULT_RUNTIME_LIMITS}} from {json.dumps(module.as_uri())}; console.log(JSON.stringify(DEFAULT_RUNTIME_LIMITS));"],capture_output=True,text=True,check=True)
    assert json.loads(result.stdout)==dict(DEFAULT_RUNTIME_LIMITS)


def test_small_research_page_override_sets_usable_schema_and_validator_default():
    from capability_agent.application.research_models import ResearchRead,research_tool_schemas
    limits={'research_page_records':1}
    schema,_=research_tool_schemas(limits)
    assert schema['properties']['limit']['default']==1
    assert ResearchRead.model_validate({},context={'runtime_limits':limits}).limit==1


def test_research_override_schema_and_validation_have_one_limit():
    from capability_agent.application.research_models import research_tool_schemas, ResearchUpdate
    limits = {'research_note_count': 80, 'research_text_chars': 3000}
    _, schema = research_tool_schemas(limits)
    assert schema['$defs']['ResearchChanges']['properties']['notes']['anyOf'][0]['maxItems'] == 80
    assert schema['$defs']['ResearchNote']['properties']['text']['maxLength'] == 3000
    request = {'request_id': 'capacity-test', 'expected_revision': 0, 'changes': {'goal': 'Study',
        'notes': [{'note_id': f'n-{i}', 'text': 'x' * 2500} for i in range(80)]}}
    update = ResearchUpdate.model_validate(request, context={'runtime_limits': limits})
    assert len(update.changes.notes) == 80
    request['changes']['notes'].append({'note_id': 'overflow', 'text': 'x'})
    with pytest.raises(ValueError, match='research_note_count.*81.*80'):
        ResearchUpdate.model_validate(request, context={'runtime_limits': limits})


def test_controller_channel_publish_override_and_replay_large_accepted_state(tmp_path):
    from capability_agent.application import ApplicationContextStore, ContextEventDraft, ResearchController
    from capability_agent.application.workspace import ApplicationWorkspace
    from capability_agent.runtime.research_channel import ResearchRequestChannel
    workspace = ApplicationWorkspace.create(tmp_path / 'runs', run_id='run-capacity', binding_ids=())
    store = ApplicationContextStore.initialize(workspace)
    store.append(ContextEventDraft(event_type='turn.started', turn_id='turn-capacity', payload={'ordinal': 1}))
    controller = ResearchController(store, research_id='research-capacity', turn_id='turn-capacity',
        admit_reference=lambda _: False, runtime_limits={'research_note_count': 80, 'research_text_chars': 3000})
    channel = ResearchRequestChannel(controller, attempt_id='attempt-capacity', is_active=lambda: True)
    binding = json.loads((channel.root / 'binding.json').read_text())
    assert binding['runtime_limits']['research_note_count'] == 80
    document = {'request_id': 'large', 'expected_revision': 0, 'changes': {'goal': 'Study',
        'notes': [{'note_id': f'n-{i}', 'text': 'x' * 2500} for i in range(80)]}}
    (channel.requests_path / 'large.json').write_text(json.dumps(document))
    assert channel.drain() == 1
    assert len(controller.read().notes) == 80
    assert ApplicationContextStore.replay(workspace).core.research == controller.read()
    document.update(request_id='overflow', expected_revision=1)
    document['changes']['notes'].append({'note_id': 'n-overflow', 'text': 'one'})
    (channel.requests_path / 'overflow.json').write_text(json.dumps(document))
    channel.drain()
    receipt = json.loads((channel.receipts_path / 'overflow.json').read_text())
    assert (receipt['code'], receipt['actual'], receipt['limit']) == ('capacity_exceeded', 81, 80)
    assert controller.read().revision == 1
