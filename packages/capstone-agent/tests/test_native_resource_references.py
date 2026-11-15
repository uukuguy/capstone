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


def test_range_port_materializes_only_verified_fragment(tmp_path):
    port,staging,manifest=setup(tmp_path)
    req={'schema':'capstone-resource-range-request/1','request_id':'a'*64,
         'resource_id':manifest['resource_id'],'offset':2,'length':3}
    (port.root/'range-requests'/('a'*64+'.json')).write_text(json.dumps(req))
    assert port.pending_ranges()==[req]
    data=b'igi'
    receipt={'schema':'capstone-resource-read/1','read_id':'read_'+'c'*32,'thread_id':'thr_test',
        'attempt_id':'attempt','task_id':'task','request_id':req['request_id'],'resource':manifest,
        'offset':2,'length':3,'sha256':sha256(data).hexdigest(),'preview':{'bytes_read':3,'truncated':False,'status':'text','text':'igi'}}
    port.accept_range({'task_id':'task','request':req,'receipt':receipt,
                       'content_base64':base64.b64encode(data).decode()})
    result=json.loads((port.root/'range-responses'/('a'*64+'.json')).read_text())
    from pathlib import Path
    assert Path(result['path']).read_bytes()==data
    assert Path(result['path']).stat().st_mode&0o222==0
    assert list(staging.root.iterdir())==[]


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


@pytest.mark.parametrize('failure',[None,'unavailable','capacity','debug_capacity','cancelled','persistence'])
def test_worker_polls_ranges_without_whole_file_staging(monkeypatch,failure):
    import time
    from types import SimpleNamespace
    from capstone_agent.pi_delegation import HttpGeneralPiExecutor,PiTaskResult
    from capstone_agent.request_intent import NodeControl
    executor=HttpGeneralPiExecutor('http://localhost:1',identity={'engine':'fixture'},capability={})
    manifest=resource();calls=[];delivered=[];polls=0
    req={'schema':'capstone-resource-range-request/1','request_id':'a'*64,
         'resource_id':manifest['resource_id'],'offset':2,'length':3}
    request=SimpleNamespace(task_id='task',parent_attempt_id='attempt',executor_identity=executor.identity,
        timeout_seconds=2,research_binding=None,native_context={'resource_manifests':[manifest]},
        to_document=lambda:{'task_id':'task'})
    def call(method,path,**kwargs):
        nonlocal polls
        if method=='POST':
            if path=='/range-inputs':delivered.append(kwargs['document']);return {'ok':True}
            return {'task_id':'task'}
        polls+=1
        return {'status':'running' if polls==1 else 'completed','events':[],
            'result':None if polls==1 else {},**({'range_requests':[req]} if polls==1 else {})}
    class Reader:
        def __call__(self,*args):pytest.fail('whole file must not be read')
        def read_range(self,resource,request,control):
            calls.append((resource,request));data=b'igi'
            if failure=='unavailable':
                from capstone_agent.resource_range_contract import ResourceRangeRejected
                raise ResourceRangeRejected('source missing',code='resource_range_unavailable')
            if failure in {'capacity','debug_capacity'}:
                from capstone_agent.application_capacity import CapacityExceeded
                raise CapacityExceeded('resource_read_attempt_bytes',2,1,mode='debug' if failure=='debug_capacity' else 'normal')
            if failure=='cancelled':raise InterruptedError('cancelled')
            if failure=='persistence':raise RuntimeError('required persistence failed')
            return {'content':data,'receipt':{'schema':'capstone-resource-read/1','read_id':'read_'+'c'*32,
                'thread_id':'thr_test','attempt_id':'attempt','task_id':'task','request_id':req['request_id'],
                'resource':manifest,'offset':2,'length':3,'sha256':sha256(data).hexdigest(),'preview':{'bytes_read':3,'truncated':False,'status':'text','text':'igi'}}}
    executor._call=call
    executor.stage_resources=lambda *args,**kwargs:pytest.fail('whole file staging must not run')
    monkeypatch.setattr(PiTaskResult,'from_document',lambda *args:SimpleNamespace(status='completed'))
    if failure in {'debug_capacity','cancelled'}:
        from capstone_agent.application_capacity import CapacityExceeded
        with pytest.raises(CapacityExceeded if failure=='debug_capacity' else InterruptedError):
            executor.execute_with_resource_references(request,NodeControl(lambda:None,time.monotonic()+2),lambda _:None,Reader())
        assert delivered==[]
        return
    if failure=='persistence':
        with pytest.raises(RuntimeError,match='persistence'):
            executor.execute_with_resource_references(request,NodeControl(lambda:None,time.monotonic()+2),lambda _:None,Reader())
        assert delivered==[]
        return
    executor.execute_with_resource_references(request,NodeControl(lambda:None,time.monotonic()+2),lambda _:None,Reader())
    assert calls==[(manifest,req)]
    if failure:
        assert delivered[0]['error']=={'schema':'capstone-resource-range-failure/1',
            'code':'resource_range_unavailable' if failure=='unavailable' else 'resource_range_capacity'}
        assert 'content_base64' not in delivered[0]
    else:assert base64.b64decode(delivered[0]['content_base64'])==b'igi'


