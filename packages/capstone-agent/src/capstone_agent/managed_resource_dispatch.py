"""Protected executor dispatch; caller identity is application-owned."""
import re
from .resource_permissions import ResourcePrincipal, ResourcePermissionDenied
from .managed_resources import ResourceConflict, ResourceStateError
from .managed_resource_mcp import ManagedMcpError


def dispatch_resource_request(service, request):
    if not isinstance(request, dict) or set(request) != {'workspace', 'operation', 'document'}:
        return {'ok': False, 'kind': 'input', 'code': 'resource_request_fields_invalid'}
    workspace = request['workspace']
    from .workspace_scope import workspace_name
    try:
        if workspace_name(workspace) != workspace:
            raise ValueError('resource_workspace_invalid')
    except ValueError:
        return {'ok': False, 'kind': 'input', 'code': 'resource_workspace_invalid'}
    # This endpoint requires the executor control token. No model-supplied roles.
    principal = ResourcePrincipal('workspace:' + workspace, ())
    try:
        return {'ok': True, 'result': service.invoke(principal, workspace, request['operation'], request['document'])}
    except ManagedMcpError as error:
        return {'ok':False,'kind':'runtime','code':str(error),'stage':error.stage,'executed':error.executed}
    except (ResourcePermissionDenied, ResourceConflict, ResourceStateError, KeyError, ValueError) as error:
        kind = ('permission' if isinstance(error, ResourcePermissionDenied) else
                'conflict' if isinstance(error, ResourceConflict) else
                'state' if isinstance(error, ResourceStateError) else
                'missing' if isinstance(error, KeyError) else 'input')
        code = str(error).strip("'")
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,95}', code):
            code = 'resource_request_rejected'
        return {'ok': False, 'kind': kind, 'code': code}
