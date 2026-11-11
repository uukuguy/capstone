"""Bounded authenticated public adapter for application gateway selection."""
import json
import re
from datetime import datetime
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool

from .pi_delegation import PiHTTPFailure
from .thread_input_catalog import public_gateway_identity


_ERRORS = {
    'gateway_session_locked': (409, '本会话已绑定网关；使用其他实例请新建会话。'),
    'gateway_instance_changed': (409, '网关实例标识已变化；本会话不会自动接用其他实例。'),
    'gateway_bound_instance_unavailable': (503, '本会话绑定的网关实例暂不可用。'),
    'contract_publication_unavailable': (503, '网关契约发布时间暂不可用，请稍后再试。'),
    'gateway_connections_busy': (409, '有任务正在执行，请结束后切换网关。'),
    'gateway_connection_busy': (409, '有任务正在执行，请结束后切换网关。'),
    'gateway_connection_input_invalid': (400, '请检查网关地址、名称和令牌。'),
    'gateway_authentication_failed': (400, '网关认证失败，请检查令牌。'),
    'gateway_connection_duplicate': (400, '该网关地址已在列表中。'),
    'gateway_connection_not_found': (400, '网关不存在，请刷新列表。'),
    'gateway_registry_full': (400, '网关列表已满。'),
    'gateway_timeout': (503, '网关检查超时，请稍后再试。'),
    'gateway_endpoint_rejected': (400, '网关拒绝该地址，请检查服务配置。'),
    'gateway_catalog_invalid': (503, '网关工具目录无效，请检查服务。'),
    'gateway_catalog_unavailable': (503, '网关未提供可用工具目录。'),
    'gateway_transport_failed': (503, '无法连接网关，请检查服务和网络。'),
    'gateway_connection_failed': (503, '无法连接网关，请检查服务和网络。'),
    'gateway_registry_unavailable': (503, '网关配置暂不可用，请稍后再试。'),
    'gateway_registry_closed': (503, '网关服务暂不可用，请稍后再试。'),
    'gateway_connections_unavailable': (503, '网关服务暂不可用，请稍后再试。'),
}


def _failure(code):
    code = code if isinstance(code, str) and code in _ERRORS else 'gateway_connections_unavailable'
    status, message = _ERRORS[code]
    return HTTPException(status, {'code': code, 'message': message})


def _text(value, maximum=256):
    if not isinstance(value, str) or not 0 < len(value) <= maximum or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError()
    return value


def _public_url(value):
    value = _text(value, 2048)
    parsed = urlsplit(value)
    if (parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or '?' in value or '#' in value
            or (parsed.port is not None and not 0 < parsed.port <= 65535)):
        raise ValueError()
    return value


def _identity(value):
    if not isinstance(value, dict):
        raise ValueError()
    return public_gateway_identity({'available': value.get('available') is True, 'identity': value})


def _snapshot(value):
    if (not isinstance(value, dict) or value.get('schema') != 'capstone-gateway-connections/1'
            or type(value.get('revision')) is not int or value['revision'] < 0
            or type(value.get('checking')) is not bool or not isinstance(value.get('entries'), list)
            or len(value['entries']) > 128):
        raise ValueError()
    entries, ids = [], set()
    for item in value['entries']:
        if not isinstance(item, dict):
            raise ValueError()
        identifier = _text(item.get('id'), 128)
        if not re.fullmatch(r'[A-Za-z0-9_.:-]+', identifier) or identifier in ids:
            raise ValueError()
        ids.add(identifier)
        status = item.get('status')
        if status not in {'unknown', 'checking', 'connected', 'disconnected'}:
            raise ValueError()
        entry = {'id': identifier, 'label': _text(item.get('label')), 'url': _public_url(item.get('url')), 'status': status}
        if 'identity' in item:
            entry['identity'] = _identity(item['identity'])
        if 'checked_at' in item:
            checked_at = _text(item['checked_at'], 64)
            if datetime.fromisoformat(checked_at.replace('Z', '+00:00')).tzinfo is None:
                raise ValueError()
            entry['checked_at'] = checked_at
        if 'error' in item:
            entry['error'] = item['error'] if isinstance(item['error'], str) and item['error'] in _ERRORS else 'gateway_connections_unavailable'
        if 'contract' in item:
            contract = item['contract']
            if not isinstance(contract, dict) or type(contract.get('available')) is not bool:
                raise ValueError()
            entry['contract'] = {'available': contract['available'],
                'revision': _text(contract.get('revision'), 128),
                'checked_at': _text(contract.get('checked_at'), 64)}
            if not contract['available']:
                entry['contract']['reason'] = contract.get('reason') if contract.get('reason') in _ERRORS else 'gateway_connections_unavailable'
                if contract.get('request_id') is not None:
                    entry['contract']['request_id'] = _text(contract['request_id'])
        entries.append(entry)
    result = {'schema': value['schema'], 'revision': value['revision'], 'checking': value['checking'], 'entries': entries}
    if 'selected_id' in value:
        if not isinstance(value['selected_id'], str) or value['selected_id'] not in ids:
            raise ValueError()
        result['selected_id'] = value['selected_id']
    return result


