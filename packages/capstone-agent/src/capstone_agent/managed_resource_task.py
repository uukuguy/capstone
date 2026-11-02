"""Per-call admission of installed resources, bound to one trusted task scope."""
import shutil
import fcntl
import tempfile
import os
from pathlib import Path
from .managed_resource_manifest import content_digest


def resource_task_action(service,principal,workspace,operation,document,*,inputs,deadline=None,task_id=None):
    if operation not in {'discover','call','load_skill'}:
        return service.invoke(principal,workspace,operation,document)
    service._fields(document,('resource_id','version'),('name','arguments','catalog_revision'))
    item=service.store.require_use(principal,workspace,document['resource_id'],document['version'])
    # Future calls may not silently continue on an older workspace binding.
    if service.store.get_resource(principal,workspace,document['resource_id'])['version']!=document['version']:
        raise ValueError('resource_version_changed')
    publication=service.installer.publication(item['digest'])
    admitted_revision=content_digest(service.store.list_resources(principal,workspace))
    if item['kind']=='skill':
        if operation!='load_skill':raise ValueError('resource_operation_kind_invalid')
        package=service.store.root/item['package_ref']
        if service.installer._digest(package)!=('sha256:'+package.name):
            raise ValueError('resource_package_corrupt')
        root=Path(inputs)
        if task_id is None:
            root.mkdir(parents=True,exist_ok=True)
        elif not service.task_is_open(task_id):
            raise ValueError('resource_task_closed')
        # Hold the original directory: cleanup cannot redirect or recreate it.
        descriptor=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        target=root/('managed-'+content_digest([document['resource_id'],document['version']]).split(':')[1])
        private=root.parent/'.managed-materialization'
        private.mkdir(mode=0o700,exist_ok=True)
        try:
            with (private/(target.name+'-'+content_digest(str(root)).split(':')[1]+'.lock')).open('a') as lock:
                os.chmod(lock.name,0o600)
                fcntl.flock(lock,fcntl.LOCK_EX)
                if target.is_symlink():
                    raise ValueError('resource_input_identity_changed')
                if not target.exists():
                    stage=Path(tempfile.mkdtemp(prefix='package-',dir=private))
                    try:
                        shutil.copytree(package,stage,symlinks=True,dirs_exist_ok=True)
                        if service.installer._digest(stage)!='sha256:'+package.name:
                            raise ValueError('resource_input_identity_changed')
                        stage.chmod(0o700)
                        for path in stage.rglob('*'):
                            if not path.is_symlink():
                                path.chmod(0o555 if path.is_dir() or path.stat().st_mode&0o111 else 0o444)
                        if task_id is not None and not service.task_is_open(task_id):
                            raise ValueError('resource_task_closed')
                        os.rename(stage,target.name,dst_dir_fd=descriptor)
                        os.chmod(target.name,0o555,dir_fd=descriptor)
                    finally:
                        if stage.exists():
                            from .native_resources import _remove_unpublished
                            _remove_unpublished(stage)
                if service.installer._digest(target)!='sha256:'+package.name:
                    raise ValueError('resource_input_identity_changed')
        finally:
            os.close(descriptor)
        result={'skills':[{'name':s['name'],'description':s['description'],'path':str(target/s['path'])}
                          for s in publication['skills']]}
        from .managed_resource_dependencies import dependency_environment, runtime_compatibility
        environment=dependency_environment(target,runtime_compatibility())
        if environment:
            result['runtime']={'command':'python3','environment':environment}
    else:
        if operation=='load_skill':raise ValueError('resource_operation_kind_invalid')
        invoke=getattr(service,'invoke_mcp',None)
        if not callable(invoke):raise ValueError('resource_runtime_unavailable')
        call=None
        if operation=='call':
            service._fields(document,('resource_id','version','name','arguments','catalog_revision'))
            call={k:document[k] for k in ('name','arguments','catalog_revision')}
            if call['catalog_revision']!=publication['catalog']['revision']:
                from .managed_resource_mcp import ManagedMcpError
                raise ManagedMcpError('resource_contract_changed',stage='admission',executed=False)
        result=invoke(item,call,deadline=deadline,session_key=task_id,workspace=workspace)
        if operation=='discover' and result.get('revision')!=publication['catalog']['revision']:
            from .managed_resource_mcp import ManagedMcpError
            raise ManagedMcpError('resource_contract_changed',stage='admission',executed=False)
    return {'resource_id':document['resource_id'],'resource_version':item['version'],
            'resource_set_revision':admitted_revision,
            'result':result}
