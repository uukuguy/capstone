"""Bounded operator-only request snapshots for the local diagnostic lane."""
from __future__ import annotations

import json
from hashlib import sha256
import re
from os import environ
from uuid import uuid4

from .progress import _redact_text

MAX_SNAPSHOT_BYTES = 1_000_000
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}')
_REF = re.compile(r'ctxdoc_[a-f0-9]{32}')
_REQUEST = re.compile(r'ctx-[1-9][0-9]{0,8}')
_DISPATCH = re.compile(r'request-[1-9][0-9]{0,8}')
_SECRET = re.compile(
    r'-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)'
    r'|\bBearer\s+[^\s,;"]+|\b(?:sk-|ghp_|github_pat_|xox[baprs]-)[A-Za-z0-9_-]{12,}'
    r'|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    re.IGNORECASE,
)
_ROLES = {
    'system': {'system'},
    'tools': {'definition'},
    'messages': {'user', 'assistant', 'other', 'toolCall', 'unsupported'},
    'tool_results': {'toolResult', 'unsupported'},
}


def diagnostics_enabled() -> bool:
    return environ.get('CAPSTONE_CONTEXT_DIAGNOSTICS') == '1'


def _matches(value, pattern):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _checked_origin(value):
    if not isinstance(value, dict):
        return None
    kind, identifier, revision, delivery = (value.get(field) for field in ('kind', 'id', 'revision', 'delivery'))
    if (kind not in ('file', 'skill', 'compaction', 'history', 'handoff', 'observation', 'runtime') or not _matches(identifier, _ID) or not _matches(revision, _ID)
            or delivery not in ('text', 'reference', 'preview')):
        return None
    result = {'kind': kind, 'id': identifier, 'revision': revision, 'delivery': delivery}
    if kind == 'file':
        digest, offset, length = (value.get(field) for field in ('digest', 'offset', 'length'))
        if (not _matches(digest, re.compile(r'[a-f0-9]{64}')) or type(offset) is not int or type(length) is not int
                or offset < 0 or length < 0 or offset + length > 2**53-1):
            return None
        result.update(digest=digest, offset=offset, length=length)
    return result


def checked_snapshot(event: dict) -> dict | None:
    """Validate and redact in the isolated host before transport or storage."""
    if not isinstance(event, dict):
        return None
    request, dispatch = event.get('request_id'), event.get('dispatch_id')
    kind, model = event.get('kind'), event.get('model_id')
    count, entries = event.get('total_entries'), event.get('entries')
    if (not _matches(request, _REQUEST) or dispatch is not None and not _matches(dispatch, _DISPATCH)
            or kind not in ('main', 'analysis', 'summary') or type(count) is not int
            or not isinstance(entries, list) or not 0 <= len(entries) <= min(count, 256)):
        return None
    admitted = []
    known_credentials = {value for key, value in environ.items() if len(value) >= 8
                         and re.search(r'(?:API_KEY|TOKEN|SECRET|PASSWORD|ACCESS_KEY)$', key)}
    for index, item in enumerate(entries, 1):
        if not isinstance(item, dict):
            return None
        carrier, role, text, truncated = (item.get(k) for k in ('carrier', 'role', 'text', 'truncated'))
        if (not isinstance(carrier, str) or not isinstance(role, str) or role not in _ROLES.get(carrier, ())
                or type(item.get('index')) is not int or item['index'] != index
                or not isinstance(text, str) or type(truncated) is not bool
                or len(text.encode('utf-8')) > 48_004):
            return None
        redacted = _SECRET.sub('[REDACTED]', _redact_text(text))
        for credential in sorted(known_credentials, key=len, reverse=True):
            redacted = redacted.replace(credential, '[REDACTED]')
        row = {'index': index, 'carrier': carrier, 'role': role, 'text': redacted,
               'truncated': truncated, 'redacted': redacted != text or item.get('redacted') is True,
               'digest': sha256(redacted.encode()).hexdigest()}
        if carrier in {'messages', 'tool_results'}:
            message_index, block_index = item.get('message_index'), item.get('block_index')
            if all(type(value) is int and 1 <= value <= 2**31 - 1 for value in (message_index, block_index)):
                row.update(message_index=message_index, block_index=block_index)
        if role in {'system', 'toolCall', 'toolResult', 'unsupported'} and _matches(item.get('source_id'), _ID):
            row['source_id'] = item['source_id']
        if _matches(item.get('name'), _ID):
            row['name'] = item['name']
        origin = _checked_origin(item.get('origin'))
        if origin is not None and ((carrier == 'tool_results' and origin['kind'] in ('file', 'skill'))
                                   or (carrier == 'messages' and role == 'user' and origin['kind'] in ('compaction', 'history', 'handoff', 'observation', 'runtime'))):
            row['origin'] = origin
        admitted.append(row)
    return {'schema': 'capstone-model-context-snapshot/1', 'request_id': request,
            'dispatch_id': dispatch, 'kind': kind, 'model_id': model if _matches(model, _ID) else None,
            'total_entries': count, 'entries': admitted}


def _object_key(thread_id: str, attempt_id: str, ref: str) -> str:
    if not (_matches(thread_id, _ID) and _matches(attempt_id, _ID) and _matches(ref, _REF)):
        raise KeyError('invalid context snapshot reference')
    return f'diagnostics/model-context/{thread_id}/{attempt_id}/{ref}.json'


def save_snapshot(objects, thread_id: str, attempt_id: str, snapshot: dict) -> str:
    ref = 'ctxdoc_' + uuid4().hex
    body = json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')).encode()
    if len(body) > MAX_SNAPSHOT_BYTES:
        raise ValueError('context snapshot exceeds the storage limit')
    objects.put(_object_key(thread_id, attempt_id, ref), body, 'application/json')
    return ref


def read_snapshot(objects, thread_id: str, attempt_id: str, ref: str, index: int | None) -> dict:
    try:
        body = objects.get(_object_key(thread_id, attempt_id, ref), MAX_SNAPSHOT_BYTES)
    except Exception as error:
        code = getattr(error, 'response', {}).get('Error', {}).get('Code')
        if isinstance(error, KeyError) or code in {'NoSuchKey', '404', 'NotFound'} or getattr(error, 'code', None) == 404:
            raise KeyError('context snapshot unavailable') from None
        raise
    if len(body) > MAX_SNAPSHOT_BYTES:
        raise ValueError('context snapshot exceeds the storage limit')
    snapshot = json.loads(body)
    if snapshot.get('schema') != 'capstone-model-context-snapshot/1':
        raise ValueError('unknown context snapshot format')
    if index is not None:
        if not 1 <= index <= len(snapshot['entries']):
            raise KeyError(index)
        return {'entry': snapshot['entries'][index - 1]}
    entries = []
    for row in snapshot['entries']:
        entry = {key: val for key, val in row.items() if key != 'text'}
        if row['role'] in {'user', 'assistant'} and not row.get('origin'):
            entry['preview'] = row['text'][:180]
        entries.append(entry)
    return {**snapshot, 'entries': entries}
