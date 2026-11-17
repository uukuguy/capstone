from types import SimpleNamespace
import pytest

from capstone_agent.control_host import ControlHost
from capstone_control.service import ControlService
from capstone_control.store import MemoryStore


@pytest.mark.parametrize('mode',['products','answer','unavailable'])
def test_actual_saved_deliveries_are_verified_without_inventing_required_names(monkeypatch,mode):
    from capstone_agent import control_host as module
    monkeypatch.setattr(module,'reconcile',lambda *args,**kwargs:None)
    control=ControlService(MemoryStore())
    mission=control.create_mission('enterprise',dict(schema='capstone-control-mission-create/1',operation_id='create',
        objective='Prepare a useful saved result',origin={'thread_id':'origin_thread'},acceptance_criteria=['Inspect actual saved output']))
    def command(kind,payload,operation):
        current=control.read('enterprise',mission['mission_id'])
        return control.command_mission('enterprise',dict(schema='capstone-control-mission-command/1',operation_id=operation,
            mission_id=mission['mission_id'],expected_revision=current['revision'],kind=kind,payload=payload))
    command('prepare_task',{'task':dict(task_id='task',objective='Prepare output',delivery_requirements=['Save the requested file'],
        depends_on=[],agent_id='capstone',mode='single',max_attempts=1)},'prepare')
    command('ready',{},'ready');command('delegate_next',{},'dispatch')
    task=control.read('enterprise',mission['mission_id'])['tasks'][0]
    product=dict(file_name='actual.md',sha256='a'*64,thread_id='task_thread',attempt_id='task_attempt',artifact_id='artifact_1')
    control.deliver('enterprise',mission['mission_id'],task['delegation']['delegation_id'],
        dict(thread_id='task_thread',work_id='task_work'),dict(answer_ref='saved_answer',products=[product] if mode=='products' else [],status='completed'))
    checked=[]
    host=ControlHost(control,SimpleNamespace(),verify_product=lambda workspace,value:checked.append(value),
        verify_answer=(lambda workspace,binding,ref:checked.append(ref)) if mode=='answer' else None)
    monkeypatch.setattr(host,'command_goal',lambda workspace,document,actor:control.command(workspace,document,actor=actor))
    host.tick()
    current=control.read_mission('enterprise',mission['mission_id'])
    assert current['plan_concluded'] is False
    assert current['state']=='waiting_review'
    if mode=='unavailable':
        assert current['tasks'][0]['state']=='delivered'
        assert current['reason']=='delivery_verification_unavailable'
    else:
        assert current['tasks'][0]['state']=='verified'
        assert checked==([product] if mode=='products' else ['saved_answer'])
