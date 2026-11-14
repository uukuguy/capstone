"""Compose application index operations; callers authorize each Thread request."""
import math

from .product_blocks import parser_identity
from .product_block_store import ProductBlockStore
from .product_index_reader import index_source_metadata, read_index_source
from .product_index_worker import run_index_once
from .application_capacity import limits


class ProductIndexService:
    def __init__(self, threads, objects, jobs, *, budgets):
        required = {'max_input_bytes', 'max_blocks', 'max_output_bytes', 'wall_seconds',
                    'cpu_seconds', 'max_rss_bytes', 'lease_seconds', 'max_attempts'}
        if not isinstance(budgets, dict) or set(budgets) != required:
            raise ValueError('explicit index service budgets required')
        for key in required - {'wall_seconds'}:
            if type(budgets[key]) is not int or not 0 < budgets[key] <= 2147483647:
                raise ValueError('invalid index service budget')
        wall = budgets['wall_seconds']
        if type(wall) not in (int,float) or not math.isfinite(wall) or not 0 < wall < budgets['lease_seconds']:
            raise ValueError('invalid index deadline budget')
        self.threads, self.objects, self.jobs = threads, objects, jobs
        self.budgets = dict(budgets)
        self.indexes = ProductBlockStore(objects, max_index_bytes=budgets['max_output_bytes'])

    def request(self, thread_id, parent_ref):
        metadata = index_source_metadata(self.threads, thread_id, parent_ref,
                                         max_bytes=self.budgets['max_input_bytes'])
        job_id = self.jobs.request(metadata['ref'], parser_id=parser_identity(),
                                   max_attempts=self.budgets['max_attempts'])
        return self.status(thread_id, job_id)

    def status(self, thread_id, job_id):
        row = self.jobs.status(thread_id, job_id)
        return {'schema': 'capstone-product-index-job/1', 'job_id': row['job_id'],
                'parent_ref': row['parent_ref'], 'state': row['state'], 'error': row['error']}

    def run_once(self, worker_id):
        def read(ref, limit):
            return read_index_source(self.threads, self.objects, ref['thread_id'], ref, max_bytes=limit)
        return run_index_once(self.jobs, self.indexes, read, worker_id=worker_id,
            lease_seconds=self.budgets['lease_seconds'], max_input_bytes=self.budgets['max_input_bytes'],
            max_blocks=self.budgets['max_blocks'], parser_limits={key:self.budgets[key] for key in
                ('wall_seconds','cpu_seconds','max_rss_bytes','max_output_bytes')})

    def resolve_selection(self, thread_id, selection):
        """Resolve an admitted index and exact source; caller authorizes Thread access."""
        from .product_block_identity import selection_identity
        from .product_blocks import resolve_block, resolve_dependencies
        identity = selection_identity(selection)
        parent = selection['parent_ref']
        if parent['thread_id'] != thread_id:
            raise ValueError('selection is outside the authorized scope')
        row = self.jobs.published(thread_id, selection['index_ref'], parent)
        index = self.indexes.read(thread_id, row['receipt'])
        if (index['parent_ref'] != parent or index['index_ref'] != selection['index_ref']
                or index['parser_id'] != row['parser_id']):
            raise ValueError('selection index identity mismatch')
        content = read_index_source(self.threads, self.objects, thread_id, parent,
                                    max_bytes=self.budgets['max_input_bytes'])
        metadata = index_source_metadata(self.threads, thread_id, parent,
                                         max_bytes=self.budgets['max_input_bytes'])
        args = (index, content, selection['block_id'], selection['content_digest'])
        return {'selection_id': identity, 'entry': metadata['entry'],
                'original_size': len(content), 'content': resolve_block(*args),
                'dependencies': resolve_dependencies(*args)}

    def blocks(self, thread_id, job_id, *, offset, limit):
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= limits.product_page_items:
            raise ValueError('invalid block page')
        row = self.jobs.status(thread_id, job_id)
        if row['state'] != 'ready':
            raise ValueError('index is not ready')
        index = self.indexes.read(thread_id, row['receipt'])
        if index['parent_ref'] != row['parent_ref'] or index['parser_id'] != row['parser_id']:
            raise ValueError('index job identity mismatch')
        if offset > len(index['blocks']):
            raise ValueError('block page outside index')
        page = index['blocks'][offset:offset+limit]
        next_offset = offset+len(page)
        return {'schema': 'capstone-product-block-page/1', 'job_id': job_id,
                'index_ref': index['index_ref'], 'parent_ref': index['parent_ref'],
                'blocks': page, 'limitations': index['limitations'],
                'next_offset': next_offset if next_offset < len(index['blocks']) else None}
