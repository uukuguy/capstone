"""Application-owned private gateway registry and bounded health observations."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
from threading import Event, RLock, Thread
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from .data_gateway_mcp import DataGatewayMcp, GatewayError, checked_instance_identity, identity_text, public_failure
from .data_gateway_relay import DataGatewayAccess


def _url(value):
    try:
        if not isinstance(value, str) or len(value) > 2048 or any(ord(c) <= 32 or ord(c) == 127 for c in value):
            raise ValueError()
        parsed = urlsplit(value)
        if (parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or '?' in value or '#' in value):
            raise ValueError()
        port = parsed.port
        if port is not None and not 0 < port <= 65535:
            raise ValueError()
        host = parsed.hostname.lower()
        host = f'[{host}]' if ':' in host else host
        if port is not None and port != (443 if parsed.scheme == 'https' else 80):
            host += f':{port}'
        return urlunsplit((parsed.scheme, host, parsed.path or '/', '', ''))
    except (ValueError, TypeError):
        raise GatewayError('gateway_connection_input_invalid') from None


class GatewayConnectionRegistry:
    """Synchronous admission API; health refresh runs outside request execution.

    Host callers serialize routing changes against active tasks. Admission methods
    may take up to 15 seconds and belong in the HTTP thread pool.
    """

    def __init__(self, root: Path, policy: dict, *, seeds: list[dict] | None = None,
                 client_factory=None, transport_host: str | None = None):
        self.root = Path(root)
        self.policy = deepcopy(policy)
        self._factory = client_factory or DataGatewayMcp
        self._transport_host = transport_host
        if transport_host is not None and not re.fullmatch(r'[A-Za-z0-9.-]{1,253}', transport_host):
            raise GatewayError('gateway_connection_input_invalid')
        self._lock, self._mutation = RLock(), RLock()
        self._stop = Event()
        self._closed = False
        self._access = None
        self._health = {}
        self._batch = None
        self._periodic = None
        self._paths = set()
        self._client_paths = {}
        self._executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix='gateway-health')
        try:
            if self.root.is_symlink():
                raise ValueError()
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.root.chmod(0o700)
            path = self.root / 'registry.json'
            self._document = {'schema': 'capstone-gateway-registry/1', 'revision': 0, 'entries': []}
            if path.exists():
                if path.is_symlink() or path.stat().st_mode & 0o077 or path.stat().st_size > 1024 * 1024:
                    raise ValueError()
                document = json.loads(path.read_text())
                if (not isinstance(document, dict) or document.get('schema') != self._document['schema']
                        or type(document.get('revision')) is not int or document['revision'] < 0
                        or not isinstance(document.get('entries'), list) or len(document['entries']) > 128):
                    raise ValueError()
                self._document = document
            ids, urls = set(), set()
            for item in self._document['entries']:
                self._check_entry(item)
                if item['id'] in ids or item['connection']['url'] in urls:
                    raise ValueError()
                ids.add(item['id'])
                urls.add(item['connection']['url'])
            if self._document.get('selected_id') is not None and self._document['selected_id'] not in ids:
                raise ValueError()
            for seed in seeds or []:
                item = deepcopy(seed)
                item['connection']['url'] = _url(item['connection']['url'])
                self._check_entry(item)
                if item['id'] not in ids and item['connection']['url'] not in urls:
                    self._document['entries'].append(item)
                    ids.add(item['id'])
                    urls.add(item['connection']['url'])
            if len(ids) > 128:
                raise ValueError()
            self._persist(self._document)
        except Exception:
            self._executor.shutdown(wait=False, cancel_futures=True)
            raise GatewayError('gateway_registry_unavailable') from None

    @staticmethod
    def _check_entry(item):
        if (not isinstance(item, dict) or set(item) != {'id', 'label', 'connection'}
                or not isinstance(item['id'], str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', item['id'])
                or not identity_text(item['label'])):
            raise ValueError()
        config = item['connection']
        if (not isinstance(config, dict) or set(config) - {'name', 'transport', 'url', 'headers'}
                or config.get('transport') != 'streamable-http' or _url(config.get('url')) != config['url']
                or not isinstance(config.get('headers'), dict) or set(config['headers']) != {'Authorization'}
                or ('name' in config and not identity_text(config['name']))):
            raise ValueError()
        auth = config['headers']['Authorization']
        if not isinstance(auth, str) or not auth.startswith('Bearer ') or len(auth) < 15 or any(ord(c) < 32 or ord(c) == 127 for c in auth):
            raise ValueError()

    def _persist(self, document):
        descriptor, name = tempfile.mkstemp(prefix='.registry-', dir=self.root)
        try:
            with os.fdopen(descriptor, 'w') as stream:
                json.dump(document, stream, ensure_ascii=False, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.root / 'registry.json')
            directory = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            Path(name).unlink(missing_ok=True)

    @property
    def current_access(self):
        with self._lock:
            return self._access

    def snapshot(self):
        with self._lock:
            result = {'schema': 'capstone-gateway-connections/1', 'revision': self._document['revision'],
                      'entries': [{'id': item['id'], 'label': item['label'], 'url': item['connection']['url'],
                                   **deepcopy(self._health.get(item['id'], {'status': 'unknown'}))}
                                  for item in self._document['entries']],
                      'checking': any(item.get('status') == 'checking' for item in self._health.values())}
            if self._document.get('selected_id') is not None:
                result['selected_id'] = self._document['selected_id']
            return result

    def _input(self, value):
        if not isinstance(value, dict) or set(value) - {'url', 'token', 'name'}:
            raise GatewayError('gateway_connection_input_invalid')
        url = _url(value.get('url'))
        name = value.get('name')
        if name is not None and not identity_text(name):
            raise GatewayError('gateway_connection_input_invalid')
        token = value.get('token')
        if token is None or token == '':
            with self._lock:
                known = next((item for item in self._document['entries'] if item['connection']['url'] == url), None)
                if known is None:
                    raise GatewayError('gateway_authentication_failed')
                config = deepcopy(known['connection'])
        else:
            if not isinstance(token, str):
                raise GatewayError('gateway_connection_input_invalid')
            token = token.strip()
            token = token[7:].strip() if token.lower().startswith('bearer ') else token
            if len(token) < 8 or len(token) > 8192 or any(ord(c) <= 32 or ord(c) == 127 for c in token):
                raise GatewayError('gateway_connection_input_invalid')
            config = {'transport': 'streamable-http', 'url': url, 'headers': {'Authorization': 'Bearer ' + token}}
        if name is not None:
            config['name'] = name
        return config

    def _client(self, config):
        config = deepcopy(config)
        address = urlsplit(config['url'])
        if self._transport_host and address.hostname in {'localhost', '127.0.0.1', '::1'}:
            config['url'] = urlunsplit((address.scheme, self._transport_host + (f':{address.port}' if address.port else ''), address.path, '', ''))
        descriptor, name = tempfile.mkstemp(prefix='.connection-', suffix='.json', dir=self.root)
        path = Path(name)
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(config, stream)
        with self._lock:
            self._paths.add(path)
        try:
            client = self._factory(path, self.policy)
            with self._lock:
                self._client_paths[id(client)] = path
            return client
        except Exception:
            self._release(path)
            raise

    def _release(self, path):
        path.unlink(missing_ok=True)
        with self._lock:
            self._paths.discard(path)

    def _release_client(self, client):
        with self._lock:
            path = self._client_paths.pop(id(client), None)
        if path is not None:
            self._release(path)

    def _prepare(self, config):
        client = None
        try:
            client = self._client(config)
            async def prepare():
                return await asyncio.wait_for(client.prepare(), 15)
            return DataGatewayAccess(client, asyncio.run(prepare()))
        except Exception as error:
            if client is not None:
                self._release_client(client)
            raise GatewayError(public_failure(error, 'gateway_connection_failed')) from None

    def probe(self, value):
        with self._mutation:
            self._ensure_open()
            config = self._input(value)
            access = self._prepare(config)
            try:
                return {'url': config['url'], 'identity': {**access.publication()['identity'], 'available': True}, 'available': True}
            finally:
                self._release_client(access.client)

    def add(self, value):
        with self._mutation:
            self._ensure_open()
            config = self._input(value)
            with self._lock:
                if any(item['connection']['url'] == config['url'] for item in self._document['entries']):
                    raise GatewayError('gateway_connection_duplicate')
                if len(self._document['entries']) >= 128:
                    raise GatewayError('gateway_registry_full')
            access = self._prepare(config)
            try:
                identity = access.publication()['identity']
                instance_id = identity.get('instance_id')
                with self._lock:
                    known = [state.get('identity', {}) for state in self._health.values()]
                    if self._access is not None:
                        known.append(self._access.publication()['identity'])
                    if identity_text(instance_id) and any(previous.get('instance_id') == instance_id for previous in known):
                        raise GatewayError('gateway_connection_duplicate')
                item = {'id': 'gateway-' + uuid4().hex, 'label': config.get('name', config['url'][:256]), 'connection': config}
                self._commit(lambda doc: doc['entries'].append(item))
                with self._lock:
                    self._health[item['id']] = self._connected(identity)
                return self.snapshot()
            finally:
                self._release_client(access.client)

    def _commit(self, change):
        with self._lock:
            document = deepcopy(self._document)
            change(document)
            document['revision'] += 1
            try:
                self._persist(document)
            except Exception:
                raise GatewayError('gateway_registry_unavailable') from None
            self._document = document

    def select(self, identifier):
        with self._mutation:
            self._ensure_open()
            with self._lock:
                item = next((item for item in self._document['entries'] if item['id'] == identifier), None)
                if item is None:
                    raise GatewayError('gateway_connection_not_found')
                config = deepcopy(item['connection'])
            access = self._prepare(config)
            try:
                with self._lock:
                    self._commit(lambda doc: doc.update(selected_id=identifier))
                    self._access = access
                    self._health[identifier] = self._connected(access.publication()['identity'])
            except Exception:
                self._release_client(access.client)
                raise
            return self.snapshot()

    def prepare_selected(self):
        with self._lock:
            selected = self._document.get('selected_id')
        return self.select(selected) if selected is not None else self.snapshot()

    @staticmethod
    def _connected(identity):
        return {'status': 'connected', 'checked_at': datetime.now(timezone.utc).isoformat(),
                'identity': {**identity, 'available': True}}

    def _check(self, item):
        with self._lock:
            if self._closed:
                self._health[item['id']] = {'status': 'unknown'}
                return
        client = None
        try:
            client = self._client(item['connection'])
            async def initialize():
                async with client.connect() as session:
                    catalog = {'server_info': getattr(session, 'server_info', {}) or {}}
                    instance = checked_instance_identity(getattr(session, 'instance_identity', None))
                    if instance is not None:
                        catalog['instance'] = instance
                    return DataGatewayAccess(client, catalog).publication()['identity']
            state = self._connected(asyncio.run(asyncio.wait_for(initialize(), 15)))
        except Exception as error:
            state = {'status': 'disconnected', 'checked_at': datetime.now(timezone.utc).isoformat(),
                     'error': public_failure(error, 'gateway_connection_failed')}
        finally:
            if client is not None:
                self._release_client(client)
        with self._lock:
            self._health[item['id']] = state

    def _ensure_open(self):
        if self._closed:
            raise GatewayError('gateway_registry_closed')

    def refresh(self):
        with self._lock:
            self._ensure_open()
            if self._batch is not None and self._batch.is_alive():
                return self.snapshot()
            entries = deepcopy(self._document['entries'])
            for item in entries:
                self._health[item['id']] = {**self._health.get(item['id'], {}), 'status': 'checking'}
            def batch():
                futures = [self._executor.submit(self._check, item) for item in entries]
                for future in futures:
                    future.result()
            self._batch = Thread(target=batch, name='gateway-refresh', daemon=True)
            self._batch.start()
            return self.snapshot()

    def start(self):
        with self._lock:
            self._ensure_open()
            if self._periodic is not None:
                return
            def periodic():
                while not self._stop.is_set():
                    try:
                        self.refresh()
                    except GatewayError:
                        return
                    self._stop.wait(30)
            self._periodic = Thread(target=periodic, name='gateway-periodic', daemon=True)
            self._periodic.start()

    def close(self):
        with self._mutation:
            with self._lock:
                self._closed = True
                self._stop.set()
                periodic, batch = self._periodic, self._batch
            if periodic is not None:
                periodic.join()
            if batch is not None:
                batch.join()
            self._executor.shutdown(wait=True)
            for path in tuple(self._paths):
                self._release(path)
