import pytest
from capstone_agent.artifacts import MemoryObjectStore
from capstone_agent.native_artifact_projection import artifact_object_key
from capstone_agent.thread_products import product_index
from capstone_agent.product_comparison import compare_products
from test_thread_http_api import _service
from test_thread_deliveries import native_file


def test_comparison_validates_source_and_never_silently_truncates():
    threads, objects = _service(), MemoryObjectStore()
    data = b'Original paragraph.\n'
    source, _ = native_file(threads, 'thr_demo_39', data, name='report.md')
    key = artifact_object_key(source)
    objects.put(key, data, 'text/markdown')
    ref = next(p['ref'] for p in product_index(threads, 'thr_demo_39')['products'] if p['ref']['origin']=='native_file')
    args = dict(max_input_bytes=1024, max_lines=100, max_output_bytes=4096)
    result = compare_products(threads, objects, 'thr_demo_39', ref, ref, **args)
    assert result['original_ref'] == ref and result['revised_text'] == data.decode()
    assert result['changes'] == [{'kind': 'equal', 'original': [0,1], 'revised': [0,1]}]
    with pytest.raises(ValueError, match='budget'):
        compare_products(threads, objects, 'thr_demo_39', ref, ref, **{**args,'max_input_bytes': 1})
    objects.put(key, b'Changed paragraph.\n', 'text/markdown')
    with pytest.raises(ValueError, match='source_integrity'):
        compare_products(threads, objects, 'thr_demo_39', ref, ref, **args)
    with pytest.raises(ValueError, match='scope'):
        compare_products(threads, objects, 'other_thread', ref, ref, **args)


@pytest.mark.parametrize('failure,expected', [
    ('format','unsupported_format'), ('size','input_budget'), ('lines','line_budget'),
    ('output','output_budget'), ('missing','source_unavailable'),
    ('corrupt','source_integrity'), ('encoding','invalid_utf8'),
])
def test_comparison_has_stable_failure_codes(failure, expected):
    from capstone_agent.product_series_source import ProductSourceError
    threads,objects=_service(),MemoryObjectStore()
    data=b'\xff' if failure=='encoding' else b'One\nTwo\n'
    source,_=native_file(threads,'thr_demo_39',data,name='report.pdf' if failure=='format' else 'report.md')
    objects.put(artifact_object_key(source),data,'text/markdown')
    ref=next(p['ref'] for p in product_index(threads,'thr_demo_39')['products'] if p['ref']['origin']=='native_file')
    args=dict(max_input_bytes=1 if failure=='size' else 1024,
        max_lines=1 if failure=='lines' else 100,max_output_bytes=1 if failure=='output' else 4096)
    if failure=='missing': objects.contents.clear()
    if failure=='corrupt': objects.contents[artifact_object_key(source)]=b'bad'
    with pytest.raises(ProductSourceError) as caught:
        compare_products(threads,objects,'thr_demo_39',ref,ref,**args)
    assert caught.value.code==expected
