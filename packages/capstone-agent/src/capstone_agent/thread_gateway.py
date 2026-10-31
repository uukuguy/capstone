"""Application-owned, durable conversation gateway identity."""
from contextvars import ContextVar
from copy import deepcopy

admission_gateway = ContextVar('thread_gateway_publication', default=None)


def publication_binding(publication, *, locked=False):
    from .thread_input_catalog import public_gateway_identity
    publication = publication or {}
    instance = publication.get('identity', {}).get('instance_id')
    connection = publication.get('connection_id')
    return {'connection_id': connection, 'instance_id': instance, 'locked': locked,
            'identity': public_gateway_identity(publication) or {}}


def historical_binding(submission):
    publication = (submission or {}).get('_native_execution', {}).get('capability', {}).get('data_gateway', {})
    return publication_binding(publication, locked=True)


def prepare_admission(binding, saved, publication):
    """Keep a locked identity; update only its future tool publication."""
    publication = deepcopy(publication or {})
    selected = publication_binding(publication, locked=True)
    if saved and saved.get('locked'):
        if saved.get('instance_id') != selected['instance_id']:
            return None, saved, 'gateway_instance_changed'
        if saved.get('connection_id') and saved['connection_id'] != selected['connection_id']:
            return None, saved, 'gateway_instance_changed'
        selected = {**saved, 'connection_id': saved.get('connection_id') or selected['connection_id']}
    elif saved and saved.get('connection_id') != selected['connection_id']:
        return None, saved, 'gateway_instance_changed'
    value = deepcopy(binding)
    if value is not None:
        publication['session_binding'] = selected
        value['capability']['data_gateway'] = publication
    return value, selected, None


class ThreadGatewayOwner:
    def submit_gateway_command(self, command, publication):
        token = admission_gateway.set(publication)
        try:
            return self.submit_command(command)
        finally:
            admission_gateway.reset(token)

    def gateway_admission(self, saved):
        publication = admission_gateway.get()
        if publication is None:
            publication = (self._native_binding or {}).get('capability', {}).get('data_gateway', {})
        return prepare_admission(self._native_binding, saved, publication)
