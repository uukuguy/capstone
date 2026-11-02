import json
from hashlib import sha256

from capstone_agent.general_pi_executor import collect_artifacts


def delivery_view(tmp_path):
    task, attempt = 'task_one', 'attempt_one'
    owner = {'thread_id': 'thr_one', 'work_id': 'work_one', 'research_id': 'research_one', 'goal_revision': 1}
    products = []
    for name in ['report.html', 'metrics.csv', 'process.py', 'unselected.txt']:
        (tmp_path / name).write_text(name)
        digest, size = sha256(name.encode()).hexdigest(), len(name.encode())
        ref = 'workspace-product:' + sha256(json.dumps([name, digest, size], separators=(',', ':')).encode()).hexdigest()
        products.append({'path': name, 'sha256': digest, 'bytes': size, 'ref': ref, 'status': 'ready', 'attempt_id': attempt})
    call = 'final-assess'
    note = 'runtime.checkpoint.' + sha256(task.encode()).hexdigest()[:20] + '.' + sha256(('call:' + call).encode()).hexdigest()[:24]
    saved = {'schema': 'capstone-enterprise-cycle-checkpoint/1', 'runId': task, 'status': 'limited',
             'cycleCall': {'id': call}, 'products': products,
             'snapshot': {'owner': owner, 'attempt_id': attempt, 'phase': 'limited', 'pending_action': None,
                'objectives': [{'id': 'produce', 'product_paths': ['report.html', 'metrics.csv']}],
                'active_products': [{'path': p['path'], 'ref': p['ref']} for p in products],
                'delivery_products': [{'path': p['path'], 'ref': p['ref']} for p in products[:3]],
                'limitations': ['Numerical check failed; draft retained for human review.']}}
    return {'research_revision': 4, 'state': {'notes': [{'note_id': note, 'text': json.dumps(saved)}]}}, owner


def test_committed_limited_selection_classifies_only_current_declared_core_files(tmp_path):
    from capstone_agent.native_product_roles import delivery_presentation
    view, owner = delivery_view(tmp_path)
    (tmp_path / '.capstone-products.json').write_text(json.dumps({
        'schema': 'capstone-workspace-products/1',
        'products': [{'path': 'process.py', 'role': 'primary'}]}))
    receipt = delivery_presentation(view, task_id='task_one', attempt_id='attempt_one', owner=owner)
    files = collect_artifacts(tmp_path, 'task_one', 'attempt_one', presentation=receipt)
    by_path = {x['metadata']['path']: x['metadata'] for x in files}
    assert by_path['report.html']['presentation_role'] == 'primary'
    assert by_path['metrics.csv']['presentation_role'] == 'primary'
    assert by_path['process.py']['presentation_role'] == 'support'
    assert 'presentation_role' not in by_path['unselected.txt']
    assert by_path['report.html']['delivery_status'] == 'limited'
    assert by_path['report.html']['delivery_limitations'] == ['Numerical check failed; draft retained for human review.']
    (tmp_path / 'report.html').write_text('changed after checkpoint')
    changed = collect_artifacts(tmp_path, 'task_one', 'attempt_one', presentation=receipt)
    assert 'presentation_role' not in next(x['metadata'] for x in changed if x['metadata']['path'] == 'report.html')


def test_historical_presentation_fallback_matches_exact_owner_host_id_and_sha(tmp_path):
    from capstone_agent.artifacts import MemoryObjectStore
    from capstone_agent.native_product_roles import delivery_presentation, save_presentation, presentation_for_artifact
    view, owner = delivery_view(tmp_path)
    receipt = delivery_presentation(view, task_id='task_one', attempt_id='attempt_one', owner=owner)
    objects = MemoryObjectStore();save_presentation(objects, receipt)
    selected = receipt['products'][0]
    artifact = {'thread_id': 'thr_one', 'work_id': 'work_one', 'attempt_id': 'attempt_one', 'producer_attempt_id': 'attempt_one',
        'task_id': 'task_one', 'host_artifact_id': selected['host_artifact_id'], 'sha256': selected['sha256'],
        'size_bytes': selected['size_bytes'], 'source_status': 'completed'}
    projected = presentation_for_artifact(artifact, objects)
    assert projected['presentation_role'] == 'primary'
    assert projected['delivery_status'] == 'limited'
    assert 'presentation_role' not in artifact
    for mutation in [{'thread_id': 'thr_other'}, {'work_id': 'work_other'}, {'sha256': 'a' * 64}, {'source_status': 'failed'}]:
        assert 'presentation_role' not in presentation_for_artifact({**artifact, **mutation}, objects)


