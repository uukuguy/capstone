"""One application resource contract for UI and protected executor adapters."""
from typing import Any, Callable
from .managed_resource_installation import InstallRequest
from .managed_resource_manifest import content_digest
from .resource_permissions import ResourcePrincipal


class ManagedResourceService:
    open_task: Callable
    task_is_open: Callable
    close_task: Callable
    invoke_mcp: Callable[..., dict[str, Any]]
    def __init__(self, store, installer):
        self.store, self.installer = store, installer

    @staticmethod
    def _fields(document, required=(), optional=()):
        if not isinstance(document, dict) or not set(required) <= set(document) or set(document) - set(required) - set(optional):
            raise ValueError('resource_request_fields_invalid')

    def invoke(self, principal: ResourcePrincipal, workspace: str, operation: str, document: dict):
        # Principal comes from authenticated application context, never a public body.
        if not isinstance(principal, ResourcePrincipal):
            raise TypeError('trusted_resource_principal_required')
        if not isinstance(operation,str):
            raise ValueError('resource_operation_unknown')
        from .managed_resource_contract import operation_contracts
        from jsonschema import Draft202012Validator
        contract=operation_contracts().get(operation)
        if contract is not None and not Draft202012Validator(contract).is_valid(document):
            raise ValueError('resource_request_fields_invalid')
        store = self.store
        if operation == 'list':
            self._fields(document)
            memberships = store.preinstall_memberships(principal, workspace)
            entries = [{**item, 'preinstall': memberships.get(item['resource_id'], {'drafts': [], 'published': []})}
                       for item in store.list_resources(principal, workspace)]
            from .application_capacity import limits
            return {'schema': 'capstone-managed-resources/1', 'resources': entries,
                    'operation_contracts':operation_contracts(),
                    'installation_limits': {'package_files':self.installer.max_files,
                        'package_bytes':self.installer.max_bytes,'skill_metadata_bytes':limits.native_context_bytes,
                        'acquisition_seconds':limits.mcp_initialize_seconds},
                    'revision': content_digest(entries),
                    'allowed_actions': store.permissions.allowed_actions(principal, workspace)}
        if operation == 'install':
            self._fields(document, ('request_id', 'resource_id', 'request'), ('expected_version',))
            return self.installer.install(principal, workspace, document['request_id'], document['resource_id'],
                InstallRequest.from_dict(document['request']), document.get('expected_version'))
        if operation == 'operation':
            self._fields(document, ('request_id',))
            return store.operation(principal, workspace, document['request_id'])
        if operation == 'state':
            self._fields(document, ('resource_id', 'enabled', 'expected_version'))
            return store.set_enabled(principal, workspace, document['resource_id'], document['enabled'], document['expected_version'])
        if operation == 'uninstall':
            self._fields(document, ('resource_id', 'expected_version'))
            return store.uninstall(principal, workspace, document['resource_id'], document['expected_version'])
        if operation == 'preinstall_draft':
            self._fields(document, ('profile', 'resource_id', 'include'))
            store.set_preinstall_draft(principal, workspace, document['profile'], document['resource_id'], include=document['include'])
            return store.preinstall_manifest(principal, workspace, document['profile'])
        if operation in {'preinstall_export', 'preinstall_publish'}:
            self._fields(document, ('profile',))
            method = store.preinstall_manifest if operation == 'preinstall_export' else store.publish_preinstall
            return method(principal, workspace, document['profile'])
        if operation == 'preinstall_import':
            self._fields(document, ('manifest',), ('replace',))
            if type(document.get('replace', False)) is not bool:
                raise ValueError('resource_request_fields_invalid')
            return store.import_preinstall_draft(principal, workspace, document['manifest'], replace=document.get('replace', False))
        raise ValueError('resource_operation_unknown')
