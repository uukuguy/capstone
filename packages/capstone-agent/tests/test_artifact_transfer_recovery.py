"""Publication retries transport failures without executing research again."""
import time
from types import SimpleNamespace

import pytest

from capstone_agent.delegated_runtime import DelegatedRuntime
from capstone_agent.pi_delegation import PiArtifactTransportUnavailable
from capstone_agent.request_intent import NodeControl


def setup_publication(monkeypatch, retain):
    from capstone_agent import native_artifact_projection as projection
    artifact = {'artifact_id': 'report'}
    monkeypatch.setattr(projection, 'project_native_artifacts', lambda *a, **kw: [artifact])
    monkeypatch.setattr(projection, 'retain_native_artifact', retain)
    runtime = DelegatedRuntime.__new__(DelegatedRuntime)
    runtime._claim = object()
    runtime._artifact_store = object()
    runtime._executor = object()
    runtime.runtime_mode = 'capstone'
    runtime._emit = lambda callback, payload: callback(payload)
    return runtime, artifact


def test_publication_recovers_same_file_after_connection_loss(monkeypatch):
    attempts, events = [], []
    def retain(store, executor, artifact):
        attempts.append(artifact)
        if len(attempts) < 3:
            raise PiArtifactTransportUnavailable('interrupted')
    runtime, artifact = setup_publication(monkeypatch, retain)
    runtime._publish_artifacts(SimpleNamespace(task_id='task'),
        SimpleNamespace(parent_attempt_id='attempt'), events.append,
        NodeControl(lambda: None, time.monotonic() + 2))
    assert attempts == [artifact] * 3
    assert [e.get('child_status') for e in events] == [
        'transport_interrupted', 'transport_restored', None]
    assert events[-1]['event_type'] == 'native_artifact_published'


@pytest.mark.parametrize('error', [OSError('identity changed'), InterruptedError('cancelled')])
def test_permanent_failure_or_user_cancel_never_publishes(monkeypatch, error):
    calls, events = [], []
    def retain(*args):
        calls.append(1)
        raise error
    runtime, _ = setup_publication(monkeypatch, retain)
    with pytest.raises(type(error)):
        runtime._publish_artifacts(SimpleNamespace(task_id='task'),
            SimpleNamespace(parent_attempt_id='attempt'), events.append,
            NodeControl(lambda: None, time.monotonic() + 2))
    assert calls == [1]
    assert events == []


def test_user_can_cancel_during_transfer_recovery(monkeypatch):
    events = []
    def retain(*args):
        raise PiArtifactTransportUnavailable('interrupted')
    runtime, _ = setup_publication(monkeypatch, retain)
    def cancel():
        if events:
            raise InterruptedError('cancelled')
    with pytest.raises(InterruptedError):
        runtime._publish_artifacts(SimpleNamespace(task_id='task'),
            SimpleNamespace(parent_attempt_id='attempt'), events.append,
            NodeControl(cancel, time.monotonic() + 2))
    assert len(events) == 1
    assert events[0]['child_status'] == 'transport_interrupted'
