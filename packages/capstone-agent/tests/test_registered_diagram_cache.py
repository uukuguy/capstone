import pytest
from types import SimpleNamespace

from capstone_agent.registered_diagram_cache import RegisteredDiagramCache
from capstone_agent.federated_hosted import _prewarm_default_diagram


def diagram(model_id, revision):
    return {'model': {'id': model_id, 'revision': revision}, 'buses': [{'id': 'bus:1'}]}


def test_registered_revision_reuses_geometry_without_sharing_mutable_returns():
    calls = []
    def load(model_id, revision):
        calls.append((model_id, revision))
        return diagram(model_id, revision)
    cache = RegisteredDiagramCache(load, memory_pressure=lambda: False)
    first = cache('one', 'revision:one')
    first['buses'].clear()
    assert cache('one', 'revision:one')['buses'] == [{'id': 'bus:1'}]
    cache('one', 'revision:two')
    assert calls == [('one', 'revision:one'), ('one', 'revision:two')]


def test_pressure_releases_cached_geometry_and_failed_identity_is_not_cached():
    pressure = False
    wrong = True
    calls = []
    def load(model_id, revision):
        calls.append(model_id)
        return diagram('other' if wrong else model_id, revision)
    cache = RegisteredDiagramCache(load, memory_pressure=lambda: pressure)
    with pytest.raises(ValueError, match='identity'):
        cache('one', 'revision:one')
    wrong = False
    assert cache('one', 'revision:one')['model']['id'] == 'one'
    cache('one', 'revision:one')
    pressure = True
    cache('one', 'revision:one')
    assert calls == ['one', 'one', 'one']


def test_cache_budget_does_not_reject_valid_geometry():
    calls = []
    def load(model_id, revision):
        calls.append(model_id)
        return diagram(model_id, revision)
    cache = RegisteredDiagramCache(load, max_bytes=1, memory_pressure=lambda: False)
    assert cache('one', 'revision:one') == diagram('one', 'revision:one')
    assert cache('one', 'revision:one') == diagram('one', 'revision:one')
    assert calls == ['one', 'one']


def test_optional_prewarm_failure_keeps_service_available_and_retries():
    calls = []
    def load(model_id, revision):
        calls.append(model_id)
        if len(calls) == 1:
            raise TimeoutError('exporter not ready')
        return diagram(model_id, revision)
    cache = RegisteredDiagramCache(load, memory_pressure=lambda: False)
    descriptor = SimpleNamespace(model_id='one', model_revision='revision:one', available=True)
    catalog = SimpleNamespace(default_model_id='one', resolve=lambda model_id: descriptor)
    _prewarm_default_diagram(catalog, cache)
    assert cache('one', 'revision:one') == diagram('one', 'revision:one')
    assert calls == ['one', 'one']
