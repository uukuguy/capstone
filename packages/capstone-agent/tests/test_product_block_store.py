import pytest
from capstone_agent.artifacts import MemoryObjectStore
from capstone_agent.product_block_store import ProductBlockStore
from test_product_blocks import index


def test_published_index_survives_store_adapter_recreation():
    objects = MemoryObjectStore(); value = index(b'paragraph\n')
    ref = ProductBlockStore(objects, max_index_bytes=8192).publish(value)
    assert ProductBlockStore(objects, max_index_bytes=8192).read('thr_one', ref) == value
    with pytest.raises(ValueError):
        ProductBlockStore(objects, max_index_bytes=8192).read('thr_other', ref)


def test_failed_readback_does_not_publish_a_receipt():
    class CorruptStore(MemoryObjectStore):
        def put(self, key, content, mime):
            super().put(key, b'corrupt', mime)
    with pytest.raises(ValueError):
        ProductBlockStore(CorruptStore(), max_index_bytes=8192).publish(index(b'paragraph'))


def test_budget_rejects_before_write():
    objects = MemoryObjectStore()
    with pytest.raises(ValueError, match='budget'):
        ProductBlockStore(objects, max_index_bytes=10).publish(index(b'paragraph'))
    assert objects.contents == {}


def test_retries_use_new_immutable_blobs_and_tampering_fails():
    objects = MemoryObjectStore(); store = ProductBlockStore(objects, max_index_bytes=8192)
    value = index(b'paragraph'); a, b = store.publish(value), store.publish(value)
    assert a['blob_id'] != b['blob_id']
    assert store.read('thr_one', a) == store.read('thr_one', b)
    with pytest.raises(ValueError):
        store.read('thr_one', {**a, 'blob_id': '../escape'})
    with pytest.raises(ValueError):
        store.read('thr_one', {**a, 'sha256': '0'*64})
