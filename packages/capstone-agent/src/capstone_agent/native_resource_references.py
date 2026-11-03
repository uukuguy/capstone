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
    def __init__(self, root, inputs, task_id, resources, staging, uid, gid):
        self.root,self.inputs,self.task_id=Path(root),Path(inputs),task_id
        self.resources={item['resource_id']:checked_resource(dict(item)) for item in resources}
        self.staging,self.uid,self.gid=staging,uid,gid
        self.materialized={}
        self.root.parent.mkdir(parents=True,exist_ok=True)
        self.root.parent.chmod(0o711)
        self.root.mkdir(mode=0o750)
        os.chown(self.root,0 if os.getuid()==0 else os.getuid(),gid)
        for name in ('requests','responses'):
            path=self.root/name;path.mkdir(mode=0o700 if name=='requests' else 0o750)
            os.chown(path,uid if name=='requests' else os.getuid(),gid)

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
