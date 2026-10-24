"""Task catalog grants and host-issued gateway observation receipts."""
from copy import deepcopy
from hashlib import sha256
import re
from threading import RLock

from .application_capacity import limits, require_capacity
from .data_gateway_mcp import GatewayError, encode, fingerprint


def research_gateway_tools(native_context, publication):
    if not native_context or not publication.get('available'):
        return set()
    from .native_task_context import POLICY_TEXT, resolve_research_policy
    text = native_context.get('policy', {}).get('system_policy')
    if text != POLICY_TEXT and resolve_research_policy(text) is None:
        return set()
    return set(publication['catalog']['tools'])


class DataGatewayAccess:
    def __init__(self, client, catalog):
        self.client, self.catalog = client, deepcopy(catalog)
        self._tasks = {}
        self._lock = RLock()

    def publication(self):
        return {'available': True, 'catalog': deepcopy(self.catalog)}

    def bind(self, task_id, attempt_id):
        with self._lock:
            if task_id in self._tasks:
                raise GatewayError('gateway_task_already_bound')
            self._tasks[task_id] = {'attempt_id': attempt_id, 'started': set(), 'issued': {}}

    def revoke(self, task_id):
        with self._lock:
            self._tasks.pop(task_id, None)

    async def call(self, task_id, document):
        if (not isinstance(document, dict) or set(document) != {'call_id', 'name', 'arguments'}
                or not isinstance(document.get('call_id'), str)
                or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,256}', document['call_id'])
                or not isinstance(document.get('name'), str)
                or document['name'] not in self.catalog['tools']
                or not isinstance(document['arguments'], dict)):
            raise GatewayError('gateway_request_invalid')
        call_id, name = document['call_id'], document['name']
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                raise GatewayError('gateway_task_not_admitted')
            if call_id in record['started']:
                raise GatewayError('gateway_call_already_started')
            require_capacity('mcp_call_count', len(record['started']) + 1, 'gateway_call')
            record['started'].add(call_id)
        result = await self.client.call(name, document['arguments'], self.catalog)
        body = encode(result).decode()
        observation = {'kind': 'external_gateway_observation', 'task_id': task_id,
            'parent_attempt_id': record['attempt_id'], 'tool_call_id': call_id, 'tool': name,
            'catalog_revision': self.catalog['revision'], 'tool_schema_sha256': self.catalog['tool_hashes'][name],
            'arguments_sha256': fingerprint(document['arguments']), 'output_sha256': sha256(body.encode()).hexdigest()}
        response = {'result_json': body, 'is_error': result.get('isError') is True, 'observation': observation}
        require_capacity('mcp_frame_bytes', len(encode(response)), 'gateway_envelope')
        with self._lock:
            if self._tasks.get(task_id) is not record:
                raise GatewayError('gateway_task_not_admitted')
            record['issued'][call_id] = deepcopy(response)
        return response

    def verify(self, task_id, call_id, name, observation, result_json):
        with self._lock:
            expected = self._tasks.get(task_id, {}).get('issued', {}).get(call_id)
            receipt = {key: value for key, value in observation.items() if key != 'native_research_source'}
            return bool(expected and expected['observation'] == receipt
                        and observation['tool'] == name and expected['result_json'] == result_json)
