import json
import os

import pytest

from capstone_agent.native_diagnosis import NativeDiagnosis, DIAGNOSIS_POLICY


def request(call, operation='begin', **record):
    return {'type': 'systematic_diagnosis_request', 'schema': 'capstone-systematic-diagnosis/1',
            'request_id': call, 'operation': operation, 'record': record}


def probe(issue='timeout'):
    return dict(issue=issue, input_version='source-v1', evidence_refs=['observation:failed-call'],
                hypothesis='The service had a transient timeout.',
                minimal_probe='Repeat the same permitted read once.',
                retry_reason='transient_failure', comparison='The previous read completed.',
                rejected_hypotheses=[], acceptance='advisory')


def host(tmp_path, now=lambda: 100):
    return NativeDiagnosis(root=tmp_path / 'shared', state_root=tmp_path / 'private',
                           uid=os.geteuid() + 1, policy=DIAGNOSIS_POLICY, clock=now)


def test_budget_survives_renaming_and_fresh_host(tmp_path):
    instance = host(tmp_path)
    first = instance.handle(request('call-0', **probe()))
    assert first['result']['status'] == 'probe_reserved'
    assert first['result']['record']['outcome'] == 'unknown'
    assert instance.handle(request('call-0', **probe())) == first
    for index in range(1, DIAGNOSIS_POLICY['max_probes']):
        result = host(tmp_path).handle(request(f'call-{index}', **probe(f'renamed-{index}')))
        assert result['result']['status'] == 'probe_reserved'
    result = host(tmp_path).handle(request('exhausted', **probe('new-name')))
    assert result['result']['status'] == 'exhausted'
    assert result['result']['next_disposition'] == 'retain_gap'
    assert result['result']['retained_records'] == DIAGNOSIS_POLICY['max_probes']
    changed = probe('renamed-input')
    changed['input_version'] = 'model-selected-new-label'
    assert host(tmp_path).handle(request('still-exhausted', **changed))['result']['status'] == 'exhausted'
    assert host(tmp_path).handle(request('read', 'read'))['result']['records'][0]['issue'] == 'timeout'


def test_actual_outcome_and_rejected_hypotheses_survive_resume(tmp_path):
    instance = host(tmp_path)
    instance.handle(request('one', **probe()))
    result = instance.handle(request('finish', 'finish', probe_id='one', outcome='failed',
        outcome_refs=['observation:second-call'], information_gained='The corrected call also timed out.',
        rejected_hypotheses=['The first call had malformed arguments.'], next_disposition='retain_gap'))
    assert result['result']['record']['outcome'] == 'failed'
    records = host(tmp_path).handle(request('read', 'read'))['result']['records']
    assert records[0]['rejected_hypotheses'] == ['The first call had malformed arguments.']
    assert records[0]['reported_only'] is True
    assert instance.handle(request('changed', 'finish', probe_id='one', outcome='passed',
        outcome_refs=[], information_gained='changed', rejected_hypotheses=[], next_disposition='continue'))['ok'] is False


def test_finite_time_and_missing_hypothesis_are_advisory_gaps(tmp_path):
    instance = host(tmp_path)
    instance.handle(request('first', **probe()))
    result = host(tmp_path, now=lambda: 100 + DIAGNOSIS_POLICY['max_seconds']).handle(request('late', **probe()))
    assert result['result']['status'] == 'exhausted'
    record = probe()
    record['hypothesis'] = ''
    result = instance.handle(request('gap', **record))
    assert result['ok'] is True
    assert result['result']['next_disposition'] == 'retain_gap'


def test_unrelated_failures_do_not_share_elapsed_time_or_budget(tmp_path):
    def failure(call, path, duration_ms=1):
        return request(call, 'observe_rejection', tool_call_id=call, code='missing_file', duration_ms=duration_ms,
            selection={'tool_name': 'read', 'input': {'path': path}, 'action_identity': None})
    first = host(tmp_path).handle(failure('first', 'a.csv'))['result']
    later = host(tmp_path, now=lambda: 500).handle(failure('second', 'b.csv'))['result']
    assert later['status'] == 'investigating'
    assert first['scope_ref'] != later['scope_ref']
    assert later['remaining_probes'] == DIAGNOSIS_POLICY['max_probes'] - 1
    third = host(tmp_path, now=lambda: 600).handle(failure('third', 'a.csv'))['result']
    assert third['remaining_probes'] == DIAGNOSIS_POLICY['max_probes'] - 2
    assert third['elapsed_seconds'] < 1


