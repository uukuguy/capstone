"""Exact retained-file verification, independent of text processing budgets."""
from hashlib import sha256
from contextlib import closing

from .thread_products import checked_ref, _snapshot, _events, _event_entries


class ProductSourceError(ValueError):
    """Stable application error; its code is safe for public clients."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def source_metadata(threads, thread_id, value):
    ref = checked_ref(value)
    if ref['thread_id'] != thread_id or ref['origin'] not in {'native_file', 'task_delivery'}:
        raise ValueError('source reference is outside the authorized scope')
    snapshot = _snapshot(threads, thread_id)
    expected = 'native_artifact_published' if ref['origin'] == 'native_file' else 'delivery_published'
    matches = [(event, entry) for event in _events(threads, thread_id, seq=ref['event_seq'])
               if event.event_type == expected
               for entry in _event_entries(threads, snapshot, event, metadata_only=True)
               if entry['ref'] == ref]
    if len(matches) != 1:
        raise ProductSourceError('source_unavailable')
    event, entry = matches[0]
    size = entry['byte_size']
    if type(size) is not int or size < 0:
        raise ProductSourceError('source_integrity')
    if ref['origin'] == 'native_file':
        from .native_artifact_projection import artifact_object_key
        key = artifact_object_key(entry['source'])
    else:
        from .thread_deliveries import _key
        key = _key(thread_id, event.payload['delivery'])
    return {'ref': ref, 'object_key': key, 'size_bytes': size, 'entry': entry}


def verify_source(threads, objects, thread_id, ref, *, metadata=None, collect=False):
    """Hash a retained object in fixed chunks; adoption never collects its bytes.

    The ledger supplies the immutable key, size and digest. A stream may read at
    most that size plus one byte before rejection, with constant working memory.
    Text consumers must admit their own budgets before requesting collection.
    """
    metadata = metadata or source_metadata(threads, thread_id, ref)
    digest, size, parts = sha256(), 0, []
    try:
        with closing(objects.iter_bytes(metadata['object_key'], chunk_size=64 * 1024)) as stream:
            for chunk in stream:
                size += len(chunk)
                if size > metadata['size_bytes']:
                    raise ProductSourceError('source_integrity')
                digest.update(chunk)
                if collect:
                    parts.append(chunk)
    except (KeyError, FileNotFoundError):
        raise ProductSourceError('source_unavailable') from None
    if size != metadata['size_bytes'] or digest.hexdigest() != metadata['ref']['digest']:
        raise ProductSourceError('source_integrity')
    return b''.join(parts) if collect else metadata
