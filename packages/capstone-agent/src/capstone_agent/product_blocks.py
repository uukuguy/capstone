"""Bounded source paragraph indexing, independent of authorization and storage.

This in-memory worker primitive does not provide GB-scale indexing or admission.
Callers must supply processing budgets and authorize the parent before reading it.
"""
from hashlib import sha256
from importlib.metadata import version
import json
import re

from markdown_it import MarkdownIt

from .thread_products import checked_ref


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                            separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def build_index(parent_ref, content: bytes, *, max_input_bytes: int, max_blocks: int):
    for budget in (max_input_bytes, max_blocks):
        if type(budget) is not int or budget < 1:
            raise ValueError('invalid processing budget')
    if not isinstance(content, bytes) or len(content) > max_input_bytes:
        raise ValueError('input processing budget exceeded')
    parent = checked_ref(parent_ref)
    if parent['origin'] not in {'native_file', 'task_delivery'}:
        raise ValueError('unsupported paragraph source')
    if sha256(content).hexdigest() != parent['digest']:
        raise ValueError('parent content changed')
    text = content.decode('utf-8', errors='strict')
    if '\0' in text:
        raise ValueError('unsupported text content')
    parser_id = f'markdown-it-py/{version("markdown-it-py")};commonmark+table+labels;source-paragraph/2'
    # Markdown normalizes CR/CRLF. Preserve original UTF-8 source boundaries.
    lines = re.findall(r'[^\r\n]*(?:\r\n|\r|\n|$)', text)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line.encode('utf-8')))
    environment = {}
    tokens = MarkdownIt('commonmark', {'store_labels': True}).enable('table').parse(text, environment)
    result = {'schema': 'capstone-product-block-index/1', 'parent_ref': parent,
              'parser_id': parser_id, 'blocks': [], 'limitations': []}
    for position, token in enumerate(tokens):
        if token.type != 'paragraph_open' or token.level != 0:
            continue
        inline = tokens[position + 1]
        children = list(_descendants(inline))
        if any(child.type == 'html_inline' for child in children):
            continue
        start, end = token.map
        a, b = offsets[start], offsets[end]
        raw = content[a:b]
        dependencies = []
        labels = dict.fromkeys(child.meta['label'] for child in children
                               if child.type in {'link_open', 'image'} and 'label' in child.meta)
        for label in labels:
            first, last = environment['references'][label]['map']
            da, db = offsets[first], offsets[last]
            dependencies.append({'label': label, 'byte_start': da, 'byte_end': db,
                                 'content_digest': sha256(content[da:db]).hexdigest()})
        block = {'block_id': f'paragraph_{start}_{end}', 'byte_start': a,
                 'byte_end': b, 'content_digest': sha256(raw).hexdigest(),
                 'dependencies': dependencies}
        result['blocks'].append(block)
        if len(result['blocks']) > max_blocks:
            raise ValueError('block processing budget exceeded')
    return {**result, 'index_ref': _digest(result)}


def resolve_block(index, content: bytes, block_id: str, content_digest: str) -> bytes:
    """Resolve an already host-published index; this does not authorize access."""
    if _digest({k:v for k,v in index.items() if k != 'index_ref'}) != index['index_ref']:
        raise ValueError('index content changed')
    if sha256(content).hexdigest() != index['parent_ref']['digest']:
        raise ValueError('parent content changed')
    matches = [block for block in index['blocks'] if block['block_id'] == block_id]
    if len(matches) != 1:
        raise ValueError('unknown paragraph identity')
    block = matches[0]
    raw = content[block['byte_start']:block['byte_end']]
    if sha256(raw).hexdigest() != content_digest or content_digest != block['content_digest']:
        raise ValueError('paragraph content changed')
    return raw


def _descendants(token):
    for child in token.children or ():
        yield child
        yield from _descendants(child)


def resolve_dependencies(index, content: bytes, block_id: str, content_digest: str) -> list[bytes]:
    """Return exact definition fragments separately, without rewriting the source."""
    resolve_block(index, content, block_id, content_digest)
    block = next(block for block in index['blocks'] if block['block_id'] == block_id)
    fragments = []
    for dependency in block['dependencies']:
        raw = content[dependency['byte_start']:dependency['byte_end']]
        if sha256(raw).hexdigest() != dependency['content_digest']:
            raise ValueError('paragraph dependency changed')
        fragments.append(raw)
    return fragments
