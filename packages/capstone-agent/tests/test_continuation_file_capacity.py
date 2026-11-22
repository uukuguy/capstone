"""Continuation selection must not discard files below application capacity."""
import re
from types import SimpleNamespace

import pytest

from capstone_agent import application_capacity
from capstone_agent.thread_materials import _process_files


def test_goal_continuation_freezes_only_named_files_from_its_predecessor(monkeypatch):
    from dataclasses import replace

    from capstone_agent.thread_materials import freeze_material_submission
    from test_unscoped_research_intent import governed_executor, open_store

    service = open_store(governed_executor(), session_type='enterprise-research')
    snapshot = replace(service._snapshot, works=({'work_id': 'work_one', 'goal_continuation': {
        'predecessor_attempt_id': 'attempt_prior', 'product_refs': ['draft.md']}},))
    source = {'thread_id': snapshot.thread_id, 'attempt_id': 'attempt_prior', 'work_id': 'work_one',
              'artifact_id': 'artifact_draft', 'file_name': 'draft.md', 'source_status': 'completed',
              'sha256': 'a' * 64, 'size_bytes': 17}

    def files(_service, _snapshot, work_id, source_id, _connection):
        assert (work_id, source_id) == ('work_one', 'attempt_prior')
        return [source, {**source, 'artifact_id': 'artifact_other', 'file_name': 'other.md'}]

    monkeypatch.setattr('capstone_agent.thread_materials._process_files', files)
    submission, rejection = freeze_material_submission(service, snapshot, {}, {},
        work_id='work_one', resume_goal_inputs=True)
    assert rejection is None
    assert submission['_continuation_artifacts'] == [source]
    assert submission['_resource_manifests'][0]['sha256'] == source['sha256']

    monkeypatch.setattr('capstone_agent.thread_materials._process_files', lambda *args: [])
    submission, rejection = freeze_material_submission(service, snapshot, {}, {}, work_id='work_one',
        resume_goal_inputs=True)
    assert rejection is None
    assert '_continuation_artifacts' not in submission
    assert 'draft.md' in submission['_material_notices'][0]


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
