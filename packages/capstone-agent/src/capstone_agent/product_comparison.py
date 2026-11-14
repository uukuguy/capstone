"""Bounded literal Markdown comparison over verified immutable products."""
from difflib import SequenceMatcher
import json
from pathlib import PurePosixPath

from .product_series_source import ProductSourceError, source_metadata, verify_source


def compare_products(threads, objects, thread_id, original_ref, revised_ref, *,
                     max_input_bytes, max_lines, max_output_bytes):
    for value in (max_input_bytes, max_lines, max_output_bytes):
        if type(value) is not int or value < 1:
            raise ValueError('explicit comparison budgets required')
    texts, lines = [], []
    for ref in (original_ref, revised_ref):
        metadata = source_metadata(threads, thread_id, ref)
        if PurePosixPath(metadata['entry']['source'].get('file_name', '')).suffix.lower() not in {'.md', '.markdown'}:
            raise ProductSourceError('unsupported_format')
        if metadata['size_bytes'] > max_input_bytes:
            raise ProductSourceError('input_budget')
        data = verify_source(threads, objects, thread_id, ref, metadata=metadata, collect=True)
        try:
            text = data.decode('utf-8')
        except UnicodeError:
            raise ProductSourceError('invalid_utf8') from None
        parts = text.splitlines(keepends=True)
        if len(parts) > max_lines:
            raise ProductSourceError('line_budget')
        texts.append(text)
        lines.append(parts)
    changes = [{'kind': tag, 'original': [a,b], 'revised': [c,d]}
        for tag,a,b,c,d in SequenceMatcher(None, lines[0], lines[1], autojunk=False).get_opcodes()]
    result = {'schema': 'capstone-product-comparison/1',
        'original_ref': original_ref, 'revised_ref': revised_ref,
        'original_text': texts[0], 'revised_text': texts[1], 'changes': changes,
        'interpretation': 'literal-text-difference'}
    if len(json.dumps(result, ensure_ascii=False).encode('utf-8')) > max_output_bytes:
        raise ProductSourceError('output_budget')
    return result
