"""Task-local references. Source bytes are acquired only after an admitted open."""
from hashlib import sha256
from itertools import islice
import json
import os
from pathlib import Path
import re

from .application_capacity import limits
from .resource_manifest import checked_resource
from .native_resource_staging import ResourceUnavailable


class NativeResourceReferences:
    def __init__(self, root, inputs, task_id, resources, staging, uid, gid, attempt_id=None):
        self.root,self.inputs,self.task_id=Path(root),Path(inputs),task_id
        self.resources={item['resource_id']:checked_resource(dict(item)) for item in resources}
        self.staging,self.uid,self.gid=staging,uid,gid
        self.materialized={}
        self.root.parent.mkdir(parents=True,exist_ok=True)
        self.root.parent.chmod(0o711)
        self.root.mkdir(mode=0o750)
        os.chown(self.root,0 if os.getuid()==0 else os.getuid(),gid)
        self.range_pending={}
        self.range_completed={}
        self.attempt_id=attempt_id
        for name in ('requests','responses','range-requests','range-responses'):
            requesting=name.endswith('requests')
            path=self.root/name;path.mkdir(mode=0o700 if requesting else 0o750)
            os.chown(path,uid if requesting else os.getuid(),gid)

    def pending_ranges(self):
        from .native_resource_ranges import checked_request
        result=[]
        for path in islice((self.root/'range-requests').glob('*.json'),limits.rpc_batch_requests):
            if not re.fullmatch(r'[a-f0-9]{64}\.json',path.name):continue
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            with os.fdopen(fd,'rb') as incoming:raw=incoming.read(4097)
            if len(raw)>4096:raise ValueError('range request exceeds bounds')
            request=checked_request(json.loads(raw),self.resources)
            key=request['request_id']
            if path.name!=key+'.json':raise ValueError('range request identity changed')
            previous=self.range_pending.setdefault(key,request)
            if previous!=request:raise ValueError('range request identity changed')
            if key not in self.range_completed:result.append(request)
        return result

    def accept_range(self, document):
        from .native_resource_ranges import checked_request, checked_reply
        if document.get('task_id')!=self.task_id:raise ValueError('range task changed')
        request=checked_request(document['request'],self.resources)
        key=request['request_id']
        if self.range_pending.get(key)!=request:raise ValueError('range request is not pending')
        if key in self.range_completed:
            if self.range_completed[key]!=document:raise ValueError('range response changed')
            return {'ok':True}
        receipt,data=checked_reply(document,request,self.resources[request['resource_id']],self.task_id)
        if self.attempt_id is not None and receipt['attempt_id']!=self.attempt_id:
            raise ValueError('range attempt identity changed')
        directory=self.inputs/'ranges';directory.mkdir(mode=0o750,exist_ok=True)
        if directory.is_symlink() or not directory.is_dir():raise ValueError('range directory changed')
        os.chown(directory,os.getuid(),self.gid)
        target=directory/key
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o440)
        with os.fdopen(fd,'wb') as outgoing:outgoing.write(data)
        os.chown(target,os.getuid(),self.gid)
        result={'ok':True,'receipt':receipt,'path':str(target)}
        response=self.root/'range-responses'/(key+'.json')
        response.write_text(json.dumps(result));os.chown(response,os.getuid(),self.gid);response.chmod(0o440)
        self.range_completed[key]=document
        return {'ok':True}

    def _reply(self, name, result):
        target=self.root/'responses'/name
        temporary=target.with_suffix('.tmp')
        temporary.write_text(json.dumps(result,ensure_ascii=False))
        os.chown(temporary,os.getuid(),self.gid);temporary.chmod(0o440)
        temporary.replace(target)

    def _materialize(self, resource, source):
        key=resource['resource_id']
        if key in self.materialized:return self.materialized[key]
        directory=self.inputs/'resources'/key
        directory.mkdir(parents=True,exist_ok=True)
        for path in (directory.parent,directory):
            os.chown(path,os.getuid(),self.gid);path.chmod(0o750)
        target=directory/resource['file_name'];temporary=directory/'.source.tmp'
        digest,size=sha256(),0
        try:
            with source.open('rb') as incoming,temporary.open('xb') as outgoing:
                while data:=incoming.read(limits.upload_chunk_bytes):
                    size+=len(data)
                    if size>resource['size_bytes']:raise ValueError('resource size changed')
                    digest.update(data);outgoing.write(data)
            if size!=resource['size_bytes'] or digest.hexdigest()!=resource['sha256']:
                raise ValueError('resource content changed')
            os.chown(temporary,os.getuid(),self.gid);temporary.chmod(0o440);temporary.replace(target)
            directory.chmod(0o550)
        finally:
            temporary.unlink(missing_ok=True)
        self.materialized[key]=str(target)
        return str(target)

    def pending(self):
        pending={}
        for path in islice(self.root.joinpath('requests').glob('*.json'),limits.rpc_batch_requests):
            if not re.fullmatch(r'[a-f0-9]{64}\.json',path.name) or (self.root/'responses'/path.name).exists():continue
            try:
                fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
                with os.fdopen(fd,'rb') as incoming:
                    raw=incoming.read(4097)
                if len(raw)>4096:raise ValueError()
                request=json.loads(raw)
                if not isinstance(request,dict) or set(request)!={'resource_id'}:raise ValueError()
                resource=self.resources.get(request['resource_id'])
                if resource is None:raise ValueError()
            except (OSError,ValueError,TypeError,KeyError):
                self._reply(path.name,{'ok':False,'error':'resource_not_admitted'});continue
            try:
                source=self.staging.source(self.task_id,resource)
            except ResourceUnavailable:
                self._reply(path.name,{'ok':False,'error':'resource_unavailable'});continue
            except ValueError:
                pending[resource['resource_id']]=resource;continue
            try:
                target=self._materialize(resource,source)
            except (OSError,ValueError) as error:
                import logging
                from .native_failure_origin import native_failure_origin
                logging.getLogger(__name__).warning('Resource materialization failed; task_id=%s; resource_id=%s; origin=%s',
                    self.task_id, resource['resource_id'], native_failure_origin(error))
                self._reply(path.name,{'ok':False,'error':'resource_unavailable'});continue
            self._reply(path.name,{'ok':True,'resource':resource,'path':target})
        return list(pending.values())
