from pathlib import Path


def test_native_image_stages_neutral_scheduler_and_receipt_validator():
    root = Path(__file__).resolve().parents[2]
    text = (root / 'deploy/general-pi.Dockerfile').read_text()
    for source, target in [
        ('packages/capability-agent-kernel/src/capability_agent/runtime/execution_queue.py', 'capability_agent/runtime/execution_queue.py'),
        ('packages/capstone-agent/src/capstone_agent/tool_execution_receipt.py', 'capstone_agent/tool_execution_receipt.py')]:
        assert f'COPY {source} {target}' in text