@pytest.mark.parametrize('change',[{'task_id':'foreign'},{'content_base64':'YWFh'},
    {'request':{'schema':'capstone-resource-range-request/1','request_id':'b'*64,'resource_id':'resource_'+'a'*32,'offset':2,'length':3}}])
def test_range_reply_rejects_forgery(tmp_path,change):
    port,_,manifest=setup(tmp_path)
    req={'schema':'capstone-resource-range-request/1','request_id':'a'*64,
         'resource_id':manifest['resource_id'],'offset':2,'length':3}
    (port.root/'range-requests'/('a'*64+'.json')).write_text(json.dumps(req));port.pending_ranges()
    doc={'task_id':'task','request':req,'receipt':{'schema':'capstone-resource-read/1','read_id':'read_'+'c'*32,
        'thread_id':'thr_test','attempt_id':'attempt','task_id':'task','request_id':req['request_id'],
        'resource':manifest,'offset':2,'length':3,'sha256':sha256(b'igi').hexdigest(),'preview':{'bytes_read':3,'truncated':False,'status':'text','text':'igi'}},
        'content_base64':base64.b64encode(b'igi').decode()}
    with pytest.raises(ValueError):port.accept_range({**doc,**change})


def test_native_range_rejects_historical_product_grant(tmp_path):
    staging=NativeResourceStaging(tmp_path/'staging');inputs=tmp_path/'inputs';inputs.mkdir()
    manifest=resource()
    port=NativeResourceReferences(tmp_path/'port',inputs,'task',[manifest],staging,os.getuid(),os.getgid(),
        resource_origins=[{'resource_id':manifest['resource_id']}])
    req={'schema':'capstone-resource-range-request/1','request_id':'a'*64,
         'resource_id':manifest['resource_id'],'offset':0,'length':1}
    (port.root/'range-requests'/('a'*64+'.json')).write_text(json.dumps(req))
    with pytest.raises(ValueError,match='bounds'):port.pending_ranges()
    assert list(staging.root.iterdir())==[]