def register_gateway_connection_routes(app, *, executor_provider, authorize, thread_service=None):
    async def invoke(action=None, document=None):
        try:
            def native():
                executor = executor_provider()
                return (executor.gateway_connections() if action is None else
                        executor.control_gateway_connections(action, document))
            value = await run_in_threadpool(native)
            if action == 'probe':
                if not isinstance(value, dict):
                    raise ValueError()
                return {'url': _public_url(value.get('url')), 'identity': _identity(value.get('identity'))}
            return _snapshot(value)
        except PiHTTPFailure as error:
            raise _failure(error.diagnostic.get('protocol_code')) from None
        except Exception:
            raise _failure('gateway_connections_unavailable') from None

    async def body(request, action):
        data = bytearray()
        async for part in request.stream():
            if len(data) + len(part) > 16384:
                raise _failure('gateway_connection_input_invalid')
            data.extend(part)
        try:
            value = json.loads(data)
            allowed = set() if action in {'refresh', 'reload'} else {'id'} if action == 'select' else {'url', 'token', 'name'}
            required = set() if action in {'refresh', 'reload'} else {'id'} if action == 'select' else {'url'}
            if not isinstance(value, dict) or set(value) - allowed or not required <= set(value):
                raise ValueError()
            for key, item in value.items():
                maximum = {'id': 128, 'url': 2048, 'token': 8192, 'name': 256}[key]
                if not isinstance(item, str) or len(item) > maximum or (key != 'token' and not item):
                    raise ValueError()
            return value
        except (ValueError, UnicodeError):
            raise _failure('gateway_connection_input_invalid') from None

    @app.get('/api/v1/workspace/gateways')
    async def get_gateways(request: Request):
        authorize(request)
        return await invoke()

    # Static routes keep unsupported operations outside the control surface.
    def register(action):
        async def control(request: Request):
            authorize(request)
            return await invoke(action, await body(request, action))
        app.add_api_route('/api/v1/workspace/gateways/' + action, control, methods=['POST'],
                          name='gateway_connections_' + action)

    for action in ('refresh', 'reload', 'probe', 'add', 'select'):
        register(action)

    if thread_service is None:
        return

    def session_snapshot(thread_id, *, refresh=False):
        saved = thread_service.read_thread_gateway(thread_id)
        executor = executor_provider()
        value = _snapshot(executor.gateway_connections())
        # A plain read of a new session uses the registered selection. A live
        # contract reload belongs to an explicit refresh, so one unreachable
        # selected gateway cannot hide the known label and address.
        publication = None
        if saved is not None or refresh:
            try:
                publication = executor.thread_gateway_publication(saved, refresh=refresh)
            except PiHTTPFailure:
                if refresh or not saved:
                    raise
                publication = {'available': False, 'connection_id': saved.get('connection_id'),
                               'identity': saved.get('identity', {'instance_id': saved.get('instance_id')})}
        if publication is not None:
            selected = publication.get('connection_id')
            value.pop('selected_id', None)
            if selected is not None:
                value['selected_id'] = selected
                for item in value['entries']:
                    if item['id'] == selected:
                        item['identity'] = _identity({**publication['identity'], 'available': publication.get('available') is True})
                        if not publication.get('available'):
                            item.update(status='disconnected', error='gateway_bound_instance_unavailable')
        value['locked'] = False
        if saved and saved.get('identity'):
            value['bound_instance'] = _identity(saved['identity'])
        return value

    @app.get('/api/v1/threads/{thread_id}/gateways')
    async def get_thread_gateways(thread_id: str, request: Request):
        authorize(request)
        try:
            return await run_in_threadpool(session_snapshot, thread_id)
        except PiHTTPFailure as error:
            raise _failure(error.diagnostic.get('protocol_code')) from None

    @app.post('/api/v1/threads/{thread_id}/gateways/select')
    async def select_thread_gateway(thread_id: str, request: Request):
        authorize(request)
        document = await body(request, 'select')
        def select():
            from .thread_gateway import publication_binding
            from .thread_protocol import ThreadProtocolError
            executor = executor_provider()
            publication = executor.thread_gateway_publication({'connection_id': document['id'], 'locked': False}, refresh=True)
            # The sidebar switch is the registered choice a later new session
            # reads. Persist it before this conversation is bound, so a busy
            # registry leaves both this conversation and the default unchanged.
            executor.control_gateway_connections('select', {'id': document['id']})
            try:
                thread_service.select_thread_gateway(thread_id, publication_binding(publication))
            except ThreadProtocolError:
                raise _failure('gateway_session_locked') from None
            return session_snapshot(thread_id)
        try:
            return await run_in_threadpool(select)
        except PiHTTPFailure as error:
            raise _failure(error.diagnostic.get('protocol_code')) from None

    @app.post('/api/v1/threads/{thread_id}/gateways/refresh')
    @app.post('/api/v1/threads/{thread_id}/gateways/reload')
    async def reload_thread_gateway(thread_id: str, request: Request):
        authorize(request)
        await body(request, 'reload')
        try:
            return await run_in_threadpool(session_snapshot, thread_id, refresh=True)
        except PiHTTPFailure as error:
            raise _failure(error.diagnostic.get('protocol_code')) from None
