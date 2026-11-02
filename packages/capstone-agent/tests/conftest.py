"""Keep offline workbench admission independent of developer credentials."""
import pytest


@pytest.fixture(autouse=True)
def offline_workbench_profiles(monkeypatch):
    # These tests use fake executors or explicitly mocked provider transports.
    # This value only makes the default profile selectable; it is not a key.
    # Tests of missing credentials pass environment={} or remove it explicitly.
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'offline-workbench-test-not-a-provider-key')
    monkeypatch.setenv('CAPSTONE_WORKBENCH_PRESET', 'local')
    monkeypatch.delenv('CAPSTONE_WORKBENCH_LLM_PROFILES', raising=False)


@pytest.fixture
def native_single_child_cleanup(monkeypatch):
    """RPC-only fixtures have no descendants; isolated UID cleanup stays real."""
    import sys
    if sys.platform != 'darwin':
        return
    from capstone_agent.general_pi_executor import GeneralPiProcess
    def stop_fixture(process):
        assert process.uid is None
        child, process.process = process.process, None
        if child is not None:
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=1)
            for stream in (child.stdin, child.stdout, child.stderr):
                if stream is not None:
                    stream.close()
    monkeypatch.setattr(GeneralPiProcess, 'stop', stop_fixture)
