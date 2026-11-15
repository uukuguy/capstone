from tools.ci_scope import classify


def test_worker_interruption_scope_stays_with_direct_consumers():
    paths=['packages/capstone-agent/src/capstone_agent/thread_service.py',
           'packages/capstone-agent/src/capstone_agent/thread_materials.py',
           'packages/capstone-agent/tests/test_worker_interruption_products.py']
    assert classify(paths)=='worker-interruption'
    assert classify(paths,target='main')=='release'
    assert classify(paths,release=True)=='release'
    assert classify(paths[:-1])!='worker-interruption'
    assert classify(paths+['packages/grid-simulator/src/grid_simulator/engine.py'])!='worker-interruption'
