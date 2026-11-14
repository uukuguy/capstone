"""Local selection identity; structural validation grants no source access."""
from hashlib import sha256
import json
import re

from .thread_products import checked_ref


def selection_identity(value: object) -> str:
    """Bind exact parent and block identity for deduplication and material keys.

    Callers must separately authorize and resolve the parent, published index,
    and block bytes. A structurally valid identity is not an admitted selection.
    """
    fields = {'schema', 'parent_ref', 'index_ref', 'block_id', 'content_digest', 'purpose'}
    if (not isinstance(value, dict) or set(value) != fields
            or value['schema'] != 'capstone-local-product-selection/1'
            or value['purpose'] != 'historical-context'):
        raise ValueError('invalid local product selection')
    for field in ('index_ref', 'content_digest'):
        if not isinstance(value[field], str) or not re.fullmatch(r'[a-f0-9]{64}', value[field]):
            raise ValueError('invalid local product digest')
    if (not isinstance(value['block_id'], str)
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}', value['block_id'])):
        raise ValueError('invalid local product block identity')
    document = {**value, 'parent_ref': checked_ref(value['parent_ref'])}
    encoded = json.dumps(document, sort_keys=True, ensure_ascii=False,
                         allow_nan=False, separators=(',', ':')).encode('utf-8')
    return sha256(encoded).hexdigest()
