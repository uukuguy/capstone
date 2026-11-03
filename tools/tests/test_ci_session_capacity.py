from tools.ci_scope import classify


def test_session_capacity_uses_only_its_direct_consumers():
    paths = ['packages/capstone-agent/src/capstone_agent/thread_worker.py',
             'packages/capstone-agent/src/capstone_agent/thread_service.py',
             'packages/capstone-agent/src/capstone_agent/resources/observation-read-budget.mjs',
             'packages/capstone-agent/tests/test_thread_worker_capacity.py', 'docs/RUNBOOK.md']
    assert classify(paths) == 'session-capacity'
    assert classify(paths, target='main') == 'release'
    assert classify(paths, release=True) == 'release'
    assert classify([*paths, 'packages/capstone-agent/src/capstone_agent/authority.py']) != 'session-capacity'
    assert classify([*paths, 'compose.yaml']) != 'session-capacity'


def test_capacity_deployment_allowance_cannot_hide_other_compose_or_image_changes():
    from tools.ci_scope import session_capacity_deployment_document as deployment_document
    compose = '  CAPSTONE_NATIVE_MAX_CONCURRENT_ATTEMPTS: ${CAPSTONE_NATIVE_MAX_CONCURRENT_ATTEMPTS:-1}\n'
    copied = '     packages/capstone-agent/src/capstone_agent/resources/observation-read-budget.mjs \\\n'
    for path, line in [('compose.yaml', compose), ('deploy/general-pi.Dockerfile', copied)]:
        assert deployment_document(path, 'original\n', 'original\n' + line)
        assert not deployment_document(path, 'original\n', 'changed\n' + line)
        assert not deployment_document(path, 'original\n', 'original\n' + line + line)
