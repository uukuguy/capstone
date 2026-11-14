"""Read exact retained products after ledger identity and processing admission.

The caller must authorize access to thread_id. This adapter does not fetch from
native executors or promote source objects. Missing retained bytes stay missing.
"""
from hashlib import sha256
from pathlib import PurePosixPath

from .thread_products import checked_ref, _snapshot, _events, _event_entries


def index_source_metadata(service, thread_id, parent_ref, *, max_bytes):
    if type(max_bytes) is not int or max_bytes < 1:
        raise ValueError('invalid source processing budget')
    ref = checked_ref(parent_ref)
    if ref['thread_id'] != thread_id or ref['origin'] not in {'native_file', 'task_delivery'}:
        raise ValueError('source reference is outside the authorized scope')
    snapshot = _snapshot(service, thread_id)
    events = _events(service, thread_id, seq=ref['event_seq'])
    expected_type = 'native_artifact_published' if ref['origin']=='native_file' else 'delivery_published'
    entries = [(event, entry) for event in events if event.event_type == expected_type
               for entry in _event_entries(service, snapshot, event, metadata_only=True)
               if entry['ref'] == ref]
    if len(entries) != 1:
        raise ValueError('exact source version unavailable')
    event, entry = entries[0]
    size = entry['byte_size']
    if type(size) is not int or not 0 <= size <= max_bytes:
        raise ValueError('source processing budget exceeded')
    source = entry['source']
    # The parser is Markdown-specific. Plain text receives a separate parser
    # identity later; do not interpret arbitrary text as Markdown implicitly.
    if PurePosixPath(source.get('file_name', '')).suffix.lower() not in {'.md', '.markdown'}:
        raise ValueError('unsupported paragraph source format')
    if ref['origin'] == 'native_file':
        from .native_artifact_projection import artifact_object_key
        key = artifact_object_key(source)
    else:
        from .thread_deliveries import _key
        key = _key(thread_id, event.payload['delivery'])
    return {'ref': ref, 'object_key': key, 'size_bytes': size, 'entry': entry}


def read_index_source(service, objects, thread_id, parent_ref, *, max_bytes):
    metadata = index_source_metadata(service, thread_id, parent_ref, max_bytes=max_bytes)
    ref, size = metadata['ref'], metadata['size_bytes']
    content = objects.get(metadata['object_key'], size)
    if len(content) != size or sha256(content).hexdigest() != ref['digest']:
        raise ValueError('source content changed')
    return content
