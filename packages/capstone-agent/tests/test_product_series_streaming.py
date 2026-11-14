"""Bounded object adapters used by exact adoption verification."""
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from capstone_agent.artifacts import MemoryObjectStore, S3ObjectStore, GCSObjectStore
from capstone_agent.product_series_source import ProductSourceError, verify_source


def test_s3_stream_reads_fixed_chunks_and_closes_on_early_stop():
    store = S3ObjectStore.__new__(S3ObjectStore)
    store.bucket = 'private'
    stream = BytesIO(b'abcdefgh')
    store.client = SimpleNamespace(get_object=Mock(return_value={'Body':stream}))
    chunks = store.iter_bytes('key', chunk_size=3)
    assert next(chunks) == b'abc'
    chunks.close()
    assert stream.closed


def test_gcs_stream_pins_generation_before_reading():
    store = GCSObjectStore.__new__(GCSObjectStore)
    stream = BytesIO(b'abcdefgh')
    blob = Mock()
    blob.open.return_value = stream
    store.bucket = SimpleNamespace(blob=Mock(return_value=blob))
    assert list(store.iter_bytes('key', chunk_size=3)) == [b'abc',b'def',b'gh']
    blob.reload.assert_called_once()
    blob.open.assert_called_once_with('rb', chunk_size=3)
    assert stream.closed


def test_integrity_failure_closes_stream_without_reading_rest():
    closed=[]
    class Source:
        def iter_bytes(self,key,*,chunk_size):
            try:
                yield b'overflow'
                raise AssertionError('must stop at declared byte size')
            finally:
                closed.append(True)
    with pytest.raises(ProductSourceError, match='source_integrity'):
        verify_source(None,Source(),'thread',None,metadata={'size_bytes':1,'object_key':'key','ref':{'digest':'0'*64}})
    assert closed==[True]


@pytest.mark.parametrize('size',[0,-1,True])
def test_stream_rejects_invalid_chunk_size(size):
    with pytest.raises(ValueError):
        list(MemoryObjectStore().iter_bytes('key',chunk_size=size))


def test_missing_cloud_objects_have_safe_unavailable_reason():
    from botocore.exceptions import ClientError
    from google.api_core.exceptions import NotFound
    s3=S3ObjectStore.__new__(S3ObjectStore)
    s3.bucket='private'
    s3.client=SimpleNamespace(get_object=Mock(side_effect=ClientError({'Error':{'Code':'NoSuchKey'}},'GetObject')))
    gcs=GCSObjectStore.__new__(GCSObjectStore)
    blob=Mock()
    blob.reload.side_effect=NotFound('private object path')
    gcs.bucket=SimpleNamespace(blob=Mock(return_value=blob))
    for store in (s3,gcs):
        with pytest.raises(ProductSourceError,match='source_unavailable'):
            verify_source(None,store,'thread',None,metadata={'size_bytes':1,'object_key':'key','ref':{'digest':'0'*64}})
