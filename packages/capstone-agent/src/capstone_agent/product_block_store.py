"""Private bounded index blobs; ledger publication remains the caller's duty."""
from hashlib import sha256
import json
import re
from uuid import uuid4

from .artifacts import ObjectStore
from .thread_products import checked_ref


def _bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      allow_nan=False, separators=(',', ':')).encode('utf-8')


def _hash(value):
    if not isinstance(value, str) or re.fullmatch('[a-f0-9]{64}', value) is None:
        raise ValueError('invalid index digest')
    return value


def _checked_index(value):
    if (not isinstance(value, dict) or set(value) != {
            'schema', 'parent_ref', 'parser_id', 'blocks', 'limitations', 'index_ref'}
            or value['schema'] != 'capstone-product-block-index/1'):
        raise ValueError('invalid product block index')
    checked_ref(value['parent_ref'])
    expected = sha256(_bytes({k:v for k,v in value.items() if k != 'index_ref'})).hexdigest()
    if expected != _hash(value['index_ref']):
        raise ValueError('index content changed')
    return value


class ProductBlockStore:
    """Store host-built manifests; never accept a browser manifest as trusted.

    Each attempt writes a unique immutable blob, compatible with create-only
    buckets. A durable ledger must retain the accepted receipt and fence retries.
    Unreferenced blobs require a separate ownership-scoped cleanup policy.
    """
    def __init__(self, objects: ObjectStore, *, max_index_bytes: int):
        if type(max_index_bytes) is not int or max_index_bytes < 1:
            raise ValueError('invalid index budget')
        self.objects, self.max_index_bytes = objects, max_index_bytes

    def _key(self, thread_id, ref):
        fields = {'schema', 'parent_ref', 'index_ref', 'blob_id', 'sha256', 'size_bytes'}
        if not isinstance(ref, dict) or set(ref) != fields or ref['schema'] != 'capstone-block-index-object/1':
            raise ValueError('invalid index object reference')
        parent = checked_ref(ref['parent_ref'])
        if parent['thread_id'] != thread_id:
            raise ValueError('index owner mismatch')
        if not isinstance(ref['blob_id'], str) or not re.fullmatch('[a-f0-9]{32}', ref['blob_id']):
            raise ValueError('invalid index blob identity')
        _hash(ref['sha256']); _hash(ref['index_ref'])
        if type(ref['size_bytes']) is not int or not 0 < ref['size_bytes'] <= self.max_index_bytes:
            raise ValueError('index read budget exceeded')
        owner = sha256(thread_id.encode()).hexdigest()
        return f'product-block-index/{owner}/{ref["index_ref"]}/{ref["blob_id"]}.json'

    def publish(self, index):
        data = _bytes(_checked_index(index))
        if len(data) > self.max_index_bytes:
            raise ValueError('index write budget exceeded')
        ref = {'schema': 'capstone-block-index-object/1',
               'parent_ref': checked_ref(index['parent_ref']), 'index_ref': index['index_ref'],
               'blob_id': uuid4().hex, 'sha256': sha256(data).hexdigest(), 'size_bytes': len(data)}
        thread_id = ref['parent_ref']['thread_id']
        self.objects.put(self._key(thread_id, ref), data, 'application/json')
        self.read(thread_id, ref)
        return ref

    def read(self, thread_id, ref):
        key = self._key(thread_id, ref)
        data = self.objects.get(key, ref['size_bytes'])
        if len(data) != ref['size_bytes'] or sha256(data).hexdigest() != ref['sha256']:
            raise ValueError('index object content changed')
        value = _checked_index(json.loads(data))
        if value['parent_ref'] != ref['parent_ref'] or value['index_ref'] != ref['index_ref']:
            raise ValueError('index object identity changed')
        return value
