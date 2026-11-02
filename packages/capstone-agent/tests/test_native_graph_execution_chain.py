"""Actual pinned SDK/runtime exchange with the real sealed provider and host guard."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import pytest

from capstone_agent.general_pi_storage import GeneralPiStorage
from capstone_agent.native_graph_context import NativeGraphContext
from capstone_agent.native_graph_events import NativeGraphEvents
from capstone_agent.native_research_bridge import checked_graph_progress
from test_native_graph_progress import graph_fixture


@pytest.mark.parametrize('batch,invalid,cohesive,annotations', [(False, False, False, False), (True, False, False, False), (True, True, False, False), (False, False, True, False), (False, False, False, True)])
def test_pinned_sdk_submits_structured_returns_with_native_tools_without_protocol_files_from_the_model(tmp_path, batch, invalid, cohesive, annotations):
    root = Path(__file__).resolve().parents[3]
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    result = subprocess.run(['node', str(Path(__file__).parent / 'fixtures/task-return-sdk.mjs')],
        cwd=root, input=json.dumps({'workspace': str(workspace), 'batch': batch, 'invalid': invalid, 'cohesive': cohesive, 'annotations': annotations}) + '\n',
        text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {'turns': 3, 'native_calls': (3 if batch else 2) + int(invalid), 'structured_return': True, 'checks': 'not_run'}


@pytest.mark.parametrize('scenario', ['delivered', 'cancelled', 'feedback', 'fresh-version', 'repeated', 'parent-record', 'autonomous', 'work-valid', 'limited-summary'])
def test_pinned_graph_chain_preserves_contract_associations_versions_rejections_and_delivery(tmp_path, scenario):
    cancel = scenario == 'cancelled'
    binding, task, _, _ = graph_fixture()
    if scenario in {'autonomous', 'work-valid', 'limited-summary'}:
        binding['graph_work_edition'] = 'capstone-graph-work/1'
    owner, attempt = binding['cycle_owner'], binding['attempt_id']
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    view = {'research_revision': 0, 'state': None}
    storage = GeneralPiStorage(tmp_path / 'storage')
    context = NativeGraphContext(root=tmp_path / 'contexts' / task, workspace=workspace, uid=65534,
        task_id=task, attempt_id=attempt, owner=owner, storage=storage,
        view_provider=lambda: {'binding': binding, 'view': view})
    guard = NativeGraphEvents(owner=owner, attempt_id=attempt, task_id=task)
    root = Path(__file__).resolve().parents[3]
    process = subprocess.Popen(['node', str(Path(__file__).parent / 'fixtures/graph-execution-chain.mjs')],
        cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    process.stdin.write(json.dumps({'workspace': str(workspace), 'context_root': str(context.root), 'owner': owner,
        'task_id': task, 'attempt_id': attempt, 'cancel': cancel, 'scenario': scenario}) + '\n')
    process.stdin.flush()
    commits, rejected, result, frozen_actions, frozen_snapshots = {}, [], None, set(), []
    native_frames = []
    try:
        for line in process.stdout:
            request = json.loads(line)
            operation, value = request['operation'], request['value']
            if operation == 'commit':
                command, change = value['id'], value['request']
                if command not in commits:
                    assert change['expected_revision'] == view['research_revision']
                    notes = (view['state'] or {}).get('notes', [])
                    view.update(research_revision=view['research_revision'] + 1,
                        state={**change['changes'], 'notes': [*notes, *change['changes']['notes']]})
                    commits[command] = change
                else:
                    assert commits[command] == change
                reply = {'view': view, 'ack': {'details': {'ok': True, 'result': {'status': 'committed',
                    'receipt': {'research_revision': json.loads(change['changes']['notes'][-1]['text'])['committed_revision']}}}}}
            elif operation == 'progress':
                guard.admit_progress(checked_graph_progress(value, binding=binding, task_id=task, attempt_id=attempt, view=view))
                reply = True
            elif operation == 'native':
                guard.admit(value)
                native_frames.append(value)
                if value['type'] == 'enterprise_graph_child_tool' and value['activity'] == 'end' and not value.get('is_error'):
                    body = json.dumps(value['result'], ensure_ascii=False, separators=(',', ':')).encode()
                    source = 'observation-' + sha256(value['tool_call_id'].encode()).hexdigest()[:48]
                    ref = 'native-observation:' + task + ':' + sha256(value['tool_call_id'].encode()).hexdigest()
                    storage.observation(task, source, body)
                    context.admit_observation(ref, source, sha256(body).hexdigest(), action_id=value['action_id'])
                reply = True
            elif operation == 'context':
                if value['operation'] == 'freeze':
                    frozen_actions.add(value['action_id'])
                receipt = context.handle(value)
                if receipt['ok'] and value['operation'] == 'freeze':
                    frozen_snapshots.append((value['request_id'], value['action_id'], receipt['result']['products']))
                if not receipt['ok']:
                    rejected.append(receipt)
                reply = receipt['ok']
            elif operation == 'done':
                result = value
                reply = True
            else:
                raise AssertionError(operation)
            process.stdin.write(json.dumps({'id': request['id'], 'value': reply}) + '\n')
            process.stdin.flush()
        process.wait(timeout=20)
        assert process.returncode == 0, process.stderr.read()
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)
    assert result is not None
    responses = [frame for frame in native_frames if frame['type'] == 'enterprise_graph_child_response']
    starts = {(frame['action_id'], frame['response_number']) for frame in native_frames
              if frame['type'] == 'enterprise_graph_child_response_started'}
    assert all((frame['action_id'], frame['response_number']) in starts for frame in responses)
    declared = {(frame['action_id'], call) for frame in responses for call in frame['tool_call_ids']}
    assert all((frame['action_id'], frame['tool_call_id']) in declared for frame in native_frames
               if frame['type'] == 'enterprise_graph_child_tool')
    if not cancel:
        assert responses and any(frame['tool_call_ids'] == [] for frame in responses)
    if scenario == 'repeated':
        assert result['repeated'] and result['launches'] == 1
        assert result['turns']['A'] == 6 and not frozen_actions
        assert result['delivery']['delivery']['outcome'] == 'failure'
        latest = max((json.loads(note['text']) for note in view['state']['notes']), key=lambda saved: saved['committed_revision'])
        producer = latest['dispatches'][0]
        assert producer['status'] == 'completed' and producer['proposal']['status'] == 'rejected'
        assert [item['code'] for item in producer['proposal_diagnostics']] == ['check_support_missing', 'check_support_missing']
        assert producer['proposal_diagnostics'][0]['candidate_sha256'] != producer['proposal_diagnostics'][1]['candidate_sha256']
        return
    if cancel:
        assert result['cancelled'] and result['launches'] == 1
        assert result['delivery']['delivery']['outcome'] == 'failure'
        assert result['delivery']['delivery']['delivery_product_refs'] == []
        return
    assert result['launches'] == 3
    assert result['yield_responses'] == 1
    assert result['consumer_input'] == [result['producer_ref']]
    assert not result['private_map_in_history']
    assert result['delivery']['delivery']['outcome'] == ('limited' if scenario in {'autonomous', 'limited-summary'} else 'success')
    assert len(rejected) == 1 and rejected[0]['code'] == 'source_unavailable'
    latest = max((json.loads(note['text']) for note in view['state']['notes']), key=lambda saved: saved['committed_revision'])
    report = next(item for item in latest['snapshot']['results'] if item['result_ref'] == result['report_ref'])
    assert report['consumed_results'] == [result['producer_ref']]
    if scenario == 'limited-summary':
        assert report['input_limitations'][0]['assessment_summary'] == 'LIMIT_REASON_ONLY_IN_SUMMARY'
        assert 'LIMIT_REASON_ONLY_IN_SUMMARY' in result['delivery']['delivery']['limitations']
        execution = next(item for item in latest['snapshot']['executions'] if item['step_id'] == 'A')
        assert execution['record']['limitations'] == [] and execution['assessment']['checks'] == []
    if scenario == 'parent-record':
        parents = [item for item in latest['snapshot']['executions'] if item['step_id'] == 'P']
        assert len(parents) == 1 and parents[0]['execution_revision'] == 1
        assert [item['slot'] for item in parents[0]['record']['outputs']] == ['report', 'support']
        assert result['turns']['P'] == 9
    assert all(item['contract_schema'] == 'capstone-node-contract/1' and item['proposal']['status'] ==
        ('incomplete' if scenario == 'autonomous' and item['step_id'] == 'A' else 'validated') for item in latest['dispatches'])
    producer = next(item for item in latest['dispatches'] if item['step_id'] == 'A')
    if scenario == 'feedback':
        assert [item['code'] for item in producer['proposal_diagnostics']] == ['check_support_missing']
        assert producer['proposal_diagnostics'][0]['check_label'] == 'Inspect exact saved bytes'
        assert result['turns']['A'] == 6
    else:
        assert result['turns']['A'] == (7 if scenario == 'fresh-version' else 5 if scenario == 'autonomous' else 4)
    producer_freezes = [item for item in frozen_snapshots if item[1] == producer['action_id']]
    assert len(producer_freezes) == (2 if scenario == 'fresh-version' else 1)
    if scenario == 'fresh-version':
        assert [item['code'] for item in producer['proposal_diagnostics']] == ['output_support']
        assert producer_freezes[0][0] != producer_freezes[1][0]
        old, new = producer_freezes[0][2][0], producer_freezes[1][2][0]
        assert old['ref'] != new['ref']
        assert old['sha256'] == sha256(b'value\n3\n7\n').hexdigest()
        assert new['sha256'] == sha256(b'value\n3\n7\n\n').hexdigest()
        assert producer['product_refs'] == [new['ref']]
        saved = {row['metadata']['sha256']: (storage.root / 'artifacts' / task / row['artifact_id']).read_bytes() for row in context.artifacts()}
        assert saved[old['sha256']] == b'value\n3\n7\n'
        assert saved[new['sha256']] == b'value\n3\n7\n\n'
    elif scenario == 'autonomous':
        assert [item['code'] for item in producer['proposal_diagnostics']] == ['output_slots', 'output_slots']
        assert producer['proposal']['missing_slots'] == ['optional']
        assert 'proposal_ref' not in producer['proposal']
        execution = next(item for item in latest['snapshot']['executions'] if item['step_id'] == 'A')
        assert execution['settled_status'] == 'completed' and execution['phase'] == 'limited'
        assert execution['record']['outcome'] == 'limited' and len(execution['record']['outputs']) == 1
        acceptance = next(item for item in latest['snapshot']['executions'] if item['step_id'] == 'P')['input_bindings'][0]['accepted_limitations']
        assert acceptance['assessment_ref'] == execution['assessment_ref']
        assert report['input_limitations'] == [acceptance]
        assert execution['record']['limitations'][0] in result['delivery']['delivery']['limitations']
        assert latest['snapshot']['work_envelope']['soft_task_deadline_ms'] - latest['snapshot']['work_envelope']['origin_at_ms'] == 240000
    elif scenario != 'feedback':
        assert not producer.get('proposal_diagnostics')
    assert all('.capstone-node-contract.json' not in item['path'] for item in latest['products'])
    observation_only = next(item for item in latest['dispatches'] if item['step_id'] == 'O')
    assert observation_only['action_id'] not in frozen_actions
    assert observation_only['product_refs'] == [] and observation_only['proposal']['outputs'][0]['artifact_refs'] == []
    assert len([change for change in commits.values() if json.loads(change['changes']['notes'][-1]['text'])['command_id'] == 'record-A']) == 1
