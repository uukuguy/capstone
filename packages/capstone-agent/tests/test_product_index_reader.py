import pytest
from capstone_agent.artifacts import MemoryObjectStore
from capstone_agent.native_artifact_projection import artifact_object_key
from capstone_agent.product_index_reader import read_index_source
from capstone_agent.thread_products import product_index
from test_thread_http_api import _service
from test_thread_deliveries import native_file


def prepare():
    service = _service(); data = b'Paragraph.\n'
    source, _ = native_file(service, 'thr_demo_39', data, name='report.md')
    ref = next(x['ref'] for x in product_index(service, 'thr_demo_39')['products'] if x['ref']['origin']=='native_file')
    class ObservedStore(MemoryObjectStore):
        calls = 0
        def get(self, key, limit):
            self.calls += 1
            return super().get(key, limit)
    store = ObservedStore(); store.put(artifact_object_key(source), data, 'text/markdown')
    return service, store, ref, data


def test_reader_checks_metadata_before_private_bytes():
    service, store, ref, data = prepare()
    assert read_index_source(service, store, 'thr_demo_39', ref, max_bytes=100) == data
    assert store.calls == 1


@pytest.mark.parametrize('change', ['budget','owner','version'])
def test_rejection_never_reads_object_store(change):
    service, store, ref, data = prepare()
    thread = 'other' if change=='owner' else 'thr_demo_39'
    if change=='version': ref={**ref,'digest':'0'*64}
    with pytest.raises(ValueError):
        read_index_source(service, store, thread, ref, max_bytes=1 if change=='budget' else 100)
    assert store.calls == 0


def test_corrupt_object_is_rejected():
    service, store, ref, data = prepare()
    for key in store.contents:store.contents[key]=b'changed'
    with pytest.raises(ValueError):
        read_index_source(service, store, 'thr_demo_39', ref, max_bytes=100)


def test_metadata_path_does_not_run_presentation_enrichment(monkeypatch):
    service, store, ref, data = prepare()
    def forbidden(*args, **kwargs):
        raise AssertionError('presentation must not run during source admission')
    monkeypatch.setattr('capstone_agent.native_product_roles.presentation_for_artifact', forbidden)
    assert read_index_source(service, store, 'thr_demo_39', ref, max_bytes=100) == data
