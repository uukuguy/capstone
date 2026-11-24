"""Operator review of trusted validation bundles against archived inputs."""

from .harness_validation import _processor_identity, replay_rule_input


def review_rule_candidate(objects, thread_id, attempt_id, digest, bundle, candidate):
    """Compare installed trusted bundles without modifying the archive."""
    original = replay_rule_input(objects, thread_id, attempt_id, digest, bundle)
    proposed = replay_rule_input(objects, thread_id, attempt_id, digest, bundle, candidate=candidate)
    return {
        'schema': 'capstone-validation-review/1',
        'thread_id': thread_id,
        'attempt_id': attempt_id,
        'archive_sha256': digest,
        'target': bundle.target,
        'original_bundle_sha256': bundle.digest,
        'candidate_bundle_sha256': candidate.digest,
        'original_processors': _processor_identity(bundle),
        'candidate_processors': _processor_identity(candidate),
        'original': {'status': original.status, 'value': original.value},
        'candidate': {'status': proposed.status, 'value': proposed.value},
    }


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


def runtime_receipt(objects, thread_id, attempt_id, digest, bundle, *, role, revision):
    """Run a locally installed bundle and record its exact processor identity."""
    import json
    import re
    from hashlib import sha256

    from .harness_validation import _REPLAY_LIMIT, _replay_key

    if role not in ('baseline', 'candidate') or not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise ValueError('Invalid validation runtime identity')
    body = objects.get(_replay_key(thread_id, attempt_id, digest), _REPLAY_LIMIT)
    if len(body) > _REPLAY_LIMIT or sha256(body).hexdigest() != digest:
        raise ValueError('Validation replay digest mismatch')
    archive = json.loads(body)
    if archive.get('schema') != 'capstone-validation-replay/1' or archive.get('target') != bundle.target:
        raise ValueError('Validation replay target mismatch')
    if role == 'baseline':
        result = replay_rule_input(objects, thread_id, attempt_id, digest, bundle)
    else:
        limit = archive.get('answer_limit')
        accept = None
        if limit is not None:
            accept = lambda value: isinstance(value, str) and bool(value.strip()) and len(value.encode()) <= limit
        result = bundle.pipeline().run(archive['input'], observe=lambda _: None, accept_correction=accept)
    return {
        'schema': 'capstone-validation-runtime-receipt/1',
        'role': role,
        'revision': revision,
        'thread_id': thread_id,
        'attempt_id': attempt_id,
        'archive_sha256': digest,
        'target': bundle.target,
        'bundle_sha256': bundle.digest,
        'processors': _processor_identity(bundle),
        'decision': {'status': result.status, 'value': result.value},
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