def test_identity_change_rejected_and_state_outside_model_directory(tmp_path):
    instance = host(tmp_path)
    instance.handle(request('same', **probe()))
    with pytest.raises(ValueError, match='identity'):
        instance.handle(request('same', **probe('changed')))
    assert not (tmp_path / 'shared' / 'state.json').exists()
    state = json.loads((tmp_path / 'private' / 'state.json').read_text())
    assert state['policy'] == DIAGNOSIS_POLICY


def test_native_context_requires_host_registered_policy_for_diagnostic_tools():
    from capstone_agent.native_task_context import checked_native_context, POLICY_TEXT
    context = {'policy': {'schema': 'capstone-conversation-policy/1', 'system_policy': POLICY_TEXT,
        'allowed_tools': ['agent_diagnosis_record'], 'external_lookup_enabled': False},
        'selected_task_records': [], 'selected_task_source': None, 'records_truncated': False,
        'systematic_diagnosis': DIAGNOSIS_POLICY}
    assert checked_native_context(context) == context
    del context['systematic_diagnosis']
    with pytest.raises(ValueError, match='diagnosis'):
        checked_native_context(context)


def test_host_binds_diagnostic_port_and_publishes_exact_policy(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost
    class Runner:
        def bind_diagnosis_provider(self, provider):
            self.provider = provider
        def __call__(self, *args):
            return 'done', {}
    runner = Runner()
    host_instance = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=runner)
    assert host_instance.capability['systematic_diagnosis'] == DIAGNOSIS_POLICY
    assert callable(runner.provider)


def test_observed_protocol_rejections_share_budget_with_declared_probes(tmp_path):
    instance = host(tmp_path)
    for index in range(DIAGNOSIS_POLICY['max_probes']):
        result = instance.handle(request(f'error-{index}', 'observe_rejection', tool_call_id=f'call-{index}',
            selection={'tool_name': 'agent_research_record', 'input': {'ref': 'same'}, 'action_identity': None},
            duration_ms=1, code='graph_context_rejected'))
    assert result['result']['status'] == 'exhausted'
    state = host(tmp_path).handle(request('recovery', 'read'))['result']
    assert len(state['rejections']) == DIAGNOSIS_POLICY['max_probes']
    assert instance.handle(request('another', **probe('renamed'), scope_ref=result['result']['scope_ref']))['result']['status'] == 'exhausted'


