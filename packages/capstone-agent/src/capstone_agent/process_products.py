"""Instruction products projected from the existing durable execution ledger.

No task delivery is inferred from an answer or a successful tool call. Raw
diagnostics remain available through the separate attempt-records endpoint.
"""
import re

TERMINAL_TYPES = {'attempt_completed', 'attempt_failed', 'attempt_cancelled', 'attempt_interrupted'}


def process_product_page(service, thread_id, *, before=None, limit=32):
    history = service.read_history(thread_id, before=before, limit=limit)
    products = []
    for event in reversed(history['events']):
        if event['event_type'] not in TERMINAL_TYPES or not event.get('attempt_id'):
            continue
        attempt_id = event['attempt_id']
        records = service.read_attempt_records(thread_id, attempt_id, limit=1, observations_only=True)
        payload = event['payload']
        failure = payload.get('error_code')
        # Only public machine codes belong in this overview, never raw errors.
        failure = failure if isinstance(failure, str) and re.fullmatch(r'[a-z][a-z0-9_]{0,127}', failure) else None
        products.append({
            'product_id': 'process_' + attempt_id, 'scope': 'instruction',
            'thread_id': thread_id, 'run_id': event['run_id'],
            'work_id': payload.get('work_id'), 'turn_id': event.get('turn_id'),
            'attempt_id': attempt_id, 'event_seq': event['event_seq'],
            'status': event['event_type'].removeprefix('attempt_'),
            'instruction': records['instruction'][:2000],
            'instruction_truncated': len(records['instruction']) > 2000,
            'model_context': records['model_context'],
            'occurred_at': event['occurred_at'], 'failure_code': failure,
            # These identify historical records, not current-run evidence grants.
            'historical_only': True,
        })
    return {'schema': 'capstone-process-products/1', 'thread_id': thread_id,
            'products': products, 'has_more': history['has_more'],
            'next_before_event_seq': history['next_before_event_seq']}
