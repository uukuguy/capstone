"""Bounded literal Markdown comparison over verified immutable products."""
from difflib import SequenceMatcher
import json

from .product_index_reader import read_index_source


def compare_products(threads, objects, thread_id, original_ref, revised_ref, *,
                     max_input_bytes, max_lines, max_output_bytes):
    for value in (max_input_bytes, max_lines, max_output_bytes):
        if type(value) is not int or value < 1:
            raise ValueError('explicit comparison budgets required')
    texts, lines = [], []
    for ref in (original_ref, revised_ref):
        data = read_index_source(threads, objects, thread_id, ref, max_bytes=max_input_bytes)
        text = data.decode('utf-8')
        parts = text.splitlines(keepends=True)
        if len(parts) > max_lines:
            raise ValueError('comparison line budget exceeded')
        texts.append(text)
        lines.append(parts)
    changes = [{'kind': tag, 'original': [a,b], 'revised': [c,d]}
        for tag,a,b,c,d in SequenceMatcher(None, lines[0], lines[1], autojunk=False).get_opcodes()]
    result = {'schema': 'capstone-product-comparison/1',
        'original_ref': original_ref, 'revised_ref': revised_ref,
        'original_text': texts[0], 'revised_text': texts[1], 'changes': changes,
        'interpretation': 'literal-text-difference'}
    if len(json.dumps(result, ensure_ascii=False).encode('utf-8')) > max_output_bytes:
        raise ValueError('comparison output budget exceeded')
    return result
