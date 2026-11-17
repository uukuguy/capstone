"""Pure instruction transitions; callers own durable transactions and lease checks."""
from copy import deepcopy


def submit(queue, identity, text, attempt_id):
    if any(not isinstance(value, str) or not value.strip()
           for value in (identity, text, attempt_id)):
        raise ValueError('Instruction identity, text and attempt are required')
    previous = next((item for item in queue if item['id'] == identity), None)
    if previous is not None:
        if previous['text'] != text or previous['attempt_id'] != attempt_id:
            raise ValueError('Instruction identity was reused with different content')
        return deepcopy(queue)
    result = deepcopy(queue)
    result.append(dict(id=identity, text=text, attempt_id=attempt_id,
                       sequence=max((item['sequence'] for item in queue), default=0) + 1,
                       state='pending'))
    return result


def withdraw(queue, identity):
    result = deepcopy(queue)
    item = next((item for item in result if item['id'] == identity), None)
    if item is None:
        raise ValueError('Instruction not found')
    if item['state'] == 'admitted':
        raise ValueError('Instruction already admitted')
    item['state'] = 'withdrawn'
    return result


def admit(queue, attempt_id, lease_token, *, stopped=False):
    if not isinstance(lease_token, str) or not lease_token:
        raise ValueError('A checked execution lease is required')
    result = deepcopy(queue)
    if stopped:
        return result, None
    item = next((item for item in result
                 if item['attempt_id'] == attempt_id and item['state'] == 'pending'), None)
    if item is None:
        return result, None
    # Lease secrets remain execution-owner state, never public Work projections.
    item.update(state='admitted')
    return result, deepcopy(item)
