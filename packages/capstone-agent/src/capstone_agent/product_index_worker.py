"""Single application index job, with lease checks at each publication boundary.

The host supplies an authorized bounded reader. Production wiring must also
provide process-level memory/time limits; this function is not a daemon or a
hard-timeout sandbox. A slow stage can lose its lease but cannot publish later.
"""
from .product_blocks import build_index


def run_index_once(jobs, objects, read_source, *, worker_id, lease_seconds,
                   max_input_bytes, max_blocks):
    for limit in (lease_seconds, max_input_bytes, max_blocks):
        if type(limit) is not int or limit < 1:
            raise ValueError('invalid index worker budget')
    claim = jobs.claim(worker_id, lease_seconds=lease_seconds)
    if claim is None:
        return 'idle'
    identity = (claim['job_id'], claim['generation'], worker_id)

    def current():
        return jobs.renew(*identity, lease_seconds=lease_seconds)

    phase = 'source_read'
    try:
        content = read_source(claim['parent_ref'], max_input_bytes)
        if not current():
            return 'lease_lost'
        phase = 'source_parse'
        index = build_index(claim['parent_ref'], content,
                            max_input_bytes=max_input_bytes, max_blocks=max_blocks)
        if index['parser_id'] != claim['parser_id']:
            raise ValueError('index parser version changed')
        if not current():
            return 'lease_lost'
        phase = 'object_publish'
        receipt = objects.publish(index)
    except Exception:
        # Store only a bounded phase code. Source content, URLs and credentials
        # in provider exception messages must not enter public job records.
        accepted = jobs.finish(*identity, error=phase + '_failed')
        return 'failed' if accepted else 'lease_lost'
    # finish rechecks lease expiry and generation after object readback. A losing
    # worker can leave an unreferenced blob; it cannot make the ledger ready.
    return 'ready' if jobs.finish(*identity, receipt=receipt) else 'lease_lost'
