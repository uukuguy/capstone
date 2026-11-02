"""Continuation selection must not discard files below application capacity."""
import re
from types import SimpleNamespace

import pytest

from capstone_agent import application_capacity
from capstone_agent.thread_materials import _process_files


@pytest.mark.parametrize('change,accepted', [({'saved_at': '2026-11-02T10:00:00Z'}, True),
    ({'work_id': 'work_other'}, False), ({'sha256': '0' * 64}, False),
    ({'unknown_metadata': True}, False)])
def test_historical_resource_read_preserves_frozen_identity(monkeypatch, change, accepted):
    from hashlib import sha256
    from capstone_agent.continuation_resources import artifact_resource, resource_reader_for
    import capstone_agent.native_artifact_projection as projection
    data = b'catalog,data\noriginal,1\n'
    source = {'thread_id': 'thr_test', 'attempt_id': 'attempt_old', 'artifact_id': 'file-old',
              'work_id': 'work_test', 'file_name': 'catalog.csv', 'size_bytes': len(data),
              'sha256': sha256(data).hexdigest()}
    manifest = artifact_resource(source)
    claim = SimpleNamespace(thread_id='thr_test', task_context=SimpleNamespace(
        binding=SimpleNamespace(work_id='work_test')), submission={
        '_resource_manifests': [manifest], '_continuation_artifacts': [source]})
    monkeypatch.setattr(projection, 'native_artifact_page', lambda *args, **kwargs: {
        'artifacts': [{**source, **change}], 'has_more': False, 'next_after': 1})
    reads = []
    monkeypatch.setattr(projection, 'retain_native_artifact', lambda *args: reads.append(1) or data)
    reader = resource_reader_for(SimpleNamespace(), claim)
    if accepted:
        assert b''.join(reader(manifest)) == data
        assert reads == [1]
    else:
        from capstone_agent.continuation_resources import ContinuationResourceUnavailable
        with pytest.raises(ContinuationResourceUnavailable):
            list(reader(manifest))
        assert reads == []


@pytest.mark.parametrize('source_id', [None, 'attempt_saved'])
@pytest.mark.parametrize('capacity', [80, 300])
def test_database_continuation_uses_initialized_capacity(monkeypatch, source_id, capacity):
    monkeypatch.setattr(application_capacity, '_current', application_capacity._profile({'artifact_count': capacity}))
    rows = [{'payload': {'artifact': {'file_name': f'file-{i}.csv'}}} for i in range(capacity)]

    class Connection:
        def execute(self, query, parameters):
            # Model only the database's final LIMIT, so this catches a hidden
            # fixed bound before Python sees the selected files.
            token = re.search(r'LIMIT\s+(%s|\d+)\s*$', query).group(1)
            count = parameters[-1] if token == '%s' else int(token)
            return SimpleNamespace(fetchall=lambda: rows[:count])

    service = SimpleNamespace(_event_from_row=lambda row: SimpleNamespace(to_document=lambda: row))
    selected = _process_files(service, SimpleNamespace(thread_id='thread'), 'work', source_id, Connection())
    assert len(selected) == capacity
