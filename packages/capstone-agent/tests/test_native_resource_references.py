import base64
from hashlib import sha256
import json
import os

import pytest

from capstone_agent.native_resource_references import NativeResourceReferences
from capstone_agent.native_resource_staging import NativeResourceStaging


def resource(data=b'original bytes', char='a'):
    return {'schema':'capstone-resource/1','thread_id':'thr_test','resource_id':'resource_'+char*32,
            'version':1,'file_name':'data.csv','size_bytes':len(data),'sha256':sha256(data).hexdigest()}


def setup(tmp_path):
    staging=NativeResourceStaging(tmp_path/'staging')
    inputs=tmp_path/'inputs';inputs.mkdir()
    manifest=resource()
    port=NativeResourceReferences(tmp_path/'port',inputs, 'task', [manifest],staging,os.getuid(),os.getgid())
    return port,staging,manifest


def request(port,manifest,key='1'*64):
    (port.root/'requests'/f'{key}.json').write_text(json.dumps({'resource_id':manifest['resource_id']}))
    return port.root/'responses'/f'{key}.json'


def test_reference_catalog_starts_without_reading_or_staging_any_file(tmp_path):
    port,staging,manifest=setup(tmp_path)
    assert port.pending()==[]
    assert list(staging.root.iterdir())==[]
    assert list(port.inputs.iterdir())==[]


def test_unavailable_selected_resource_returns_a_local_error_instead_of_pending_forever(tmp_path):
    port,staging,manifest=setup(tmp_path)
    receipt=request(port,manifest)
    staging.control({'task_id':'task','resource':manifest,'operation':'unavailable'})
    assert port.pending()==[]
    assert json.loads(receipt.read_text())=={'ok':False,'error':'resource_unavailable'}


def test_only_requested_exact_resource_is_materialized_and_receipted(tmp_path):
    port,staging,manifest=setup(tmp_path)
    receipt=request(port,manifest)
    assert port.pending()==[manifest]
    assert not receipt.exists()
    args={'task_id':'task','resource':manifest}
    staging.control({**args,'operation':'part','index':0,'content_base64':base64.b64encode(b'original bytes').decode()})
    staging.control({**args,'operation':'complete'})
    assert port.pending()==[]
    result=json.loads(receipt.read_text())
    assert result['ok'] is True and result['resource']==manifest
    from pathlib import Path
    target=Path(result['path'])
    assert target.read_bytes()==b'original bytes'
    assert target.is_relative_to(port.inputs)
    assert target.stat().st_mode&0o222==0
    original=target.stat().st_ino
    second=request(port,manifest,'2'*64);assert port.pending()==[]
    assert json.loads(second.read_text())['path']==str(target)
    assert target.stat().st_ino==original


@pytest.mark.parametrize('change',[{'resource_id':'resource_'+'b'*32},{'resource_id':'resource_'+'a'*32,'path':'/etc/passwd'}])
def test_reference_request_cannot_expand_the_frozen_grant(tmp_path,change):
    port,staging,manifest=setup(tmp_path)
    path=port.root/'requests'/('1'*64+'.json');path.write_text(json.dumps(change))
    assert port.pending()==[]
    result=json.loads((port.root/'responses'/path.name).read_text())
    assert result=={'ok':False,'error':'resource_not_admitted'}
    assert list(staging.root.iterdir())==[]


@pytest.mark.parametrize('unavailable', [False, True])
def test_worker_starts_with_references_then_reads_only_requested_resource(monkeypatch, unavailable):
    import time
    from types import SimpleNamespace
    from capstone_agent.pi_delegation import HttpGeneralPiExecutor,PiTaskResult
    from capstone_agent.request_intent import NodeControl
    executor=HttpGeneralPiExecutor('http://localhost:1',identity={'engine':'fixture'},capability={})
    first,unused=resource(),resource(b'unrelated','b');reads=[];polls=0;receipts=[]
    request=SimpleNamespace(task_id='task',parent_attempt_id='attempt',executor_identity=executor.identity,
        timeout_seconds=2,research_binding=None,native_context={'resource_manifests':[first,unused]},
        to_document=lambda:{'task_id':'task'})
    def call(method,path,**kwargs):
        nonlocal polls
        if method=='POST':
            if path.endswith('/inputs'):
                receipts.append(kwargs)
                return {}
            assert path=='/tasks' and reads==[]
            return {'task_id':'task'}
        polls+=1
        return {'status':'running' if polls==1 else 'completed','events':[],
                'result':None if polls==1 else {},**({'resource_requests':[first]} if polls==1 else {})}
    executor._call=call
    executor.stage_resources=lambda task,refs,reader,*args,**kwargs:[b''.join(reader(item)) for item in refs]
    monkeypatch.setattr(PiTaskResult,'from_document',lambda *args:SimpleNamespace(status='completed'))
    def reader(item):
        reads.append(item)
        if unavailable:
            from capstone_agent.continuation_resources import ContinuationResourceUnavailable
            raise ContinuationResourceUnavailable('historical resource reference is unavailable')
        yield b'original bytes'
    executor.execute_with_resource_references(request,NodeControl(lambda:None,time.monotonic()+2),lambda _:None,reader)
    assert reads==[first] and polls==2
    assert len(receipts) == int(unavailable)
