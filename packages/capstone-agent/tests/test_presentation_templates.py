from hashlib import sha256
from pathlib import Path

import pytest

from capstone_agent.artifacts import MemoryObjectStore
from capstone_agent.presentation_templates import PresentationTemplates
from capstone_agent.thread_resources import ResourceUploads
from test_enterprise_normal_chat import chat_store
from test_thread_postgres import postgres_thread_service


@pytest.fixture(autouse=True)
def clean_owned_template_rows(chat_store):
    service, thread = chat_store
    yield
    if not hasattr(service, '_lock'):
        with service._connect() as connection:
            connection.execute('DELETE FROM capstone_presentation_templates WHERE owner_thread_id=%s', (thread,))


BUILTIN = Path(__file__).resolve().parents[3] / 'tools/presentation-templates/state-grid.pptx'


def setup_library(service):
    objects = MemoryObjectStore()
    uploads = ResourceUploads(service, objects, chunk_bytes=8192)
    return PresentationTemplates(service, objects, builtin=BUILTIN, uploads=uploads), uploads, objects


def upload(uploads, thread, data, request='upload-template'):
    uid = uploads.begin(thread, 'uploaded.pptx', len(data), request)['upload_id']
    for i, start in enumerate(range(0, len(data), uploads.chunk_bytes)):
        uploads.part(thread, uid, i, data[start:start+uploads.chunk_bytes])
    return uploads.complete(thread, uid)


def ref(template):
    return {key: template[key] for key in ('template_id', 'version', 'sha256')}


def test_default_is_builtin_and_selection_survives_service_restart(chat_store):
    service, thread = chat_store
    library, uploads, objects = setup_library(service)
    default = library.selection(thread, 'enterprise')
    assert default['template']['template_id'] == 'state-grid'
    assert default['revision'] == 0
    data = BUILTIN.read_bytes()
    source = upload(uploads, thread, data)
    added = library.add(thread, 'enterprise', source, name='Session template', request_id='add-one')
    chosen = library.select(thread, 'enterprise', ref(added), expected_revision=0, request_id='select-one')
    restored = PresentationTemplates(service, objects, builtin=BUILTIN, uploads=uploads)
    assert restored.selection(thread, 'enterprise') == chosen
    assert b''.join(restored.read(thread, 'enterprise', ref(added))) == data
    assert restored.freeze(thread, 'enterprise', override=ref(default['template']))['template_id'] == 'state-grid'
    assert restored.selection(thread, 'enterprise') == chosen


def test_uploaded_template_is_session_only_until_explicit_publication(chat_store):
    service, thread = chat_store
    library, uploads, _ = setup_library(service)
    added = library.add(thread, 'enterprise', upload(uploads, thread, BUILTIN.read_bytes()), name='Mine', request_id='add-one')
    assert added['scope'] == 'session'
    assert library.catalog(thread, 'enterprise')['templates'][0]['scope'] == 'session'
    library.select(thread, 'enterprise', ref(added), expected_revision=0, request_id='select-before-publish')
    published = library.publish(thread, 'enterprise', ref(added), request_id='publish-one')
    assert published['scope'] == 'library'
    current = library.selection(thread, 'enterprise')
    assert current['revision'] == 1 and current['template']['scope'] == 'library'
    assert ref(published) == ref(added)
    assert library.publish(thread, 'enterprise', ref(added), request_id='publish-one') == published


def test_revisions_and_idempotency_are_exact(chat_store):
    service, thread = chat_store
    library, _, _ = setup_library(service)
    default = ref(library.selection(thread, 'enterprise')['template'])
    selected = library.select(thread, 'enterprise', default, expected_revision=0, request_id='selection')
    assert library.select(thread, 'enterprise', default, expected_revision=0, request_id='selection') == selected
    with pytest.raises(ValueError, match='revision_conflict'):
        library.select(thread, 'enterprise', default, expected_revision=0, request_id='new-selection')
    with pytest.raises(ValueError, match='request_conflict'):
        library.select(thread, 'enterprise', default, expected_revision=1, request_id='selection')