def test_declared_outputs_precede_support_and_do_not_publish_runtime_cache(tmp_path):
    (tmp_path / 'report.html').write_text('report')
    (tmp_path / 'chart.svg').write_text('chart')
    (tmp_path / 'analysis.py').write_text('reproduction')
    (tmp_path / '__pycache__').mkdir()
    (tmp_path / '__pycache__/analysis.pyc').write_bytes(b'cache')
    (tmp_path / '.capstone-products.json').write_text(json.dumps({
        'schema': 'capstone-workspace-products/1', 'products': [
            {'path': 'report.html', 'role': 'primary'},
            {'path': 'chart.svg', 'role': 'support'},
            {'path': 'analysis.py', 'role': 'reproduction'},
            {'path': '../outside.html', 'role': 'primary'},
            {'path': 'missing.pdf', 'role': 'primary'}]}))
    files = collect_artifacts(tmp_path, 'task', 'attempt')
    assert [(x['metadata']['path'], x['metadata']['presentation_role']) for x in files] == [
        ('report.html', 'primary'), ('chart.svg', 'support'), ('analysis.py', 'reproduction')]


def test_invalid_manifest_preserves_unclassified_files_without_claiming_delivery(tmp_path):
    (tmp_path / 'report.html').write_text('partial')
    (tmp_path / '.capstone-products.json').write_text('{invalid')
    files = collect_artifacts(tmp_path, 'task', 'attempt')
    assert len(files) == 1
    assert files[0]['metadata'].get('presentation_role') is None


def test_primary_outputs_survive_collection_limit(tmp_path):
    for i in range(70):
        (tmp_path / f'a{i:02}.txt').write_text('intermediate')
    (tmp_path / 'z-report.html').write_text('report')
    (tmp_path / '.capstone-products.json').write_text(json.dumps({
        'schema': 'capstone-workspace-products/1',
        'products': [{'path': 'z-report.html', 'role': 'primary'}]}))
    files = collect_artifacts(tmp_path, 'task', 'attempt')
    assert len(files) == 71
    assert files[0]['metadata']['path'] == 'z-report.html'


def test_role_crosses_projection_without_promoting_failed_output(tmp_path):
    from types import SimpleNamespace
    from capstone_agent.native_artifact_projection import project_native_artifacts
    (tmp_path / 'report.html').write_text('partial report')
    (tmp_path / '.capstone-products.json').write_text(json.dumps({
        'schema': 'capstone-workspace-products/1',
        'products': [{'path': 'report.html', 'role': 'primary'}]}))
    files = collect_artifacts(tmp_path, 'task_one', 'attempt_one')
    claim = SimpleNamespace(thread_id='thr_one', run_id='run_one', task_context=None,
        attempt=SimpleNamespace(attempt_id='attempt_one', turn_id='turn_one'))
    result = SimpleNamespace(to_document=lambda: {'artifacts': files, 'parent_attempt_id': 'attempt_one',
        'task_id': 'task_one', 'status': 'failed', 'executor_identity': {'engine': 'pi'}})
    projected = project_native_artifacts(claim, result)[0]
    assert projected['presentation_role'] == 'primary'
    assert projected['source_status'] == 'failed'
    assert projected['scope'] == 'instruction'


def test_manifest_symlink_is_not_read(tmp_path):
    (tmp_path / 'report.html').write_text('report')
    (tmp_path / '.capstone-products.json').symlink_to('/etc/passwd')
    files = collect_artifacts(tmp_path, 'task_one', 'attempt_one')
    assert len(files) == 1
    assert 'presentation_role' not in files[0]['metadata']
