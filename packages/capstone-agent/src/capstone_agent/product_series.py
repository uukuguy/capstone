"""Application-owned version membership and explicit adoption transitions.

Persistence owners must authorize and resolve exact product references before
calling this pure transition, then atomically save state and command receipt.
"""
from copy import deepcopy

from .thread_products import checked_ref


def transition(state, *, thread_id, series_id, expected_revision, operation, product):
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValueError('invalid series revision')
    if operation not in {'register', 'adopt', 'clear'}:
        raise ValueError('invalid series operation')
    if not isinstance(series_id, str) or not series_id or len(series_id) > 255:
        raise ValueError('invalid series identity')
    if state is None:
        if operation != 'register':
            raise ValueError('series member registration required')
        current = {'schema': 'capstone-product-series/1', 'thread_id': thread_id,
            'series_id': series_id, 'revision': 0, 'members': [], 'adopted_ref': None}
    else:
        current = deepcopy(state)
        if current['thread_id'] != thread_id or current['series_id'] != series_id:
            raise ValueError('series scope mismatch')
    if current['revision'] != expected_revision:
        raise ValueError('series revision conflict')
    if operation == 'clear':
        if product is not None:
            raise ValueError('clear cannot select a product')
        current['adopted_ref'] = None
    else:
        product = checked_ref(product)
        if product['thread_id'] != thread_id:
            raise ValueError('product scope mismatch')
        if operation == 'register':
            if product in current['members']:
                raise ValueError('product is already a series member')
            current['members'].append(product)
        else:
            if product not in current['members']:
                raise ValueError('product is not a series member')
            current['adopted_ref'] = product
    current['revision'] += 1
    return current