def test_rejects_foreign_scope_changed_source_and_invalid_package(chat_store):
    service, thread = chat_store
    library, uploads, _ = setup_library(service)
    source = upload(uploads, thread, BUILTIN.read_bytes())
    with pytest.raises(Exception):
        library.add(thread, 'foreign-workspace', source, name='Mine', request_id='add-one')
    with pytest.raises(ValueError, match='source_changed'):
        library.add(thread, 'enterprise', {**source, 'sha256': '0'*64}, name='Mine', request_id='add-two')
    for version in (True, 1.0):
        with pytest.raises(ValueError, match='source_changed'):
            library.add(thread, 'enterprise', {**source, 'version': version}, name='Mine', request_id='invalid-type')
    bad = upload(uploads, thread, b'not-a-pptx', 'bad-upload')
    with pytest.raises(ValueError, match='invalid_template'):
        library.add(thread, 'enterprise', bad, name='Bad', request_id='bad-add')
    assert library.catalog(thread, 'enterprise')['templates'] == []


def test_catalog_has_bounded_cursor_and_frozen_identity(chat_store):
    service, thread = chat_store
    library, uploads, _ = setup_library(service)
    source = upload(uploads, thread, BUILTIN.read_bytes())
    for i in range(3):
        library.add(thread, 'enterprise', source, name=f'Template{i}', request_id=f'add-{i}')
    first = library.catalog(thread, 'enterprise', limit=2)
    assert len(first['templates']) == 2 and first['has_more']
    second = library.catalog(thread, 'enterprise', limit=2, after=first['next_after'])
    assert len(second['templates']) == 1 and not second['has_more']
    assert not {t['template_id'] for t in first['templates']} & {t['template_id'] for t in second['templates']}
    default = ref(first['builtin'])
    with pytest.raises(ValueError, match='template_not_found|identity_changed'):
        library.freeze(thread, 'enterprise', override={**default, 'sha256': sha256(b'changed').hexdigest()})


def test_published_template_crosses_sessions_only_inside_its_workspace(chat_store):
    service, thread = chat_store
    if hasattr(service, '_lock'):
        pytest.skip('Cross-session persistence uses the PostgreSQL adapter')
    from dataclasses import replace
    import uuid
    from capstone_agent.thread_protocol import RunSnapshot
    from test_thread_postgres import _snapshot
    sibling, foreign = 'thr_test_' + uuid.uuid4().hex, 'thr_test_' + uuid.uuid4().hex
    for identity, workspace in ((sibling, 'enterprise'), (foreign, 'another-workspace')):
        snapshot = replace(_snapshot(identity), run=RunSnapshot('run_' + uuid.uuid4().hex, 'open'))
        service.create_thread(snapshot, workspace_name=workspace)
    try:
        library, uploads, objects = setup_library(service)
        data = BUILTIN.read_bytes()
        added = library.add(thread, 'enterprise', upload(uploads, thread, data), name='Shared', request_id='add-shared')
        assert library.catalog(sibling, 'enterprise')['templates'] == []
        with pytest.raises(ValueError, match='not_found'):
            library.freeze(sibling, 'enterprise', override=ref(added))
        library.publish(thread, 'enterprise', ref(added), request_id='publish-shared')
        assert library.catalog(sibling, 'enterprise')['templates'][0]['template_id'] == added['template_id']
        assert library.catalog(foreign, 'another-workspace')['templates'] == []
        with pytest.raises(ValueError, match='not_found'):
            library.freeze(foreign, 'another-workspace', override=ref(added))
        # Published bytes have their own durable reference, not an upload lifetime.
        with service._connect() as connection:
            connection.execute('DELETE FROM capstone_threads WHERE thread_id=%s', (thread,))
        restored = PresentationTemplates(service, objects, builtin=BUILTIN)
        assert b''.join(restored.read(sibling, 'enterprise', ref(added))) == data
    finally:
        with service._connect() as connection:
            connection.execute('DELETE FROM capstone_threads WHERE thread_id=ANY(%s)', ([sibling, foreign],))


def test_processing_rejection_does_not_change_upload_quota_or_publish(chat_store):
    service, thread = chat_store
    library, uploads, _ = setup_library(service)
    from capstone_agent.presentation_templates import PROCESSING_BYTES
    assert uploads.max_file_bytes > PROCESSING_BYTES
    source = upload(uploads, thread, BUILTIN.read_bytes())
    from unittest.mock import patch
    with patch('capstone_agent.presentation_templates.PROCESSING_BYTES', len(BUILTIN.read_bytes()) - 1):
        with pytest.raises(ValueError, match='processing_limit'):
            library.add(thread, 'enterprise', source, name='Large', request_id='large-add')
    assert uploads.resources(thread)[0] == source
    assert library.catalog(thread, 'enterprise')['templates'] == []
