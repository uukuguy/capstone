from pathlib import Path


def test_native_image_stages_neutral_scheduler_and_receipt_validator():
    root = Path(__file__).resolve().parents[2]
    text = (root / 'deploy/general-pi.Dockerfile').read_text()
    instructions = [line.split() for line in text.replace('\\\n', ' ').splitlines() if line.startswith('COPY ')]
    for source, target in [
        ('packages/capability-agent-kernel/src/capability_agent/runtime/execution_queue.py', 'capability_agent/runtime/execution_queue.py'),
        ('packages/capstone-agent/src/capstone_agent/tool_execution_receipt.py', 'capstone_agent/tool_execution_receipt.py')]:
        assert any(source in parts[1:-1] and (parts[-1] == target
                   or parts[-1].endswith('/') and target == parts[-1] + Path(source).name)
                   for parts in instructions)


def test_local_owner_control_records_use_existing_persistent_worker_volume():
    root = Path(__file__).resolve().parents[2]
    worker = (root / 'compose.yaml').read_text().split('\n  worker:\n', 1)[1].split('\n  worker-pypsa:', 1)[0]
    assert 'worker-runs:/app/runs' in worker
    assert 'CAPSTONE_DOMAIN_EXECUTION_RECEIPTS_ROOT: /app/runs/domain-control' in worker
