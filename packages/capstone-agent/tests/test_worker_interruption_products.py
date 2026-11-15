from hashlib import sha256
import time
import pytest

from capstone_agent.artifacts import MemoryObjectStore
from capstone_agent.native_artifact_projection import artifact_object_key, project_native_artifact_capture
from capstone_agent.native_product_roles import file_artifact_id
from capstone_agent.pi_delegation import PiTaskRequest
from capstone_agent.thread_materials import _process_files
from capstone_agent.thread_service import ThreadExecutionError
from test_enterprise_normal_chat import chat_store, native_executor
from test_thread_postgres import postgres_thread_service
from test_thread_work_execution import command


@pytest.mark.parametrize('end', ['expiry', 'explicit'])
def test_interruption_seals_exact_captured_file_for_new_instruction(chat_store, end, monkeypatch):
    store, tid = chat_store
    executor = native_executor();store.set_native_executor(executor)
    objects=MemoryObjectStore();store.set_material_store(objects)
    store.submit_command(command(store,tid,'send_message','start_loss',payload={'text':'Save a draft'}))
    claim=store.claim_attempt('loss-test',60)
    data=b'Incomplete original bytes'
    request=PiTaskRequest('task_loss',claim.attempt.attempt_id,'direct','Save draft',(),(),executor.identity,60)
    artifact={'artifact_id':file_artifact_id('draft.md',sha256(data).hexdigest()),
      'task_id':request.task_id,'parent_attempt_id':request.parent_attempt_id,'kind':'workspace_file',
      'metadata':{'path':'draft.md','sha256':sha256(data).hexdigest(),'size_bytes':len(data)}}
    event={'type':'native_artifact_captured','schema':'capstone-pi-artifact-capture/1',
      'task_id':request.task_id,'parent_attempt_id':request.parent_attempt_id,
      'executor_identity':dict(executor.identity),'artifact':artifact}
    captured=project_native_artifact_capture(claim,request,event)[0]
    objects.put(artifact_object_key(captured),data,'text/markdown')
    store.append_runtime_event(claim,event_type='native_artifact_published',payload={'artifact':captured})
    if end=='expiry':
        if hasattr(store,'_lock'):
            store._attempts[claim.attempt.attempt_id]['lease_deadline']=time.monotonic()-1
        else:
            with store._connect() as c:
                c.execute("UPDATE capstone_thread_attempts SET lease_deadline=clock_timestamp()-interval '1 second' WHERE attempt_id=%s",(claim.attempt.attempt_id,))
            insert=store._insert_event
            def reject_terminal(connection, value):
                if value.event_type=='attempt_interrupted':
                    raise OSError('Simulated terminal persistence failure')
                return insert(connection,value)
            with monkeypatch.context() as patch:
                patch.setattr(store,'_insert_event',reject_terminal)
                with pytest.raises(OSError,match='terminal persistence failure'):
                    store.interrupt_expired_attempts()
            with store._connect() as c:
                assert c.execute('SELECT phase FROM capstone_thread_attempts WHERE attempt_id=%s',
                                 (claim.attempt.attempt_id,)).fetchone()['phase']=='running'
                assert c.execute("SELECT count(*) AS n FROM capstone_thread_events WHERE attempt_id=%s AND event_type='native_artifact_published'",
                                 (claim.attempt.attempt_id,)).fetchone()['n']==1
        assert store.interrupt_expired_attempts()==1
    else:
        store.finish_attempt(claim,phase='interrupted',payload={})
    snapshot=store.snapshot(tid)
    records=store.read_events(tid,0).events
    versions=[e for e in records if e.event_type=='native_artifact_published']
    assert [e.payload['artifact']['source_status'] for e in versions]==['running','incomplete']
    assert versions[1].payload['artifact']=={**captured,'source_status':'incomplete'}
    assert versions[1].event_seq < next(e.event_seq for e in records if e.event_type=='attempt_interrupted')
    assert objects.get(artifact_object_key(captured),len(data))==data
    if hasattr(store,'_lock'):
        files=_process_files(store,snapshot,claim.task_context.binding.work_id,None,None)
    else:
        with store._connect() as connection:
            files=_process_files(store,snapshot,claim.task_context.binding.work_id,None,connection)
    assert files==[{**captured,'source_status':'incomplete'}]
    if hasattr(store,'_lock'):
        with pytest.raises(ThreadExecutionError):
            store.renew_attempt(claim,60)
    else:
        assert not store.renew_attempt(claim,60)
    with pytest.raises(ThreadExecutionError):
        store.append_runtime_event(claim,event_type='late_probe',payload={})
    with pytest.raises(ThreadExecutionError):
        store.finish_attempt(claim,phase='completed',payload={'answer':'Late answer must not commit'})
    assert store.interrupt_expired_attempts()==0
    work=snapshot.works[0]
    receipt=store.submit_command(command(store,tid,'send_message','after_loss',work_id=work['work_id'],
        revision=work['revision'],payload={'text':'Read only the saved draft'}))
    assert receipt.status=='accepted'
    following=store.claim_attempt('recovery-test',60)
    assert following.attempt.attempt_id!=claim.attempt.attempt_id
    assert following.submission['_continuation_artifacts']==[{**captured,'source_status':'incomplete'}]
    from capstone_agent.continuation_resources import resource_reader_for
    resource,=following.submission['_resource_manifests']
    assert b''.join(resource_reader_for(store,following)(resource))==data