def test_real_node_client_uses_python_host_receipt(tmp_path):
    from pathlib import Path
    import subprocess
    instance = host(tmp_path)
    module = Path(__file__).parents[1] / 'src/capstone_agent/resources/systematic-diagnosis.mjs'
    script = '''
      const {createDiagnosisTools}=await import(process.argv[1]);
      const config={diagnosisContextPath:process.argv[2],applicationPolicy:{allowed_tools:['agent_diagnosis_record']}};
      const [tool]=createDiagnosisTools(config);
      const result=await tool.execute('real-call',{operation:'read'});
      process.stdout.write(JSON.stringify({done:result.details.diagnosis})+'\\n');
    '''
    process = subprocess.Popen(['node', '--input-type=module', '-e', script, module.as_uri(), str(instance.root)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        frame = json.loads(process.stdout.readline())
        assert frame['operation'] == 'read'
        instance.handle(frame)
        stdout, stderr = process.communicate(timeout=5)
        assert process.returncode == 0, stderr
        assert json.loads(stdout)['done']['remaining_probes'] == DIAGNOSIS_POLICY['max_probes']
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def test_required_diagnostic_persistence_failure_is_fatal(tmp_path, monkeypatch):
    import capstone_agent.native_diagnosis as module
    instance = host(tmp_path)
    def unavailable(*args, **kwargs):
        raise OSError('storage unavailable')
    monkeypatch.setattr(module, 'write_json', unavailable)
    with pytest.raises(OSError):
        instance.handle(request('cannot-retain', **probe()))
    assert not (instance.root / 'responses' / 'cannot-retain.json').exists()


def _run_sdk(instance, workspace, mode, numeric=None):
    from pathlib import Path
    import subprocess
    workspace.mkdir(exist_ok=True)
    script = Path(__file__).parent / 'fixtures/systematic-diagnosis-sdk.mjs'
    process = subprocess.Popen(['node', str(script), str(workspace), str(instance.root), mode,
                                *([] if numeric is None else [json.dumps(numeric)])],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        result = None
        while line := process.stdout.readline():
            frame = json.loads(line)
            if 'done' in frame:
                result = frame['done']
                break
            instance.handle(frame)
        _, stderr = process.communicate(timeout=5)
        assert process.returncode == 0, stderr
        assert result is not None, stderr
        return result
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


@pytest.mark.parametrize('mode', ['limited', 'independent', 'ignore'])
def test_pinned_sdk_scoped_exhaustion_with_real_host(tmp_path, mode):
    result = _run_sdk(host(tmp_path), tmp_path / 'workspace', mode)
    assert result['retained'] == 'Retained facts'
    assert result['failedExecutions'] == DIAGNOSIS_POLICY['max_probes']
    if mode == 'ignore':
        assert result['failure'] == 'continuation_no_progress'
        assert result['requests'] == DIAGNOSIS_POLICY['max_probes'] + 2
    else:
        assert 'failure' not in result
        assert 'explicit gap' in json.dumps(result['final'])
        assert result['independentExecutions'] == (1 if mode == 'independent' else 0)


def test_fresh_sdk_restores_current_exhaustion_instead_of_old_read_snapshot(tmp_path):
    _run_sdk(host(tmp_path), tmp_path / 'workspace', 'limited')
    result = _run_sdk(host(tmp_path), tmp_path / 'workspace', 'recovery')
    assert result['failedExecutions'] == 0
    assert result['requests'] == 2
    assert 'failure' not in result
    assert 'explicit gap' in json.dumps(result['final'])


@pytest.mark.parametrize('numeric', [1e-7, 1e20, -0.0])
def test_numeric_sdk_selections_match_host_and_remain_exhausted_after_restore(tmp_path, numeric):
    first = _run_sdk(host(tmp_path), tmp_path / 'workspace', 'limited', numeric)
    assert first['failedExecutions'] == DIAGNOSIS_POLICY['max_probes']
    assert 'failure' not in first
    second = _run_sdk(host(tmp_path), tmp_path / 'workspace', 'recovery', numeric)
    assert second['failedExecutions'] == 0
    assert second['requests'] == 2
    assert 'failure' not in second


def test_typed_wire_hash_matches_binary64_numbers_and_utf8_key_order():
    from pathlib import Path
    import subprocess
    from capstone_agent.native_diagnosis import _digest
    module = Path(__file__).parents[1] / 'src/capstone_agent/resources/systematic-diagnosis.mjs'
    value = {'numbers': [1e-7, 1e20, -0.0, 5e-324, 1.7976931348623157e308, 9007199254740993],
             '\U00010000': ['中文', True, None], '\ue000': {'a': 1, 'b': '1'}}
    result = subprocess.run(['node', '--input-type=module', '-e',
        'const {diagnosisDigest}=await import(process.argv[1]);process.stdout.write(diagnosisDigest(JSON.parse(process.argv[2])));',
        module.as_uri(), json.dumps(value)], capture_output=True, text=True, check=True)
    assert result.stdout == _digest(value)
    assert _digest([1]) != _digest({'0': 1})
    assert _digest(1) != _digest('1')


def test_unknown_diagnostic_receipt_stops_sdk_even_if_result_hook_error_is_swallowed(tmp_path, monkeypatch):
    import capstone_agent.native_diagnosis as module
    original = module.write_json
    def broken_receipt(path, document, **kwargs):
        if path.parent.name == 'responses' and document.get('result', {}).get('status') == 'investigating':
            document = {**document, 'request_sha256': '0' * 64}
        return original(path, document, **kwargs)
    monkeypatch.setattr(module, 'write_json', broken_receipt)
    result = _run_sdk(host(tmp_path), tmp_path / 'workspace', 'limited')
    assert result['failedExecutions'] == 1
    assert result['requests'] == 1
    assert result['retained'] == 'Retained facts'
    assert 'identity changed' in result['failure']
