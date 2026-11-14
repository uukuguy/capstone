"""Optional host composition for bounded paragraph indexing."""
import json
import logging
import math
import os
import uuid

from .product_index_jobs import ProductIndexJobs
from .product_index_service import ProductIndexService


def configured_product_indexes(environ, threads, objects):
    raw = environ.get('CAPSTONE_PRODUCT_INDEX_BUDGETS_JSON')
    if raw is None:
        return None
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate index budget')
            result[key] = value
        return result
    try:
        if len(raw) > 4096:
            raise ValueError('index configuration too large')
        budgets = json.loads(raw, object_pairs_hook=unique)
        # Validate before touching the database or object store.
        service = ProductIndexService(threads, objects, None, budgets=budgets)
    except (ValueError, TypeError, RecursionError):
        raise ValueError('invalid product index configuration') from None
    if threads is None or objects is None:
        raise ValueError('product index storage is required')
    jobs = ProductIndexJobs(threads.dsn)
    jobs.initialize()
    service.jobs = jobs
    return service


def serve_product_indexes(service, *, stop_event, poll_seconds=1.0):
    if not math.isfinite(poll_seconds) or poll_seconds <= 0:
        raise ValueError('invalid product index poll interval')
    worker_id = f'product-index-{os.getpid()}-{uuid.uuid4().hex}'
    while not stop_event.is_set():
        try:
            result = service.run_once(worker_id)
        except Exception:
            logging.getLogger(__name__).warning('Product index scheduler operation failed')
            result = 'failed'
        if result != 'ready':
            stop_event.wait(poll_seconds)
