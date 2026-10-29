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
