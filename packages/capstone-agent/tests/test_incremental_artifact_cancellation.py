import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock
from hashlib import sha256

from capstone_agent.incremental_artifacts import IncrementalArtifacts
from capstone_agent.pi_delegation import PiTaskRequest


def request():
    return PiTaskRequest('task_cancel', 'attempt_files', 'direct', 'Report', (), (), {'engine':'pi'}, 10)


def test_capture_close_is_bounded_and_a_blocked_scan_cannot_later_commit(tmp_path, monkeypatch):
    import capstone_agent.incremental_artifacts as module
    entered, release, closed = threading.Event(), threading.Event(), threading.Event()
    def scan(*args, **kwargs):
        entered.set();release.wait(2)
        return [{'artifact_id':'late','metadata':{'path':'report.md'}}]
    monkeypatch.setattr(module, 'collect_artifacts', scan)
    storage, publish = MagicMock(), MagicMock()
    capture = IncrementalArtifacts(workspace=tmp_path, request=request(), identity={'engine':'pi'}, storage=storage, publish=publish)
    capture.trigger();assert entered.wait(1)
    closing = threading.Thread(target=lambda:(capture.close(),closed.set()), daemon=True);closing.start()
    try:
        assert closed.wait(.3), 'capture close waited for the blocked scanner'
    finally:
        release.set();closing.join(1);capture.thread.join(1)
    storage.capture_artifact.assert_not_called();publish.assert_not_called()


def test_running_transfer_queue_does_not_block_controls_or_retry_a_failed_transfer():
    from capstone_agent.incremental_artifact_transfers import IncrementalArtifactTransfers
    entered, release = threading.Event(), threading.Event()
    attempts, published = [], []
    def transfer(artifact, check):
        attempts.append(artifact['artifact_id']);entered.set();release.wait(2)
        check();published.append(artifact)
    queue = IncrementalArtifactTransfers(transfer, maximum=2)
    started = time.monotonic()
    queue.submit({'artifact_id':'one','host_artifact_id':'file-path-one'})
    assert entered.wait(1)
    queue.submit({'artifact_id':'two','host_artifact_id':'file-other-two'})
    assert time.monotonic()-started < .3
    queue.close()
    release.set();queue.thread.join(1)
    assert attempts == ['one'] and published == []


def test_slow_capture_copy_cannot_lock_terminal_receipts_or_overwrite_them(tmp_path, monkeypatch):
    from capstone_agent.general_pi_storage import GeneralPiStorage
    from capstone_agent.general_pi_executor import collect_artifacts
    workspace = tmp_path / 'work';workspace.mkdir();(workspace/'report.md').write_text('report')
    storage = GeneralPiStorage(tmp_path/'receipts');task=request();storage.save(task.to_document(), None)
    artifact = collect_artifacts(workspace, task.task_id, task.parent_attempt_id)[0]
    entered, release, terminal = threading.Event(), threading.Event(), threading.Event()
    original = storage.artifact_file
    def slow_copy(*args, **kwargs):entered.set();release.wait(2);return original(*args, **kwargs)
    monkeypatch.setattr(storage, 'artifact_file', slow_copy)
    errors=[]
    def capture():
        try:storage.capture_artifact(task.task_id, workspace, artifact)
        except (OSError, ValueError, InterruptedError) as error:errors.append(error)
    copying = threading.Thread(target=capture,daemon=True);copying.start();assert entered.wait(1)
    saved_result={'status':'failed','artifacts':[]}
    saving=threading.Thread(target=lambda:(storage.save(task.to_document(),saved_result),terminal.set()),daemon=True);saving.start()
    try:
        assert terminal.wait(.3), 'a slow capture held the shared receipt lock'
    finally:
        release.set();copying.join(1);saving.join(1)
    assert storage.load(task.task_id)['result'] == saved_result
    assert storage.captured_artifacts(task.task_id) == []


def test_controller_can_process_controls_while_live_read_is_blocked_and_close_prevents_late_put():
    from capstone_agent.delegated_runtime import DelegatedRuntime
    from capstone_agent.request_intent import NodeControl
    from capstone_agent.native_product_roles import file_artifact_id
    from test_native_artifact_projection import claim
    entered, release = threading.Event(), threading.Event()
    def read(*args, **kwargs):entered.set();release.wait(2);return b'report'
    runtime = object.__new__(DelegatedRuntime)
    runtime._claim, runtime._executor = claim(), SimpleNamespace(read_artifact=read)
    runtime._artifact_store = MagicMock();runtime._artifact_store.get.side_effect = KeyError('not retained')
    runtime.runtime_mode='capstone'
    published, controls = [], []
    control = NodeControl(lambda:controls.append('checkpoint'), time.monotonic()+10)
    queue = runtime._incremental_artifact_transfers(published.append, control)
    task = request();digest=sha256(b'report').hexdigest()
    event={'type':'native_artifact_captured','schema':'capstone-pi-artifact-capture/1',
        'task_id':task.task_id,'parent_attempt_id':task.parent_attempt_id,'executor_identity':{'engine':'pi'},
        'artifact':{'artifact_id':file_artifact_id('report.md',digest),'task_id':task.task_id,
            'parent_attempt_id':task.parent_attempt_id,'kind':'workspace_file',
            'metadata':{'path':'report.md','sha256':digest,'size_bytes':6}}}
    runtime._publish_captured_artifact(event,task,queue)
    assert entered.wait(1)
    started=time.monotonic();control.checkpoint();queue.close()
    assert time.monotonic()-started<.3
    release.set();queue.thread.join(1)
    assert controls and published==[]
    runtime._artifact_store.put.assert_not_called()


def test_live_transfer_transport_failure_is_attempted_once_without_retry():
    from capstone_agent.incremental_artifact_transfers import IncrementalArtifactTransfers
    attempted = threading.Event()
    calls=[]
    def unavailable(*args):calls.append('attempt');attempted.set();raise OSError('unavailable')
    queue=IncrementalArtifactTransfers(unavailable,maximum=2)
    queue.submit({'artifact_id':'one','host_artifact_id':'file-path-one'})
    assert attempted.wait(1)
    queue.close()
    assert calls==['attempt']
