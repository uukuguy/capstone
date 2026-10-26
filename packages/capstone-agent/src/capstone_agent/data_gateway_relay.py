"""Task catalog grants and host-issued gateway observation receipts."""
from copy import deepcopy
from hashlib import sha256
import asyncio
import json
from pathlib import Path
import re
import stat
from threading import RLock

from .application_capacity import limits, require_capacity, CapacityExceeded
from .data_gateway_mcp import GatewayError, TASK_STOP_ERRORS, encode, fingerprint


def load_container_gateway(connection_file, policy_path, *, private_root=Path('/run/capstone-private'), owner_uid=0):
    if not connection_file:
        return None, {'available': False, 'reason': 'not_configured'}
    try:
        # This parent belongs to the image filesystem, outside the host bind.
        # Bind-file mode bits alone do not protect data on every host filesystem.
        parent = private_root.lstat()
        if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != owner_uid
                or stat.S_IMODE(parent.st_mode) != 0o700
                or Path(connection_file) != private_root / 'data-gateway/connection.json'):
            raise GatewayError('gateway_private_mount_invalid')
        from .data_gateway_mcp import DataGatewayMcp
        client = DataGatewayMcp(Path(connection_file), json.loads(Path(policy_path).read_text()))
        resource = DataGatewayAccess(client, asyncio.run(client.prepare()))
        return resource, resource.publication()
    except GatewayError as error:
        return None, {'available': False, 'reason': str(error)}
    except CapacityExceeded:
        raise
    except (OSError, ValueError):
        return None, {'available': False, 'reason': 'gateway_private_mount_invalid'}


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
            if record.get('failure'):
                raise GatewayError(record['failure'])
            require_capacity('mcp_call_count', len(record['started']) + 1, 'gateway_call')
            record['started'].add(call_id)
        arguments = deepcopy(document['arguments'])
        try:
            result = await self.client.call(name, deepcopy(arguments), self.catalog)
        except GatewayError as error:
            if str(error) in TASK_STOP_ERRORS:
                with self._lock:
                    if self._tasks.get(task_id) is record:
                        record['failure'] = str(error)
            raise
        body = encode(result).decode()
        observation = {'kind': 'external_gateway_observation', 'task_id': task_id,
            'parent_attempt_id': record['attempt_id'], 'tool_call_id': call_id, 'tool': name,
            'catalog_revision': self.catalog['revision'], 'tool_schema_sha256': self.catalog['tool_hashes'][name],
            'arguments_sha256': fingerprint(arguments), 'output_sha256': sha256(body.encode()).hexdigest()}
        response = {'result_json': body, 'is_error': result.get('isError') is True, 'observation': observation}
        require_capacity('mcp_frame_bytes', len(encode(response)), 'gateway_envelope')
        with self._lock:
            if self._tasks.get(task_id) is not record:
                raise GatewayError('gateway_task_not_admitted')
            record['issued'][call_id] = {'response': deepcopy(response), 'arguments': arguments}
        return response

    def verify(self, task_id, call_id, name, observation, result_json):
        with self._lock:
            issued = self._tasks.get(task_id, {}).get('issued', {}).get(call_id)
            expected = issued['response'] if issued else None
            receipt = {key: value for key, value in observation.items() if key != 'native_research_source'}
            return bool(expected and expected['observation'] == receipt
                        and observation['tool'] == name and expected['result_json'] == result_json)

    def verified_arguments(self, task_id, call_id, name, observation, result_json):
        """Read private original arguments only for this host's exact receipt."""
        with self._lock:
            if not self.verify(task_id, call_id, name, observation, result_json):
                raise GatewayError('gateway_observation_not_issued')
            return deepcopy(self._tasks[task_id]['issued'][call_id]['arguments'])