def test_sequential_range_reads_pass_poll_batch_boundary(tmp_path, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr('capstone_agent.native_resource_references.limits',SimpleNamespace(rpc_batch_requests=2))
    port,_,manifest=setup(tmp_path)
    for number in range(5):
        key=f'{number:064x}'
        req={'schema':'capstone-resource-range-request/1','request_id':key,
             'resource_id':manifest['resource_id'],'offset':0,'length':1}
        (port.root/'range-requests'/(key+'.json')).write_text(json.dumps(req))
        assert port.pending_ranges()==[req]
        port.accept_range({'task_id':'task','request':req,'content_base64':'bw==',
            'receipt':{'schema':'capstone-resource-read/1','read_id':'read_'+key[-32:],'thread_id':'thr_test',
             'attempt_id':'attempt','task_id':'task','request_id':key,'resource':manifest,'offset':0,
             'length':1,'sha256':sha256(b'o').hexdigest(),'preview':{'bytes_read':1,'truncated':False,'status':'text','text':'o'}}})


def test_range_receipt_is_published_atomically(tmp_path, monkeypatch):
    from pathlib import Path
    port,_,manifest=setup(tmp_path)
    key='a'*64
    req={'schema':'capstone-resource-range-request/1','request_id':key,
         'resource_id':manifest['resource_id'],'offset':0,'length':1}
    (port.root/'range-requests'/(key+'.json')).write_text(json.dumps(req));port.pending_ranges()
    target=port.root/'range-responses'/(key+'.json')
    original=Path.write_text;observed=[]
    def interrupted_write(path,text,*args,**kwargs):
        if path.parent==target.parent:
            # A concurrent SDK poll can observe the final name at every write boundary.
            original(path,text[:len(text)//2],*args,**kwargs)
            observed.append(json.loads(target.read_text()) if target.exists() else None)
        return original(path,text,*args,**kwargs)
    monkeypatch.setattr(Path,'write_text',interrupted_write)
    port.accept_range({'task_id':'task','request':req,'content_base64':'bw==',
        'receipt':{'schema':'capstone-resource-read/1','read_id':'read_'+'c'*32,'thread_id':'thr_test',
         'attempt_id':'attempt','task_id':'task','request_id':key,'resource':manifest,'offset':0,
         'length':1,'sha256':sha256(b'o').hexdigest(),'preview':{'bytes_read':1,'truncated':False,'status':'text','text':'o'}}})
    assert observed==[None]
    assert json.loads(target.read_text())['ok'] is True


def test_range_failure_is_bounded_local_receipt_without_fragment(tmp_path):
    port,staging,manifest=setup(tmp_path)
    req={'schema':'capstone-resource-range-request/1','request_id':'a'*64,
         'resource_id':manifest['resource_id'],'offset':0,'length':1}
    (port.root/'range-requests'/('a'*64+'.json')).write_text(json.dumps(req));port.pending_ranges()
    document={'task_id':'task','request':req,'error':{'schema':'capstone-resource-range-failure/1','code':'resource_range_unavailable'}}
    assert port.accept_range(document)=={'ok':True}
    result=json.loads((port.root/'range-responses'/('a'*64+'.json')).read_text())
    assert result=={'ok':False,'request_id':'a'*64,'error':document['error']}
    assert port.pending_ranges()==[] and list(port.inputs.iterdir())==[]
    assert list(staging.root.iterdir())==[]


@pytest.mark.parametrize('preview',[
    {'bytes_read':3,'truncated':False,'status':'text','text':'forged'},
    {'bytes_read':3,'truncated':False,'status':'binary','text':None},
    {'bytes_read':True,'truncated':False,'status':'text','text':'igi'},
])
def test_range_preview_must_match_verified_bytes(preview):
    from capstone_agent.native_resource_ranges import checked_reply
    manifest=resource()
    req={'schema':'capstone-resource-range-request/1','request_id':'a'*64,
        'resource_id':manifest['resource_id'],'offset':2,'length':3}
    receipt={'schema':'capstone-resource-read/1','read_id':'read_'+'c'*32,'thread_id':'thr_test',
        'attempt_id':'attempt','task_id':'task','request_id':'a'*64,'resource':manifest,'offset':2,
        'length':3,'sha256':sha256(b'igi').hexdigest(),'preview':preview}
    with pytest.raises(ValueError,match='preview'):
        checked_reply({'receipt':receipt,'content_base64':'aWdp'},req,manifest,'task')
