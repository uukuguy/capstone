from hashlib import sha256
import pytest

from capstone_agent.product_blocks import build_index, resolve_block
from test_product_block_identity import selection


def index(data, **kwargs):
    parent = {**selection()['parent_ref'], 'digest': sha256(data).hexdigest()}
    return build_index(parent, data, max_input_bytes=4096, max_blocks=20, **kwargs)


def test_duplicate_unicode_paragraphs_preserve_exact_crlf_source():
    data = '中文 e\u0301 👩‍🔬。\r\n\r\n中文 e\u0301 👩‍🔬。\r\n'.encode()
    result = index(data)
    a, b = result['blocks']
    assert a['content_digest'] == b['content_digest']
    assert a['block_id'] != b['block_id']
    for block in (a, b):
        assert resolve_block(result, data, block['block_id'], block['content_digest']) == '中文 e\u0301 👩‍🔬。\r\n'.encode()


def test_nested_code_table_and_html_are_not_plain_paragraphs():
    data = b'# Title\n\n- nested\n\n> quote\n\n```\ncode\n```\n\n|a|b|\n|-|-|\n|1|2|\n\nplain\n\ntext <span>html</span>\n'
    result = index(data)
    assert len(result['blocks']) == 1
    assert resolve_block(result, data, **{k:result['blocks'][0][k] for k in ('block_id','content_digest')}) == b'plain\n'


def test_reference_links_are_explicitly_unavailable_until_dependency_binding():
    result = index(b'Use [source][a].\n\n[a]: https://example.invalid\n')
    assert result['blocks'] == []
    assert result['limitations'] == ['reference_definition_binding_required']


def test_changed_source_and_tampered_span_are_rejected():
    data = b'first\n\nsecond\n'; result = index(data); block = result['blocks'][0]
    with pytest.raises(ValueError):
        resolve_block(result, data+b'changed', block['block_id'], block['content_digest'])
    result['blocks'][0]['byte_end'] = len(data)
    with pytest.raises(ValueError):
        resolve_block(result, data, block['block_id'], block['content_digest'])


def test_processing_limits_do_not_silently_truncate():
    parent = selection()['parent_ref']
    with pytest.raises(ValueError, match='budget'):
        build_index(parent, b'x'*20, max_input_bytes=10, max_blocks=1)
    with pytest.raises(ValueError, match='budget'):
        build_index({**parent, 'digest':sha256(b'a\n\nb').hexdigest()}, b'a\n\nb', max_input_bytes=20, max_blocks=1)
