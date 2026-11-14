"""Single application index job, with lease checks at each publication boundary.

The host supplies an authorized bounded reader and explicit parser budgets.
Parsing runs in a disposable child. Production memory cgroups and reader I/O
deadlines remain host responsibilities; a slow stage cannot publish after expiry.
"""
import math

from .product_index_process import parse_isolated


def run_index_once(jobs, objects, read_source, *, worker_id, lease_seconds,
                   max_input_bytes, max_blocks, parser_limits):
    for limit in (lease_seconds, max_input_bytes, max_blocks):
        if type(limit) is not int or limit < 1:
            raise ValueError('invalid index worker budget')
    fields = {'wall_seconds', 'cpu_seconds', 'max_rss_bytes', 'max_output_bytes'}
    if not isinstance(parser_limits, dict) or set(parser_limits) != fields:
        raise ValueError('explicit parser budgets required')
    for field in fields - {'wall_seconds'}:
        if type(parser_limits[field]) is not int or parser_limits[field] < 1:
            raise ValueError('invalid parser budget')
    wall = parser_limits['wall_seconds']
    if type(wall) not in (int, float) or not math.isfinite(wall) or not 0 < wall < lease_seconds:
        raise ValueError('parser deadline must fit inside the lease')
    if parser_limits['max_output_bytes'] > objects.max_index_bytes:
        raise ValueError('parser output exceeds index store budget')
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
        index = parse_isolated(claim['parent_ref'], content,
            max_input_bytes=max_input_bytes, max_blocks=max_blocks, **parser_limits)
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
