"""Operator review of trusted validation bundles against archived inputs."""

def compare_runtime_receipts(baseline, candidate, *, trusted_revisions):
    """Bind independently verified runtime receipts to one archived input."""
    fields = ('thread_id', 'attempt_id', 'archive_sha256', 'target')
    if (baseline.get('schema') != 'capstone-validation-runtime-receipt/1'
            or candidate.get('schema') != baseline['schema']
            or baseline.get('role') != 'baseline' or candidate.get('role') != 'candidate'
            or baseline.get('revision') not in trusted_revisions
            or candidate.get('revision') not in trusted_revisions
            or any(not baseline.get(key) or baseline.get(key) != candidate.get(key) for key in fields)):
        raise ValueError('Validation runtime receipt mismatch')
    return {
        'schema': 'capstone-validation-cross-runtime-review/1',
        **{key: baseline[key] for key in fields},
        'baseline_revision': baseline['revision'],
        'candidate_revision': candidate['revision'],
        'baseline_bundle_sha256': baseline['bundle_sha256'],
        'candidate_bundle_sha256': candidate['bundle_sha256'],
        'baseline_processors': baseline['processors'],
        'candidate_processors': candidate['processors'],
        'baseline': baseline['decision'],
        'candidate': candidate['decision'],
    }


def reviewed_rule_bytes(review, *, current: bytes, desired: bytes, rollback: bool) -> bytes:
    """Check exact rule bytes before a reviewed source change."""
    from hashlib import sha256

    if review.get('schema') != 'capstone-validation-cross-runtime-review/1':
        raise ValueError('Invalid validation review')
    old = review.get('baseline_bundle_sha256')
    new = review.get('candidate_bundle_sha256')
    expected_current, expected_desired = (new, old) if rollback else (old, new)
    if (sha256(current).hexdigest() != expected_current
            or sha256(desired).hexdigest() != expected_desired):
        raise ValueError('Reviewed validation bundle digest mismatch')
    return desired
