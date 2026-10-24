"""Continuation selection must not discard files below application capacity."""
import re
from types import SimpleNamespace

import pytest

from capstone_agent import application_capacity
from capstone_agent.thread_materials import _process_files


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
