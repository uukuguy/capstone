import hashlib
import json
import subprocess
import sys
from pathlib import Path


def test_prepare_publication_and_rollback_check_exact_review(tmp_path):
    script = Path(__file__).resolve().parents[1] / 'review_harness_rules.py'
    old, new = b'old bundle', b'new bundle'
    old_file = tmp_path / 'old'
    new_file = tmp_path / 'new'
    receipt = tmp_path / 'review.json'
    old_file.write_bytes(old)
    new_file.write_bytes(new)
    receipt.write_text(json.dumps({
        'schema': 'capstone-validation-cross-runtime-review/1',
        'baseline_bundle_sha256': hashlib.sha256(old).hexdigest(),
        'candidate_bundle_sha256': hashlib.sha256(new).hexdigest(),
    }))
    def run(operation, current, desired, output):
        return subprocess.run([sys.executable, str(script), operation,
                               '--review', str(receipt), '--current', str(current),
                               '--desired', str(desired), '--output', str(output)],
                              capture_output=True, text=True, timeout=10)
    output = tmp_path / 'publish'
    assert run('publish', old_file, new_file, output).returncode == 0
    assert output.read_bytes() == new
    assert run('publish', old_file, new_file, output).returncode != 0
    rollback = tmp_path / 'rollback'
    assert run('rollback', new_file, old_file, rollback).returncode == 0
    assert rollback.read_bytes() == old
    assert run('rollback', old_file, new_file, tmp_path / 'invalid').returncode != 0
    assert not (tmp_path / 'invalid').exists()
