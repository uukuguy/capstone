"""Task catalog grants and host-issued gateway observation receipts."""
from copy import deepcopy
from collections import OrderedDict
from hashlib import sha256
import asyncio
import json
from pathlib import Path
import re
import stat
import time
from uuid import uuid4
from threading import RLock
from concurrent.futures import Future
from datetime import datetime, timezone

from .application_capacity import limits, require_capacity, CapacityExceeded
from .data_gateway_mcp import GatewayError, TASK_STOP_ERRORS, encode, fingerprint


def load_container_gateway(connection_file, policy_path, *, private_root=Path('/run/capstone-private'), owner_uid=0):
    if not connection_file:
        return None, {'available': False, 'reason': 'not_configured'}
    client = None
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
        return None, {'available': False, 'reason': str(error), **({'identity': client.public_identity()} if client else {})}
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


def gateway_discovery_tools(native_context, publication, *, gateway_available):
    """The SDK and receipt validator share the same task-scoped discovery grant."""
    admitted = research_gateway_tools(native_context, publication).intersection(
        native_context.get('policy', {}).get('allowed_tools', ())) if native_context else set()
    return {'agent_tool_search', 'agent_tool_load'} if gateway_available and admitted else set()


def stage_gateway_contract_context(inputs, context):
    """Stage host-verified metadata under the task's protected input directory."""
    directory = Path(inputs) / 'gateway-contract-context'
    directory.mkdir(mode=0o700)
    sections = []
    for entry in context['sections']:
        body = encode(entry)
        digest = sha256(body).hexdigest()
        path = directory / (digest + '.json')
        path.write_bytes(body)
        path.chmod(0o440)
        sections.append({key: entry[key] for key in ('tool', 'section', 'contract_revision')} |
                        {'path': str(path), 'sha256': digest, 'size_bytes': len(body)})
    manifest = directory / 'index.json'
    manifest.write_bytes(encode({'catalog_revision': context['catalog_revision'],
                                'instance_id': context['instance_id'], 'sections': sections}))
    manifest.chmod(0o440)
    return manifest


class DataGatewayAccess:
    def __init__(self, client, catalog, *, contract_context_bytes=None):
        self.client, self.catalog = client, deepcopy(catalog)
        from .data_gateway_views import GatewayViewBindings
        self.view_bindings = GatewayViewBindings()
        self._tasks = {}
        self._lock = RLock()
        self._catalogs = ({self.catalog['revision']: deepcopy(self.catalog)} if 'revision' in self.catalog else {})
        self.contract_error = None
        self.contract_request_id = None
        self.contract_checked_at = datetime.now(timezone.utc).isoformat()
        self._contract_context_limit = limits.history_context_bytes if contract_context_bytes is None else contract_context_bytes
        if type(self._contract_context_limit) is not int or self._contract_context_limit <= 0:
            raise ValueError('Invalid contract context capacity')
        self._contract_sections = OrderedDict()
        self._contract_section_bytes = 0
        self._conflicting_contract_tools = set()

    async def reload_contract(self):
        """Refresh future grants; existing task receipts keep their catalog."""
        try:
            refresh = getattr(self.client, 'refresh_catalog', None)
            catalog = await refresh(self.catalog) if refresh else await self.client.prepare()
            with self._lock:
                if catalog['revision'] != self.catalog.get('revision'):
                    self._contract_sections.clear()
                    self._contract_section_bytes = 0
                    self._conflicting_contract_tools.clear()
                self.catalog = deepcopy(catalog)
                self._catalogs[catalog['revision']] = deepcopy(catalog)
                self.contract_error = None
                self.contract_request_id = None
                self.contract_checked_at = datetime.now(timezone.utc).isoformat()
        except BaseException as error:
            with self._lock:
                self.contract_error = (str(error) if isinstance(error, GatewayError)
                    else 'gateway_timeout' if isinstance(error, asyncio.CancelledError) else 'gateway_connection_failed')
                self.contract_request_id = getattr(error, 'request_id', None)
                self.contract_checked_at = datetime.now(timezone.utc).isoformat()
            raise
        return self.publication()

    def publication(self):
        from .data_gateway_mcp import identity_text, checked_instance_identity
        with self._lock:
            catalog, error = deepcopy(self.catalog), self.contract_error
        identity = self.client.public_identity() if hasattr(self.client, 'public_identity') else {}
        server = catalog.get('server_info', {})
        identity.update({target: server[source] for source, target in (('name', 'server_name'), ('version', 'server_version')) if identity_text(server.get(source))})
        instance = checked_instance_identity(catalog.get('instance'))
        if instance is not None:
            identity.update({key: instance[key] for key in ('instance_id', 'instance_name', 'offline')})
            identity.update(environment_label=instance['environment']['label'], data_source_label=instance['data_source']['label'])
        return ({'available': False, 'reason': error, 'identity': identity,
                 **({'request_id': self.contract_request_id} if self.contract_request_id else {})} if error else
                {'available': True, 'catalog': catalog, 'identity': identity})

    def bind(self, task_id, attempt_id, allowed_tools, *, diagnostics=None, catalog=None):
        from .gateway_diagnostics import checked_diagnostics
        context = checked_diagnostics(diagnostics)
        with self._lock:
            if self.contract_error:
                raise GatewayError(self.contract_error)
            catalog = self.catalog if catalog is None else catalog
            if (self._catalogs.get(catalog.get('revision')) != catalog
                    or not isinstance(allowed_tools, (set, frozenset, list, tuple))
                    or any(not isinstance(name, str) or name not in catalog['tools'] for name in allowed_tools)):
                raise GatewayError('gateway_tool_not_admitted')
            if task_id in self._tasks:
                raise GatewayError('gateway_task_already_bound')
            self._tasks[task_id] = {'attempt_id': attempt_id, 'catalog': deepcopy(catalog), 'allowed_tools': frozenset(allowed_tools),
                                    'started': set(), 'issued': {}, 'diagnostics': context, 'diagnostic_calls': []}

    def frozen_catalog(self, revision):
        with self._lock:
            catalog = self._catalogs.get(revision)
            if catalog is None:
                raise GatewayError('gateway_publication_changed')
            return deepcopy(catalog)

    def contract_context(self, task_id):
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                raise GatewayError('gateway_task_not_admitted')
            catalog = record['catalog']
            allowed = record['allowed_tools']
            sections = ([] if catalog['revision'] != self.catalog.get('revision') or self.contract_error else
                        [entry for entry, _ in self._contract_sections.values()
                         if entry['tool'] in allowed and entry['lookup_tool'] in allowed])
            return {'catalog_revision': catalog['revision'],
                    'instance_id': catalog.get('instance', {}).get('instance_id'), 'sections': deepcopy(sections)}

    def _remember_contract_context(self, entry):
        if entry is None or entry['catalog_revision'] != self.catalog.get('revision'):
            return
        tool = entry['tool']
        if tool in self._conflicting_contract_tools:
            return
        if any(old['tool'] == tool and old['contract_revision'] != entry['contract_revision']
               for old, _ in self._contract_sections.values()):
            self._conflicting_contract_tools.add(tool)
            for key in list(self._contract_sections):
                old, size = self._contract_sections[key]
                if old['tool'] == tool:
                    del self._contract_sections[key]
                    self._contract_section_bytes -= size
            return
        size = len(encode(entry))
        if size > self._contract_context_limit:
            return
        key = (tool, entry['section'])
        previous = self._contract_sections.pop(key, None)
        if previous is not None:
            self._contract_section_bytes -= previous[1]
        while self._contract_section_bytes + size > self._contract_context_limit:
            _, (_, removed) = self._contract_sections.popitem(last=False)
            self._contract_section_bytes -= removed
        self._contract_sections[key] = (deepcopy(entry), size)
        self._contract_section_bytes += size

    def revoke(self, task_id):
        with self._lock:
            self._tasks.pop(task_id, None)

    async def resolve_contracts(self, task_id, names):
        """Read exact metadata only for this frozen task's granted selections."""
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                raise GatewayError('gateway_task_not_admitted')
            if record.get('failure'):
                raise GatewayError(record['failure'])
            if (not isinstance(names, list) or not names or len(names) > limits.tool_active_count
                    or any(not isinstance(name, str) or name not in record['allowed_tools'] for name in names)):
                raise GatewayError('gateway_tool_not_admitted')
            catalog = record['catalog']
        tools = await self.client.exact_contracts(names, catalog)
        with self._lock:
            if self._tasks.get(task_id) is not record:
                raise GatewayError('gateway_task_not_admitted')
            record.setdefault('exact_tools', {}).update(deepcopy(tools))
        return {'catalog_revision': catalog['revision'], 'tools': tools,
                'tool_hashes': {name: catalog['tool_hashes'][name] for name in names}, 'executed': False}

    def validate_batch(self, task_id, calls):
        """Check the frozen task contract without connecting or consuming call IDs."""
        from .data_gateway_mcp import validate, argument_validation_details
        from jsonschema.exceptions import ValidationError
        if not isinstance(calls, list) or not calls:
            raise GatewayError('gateway_request_invalid')
        require_capacity('rpc_batch_requests', len(calls), 'gateway_batch_preflight')
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                raise GatewayError('gateway_task_not_admitted')
            if record.get('failure'):
                raise GatewayError(record['failure'])
            catalog, allowed = record['catalog'], record['allowed_tools']
            errors = []
            for index, item in enumerate(calls):
                if (not isinstance(item, dict) or set(item) != {'name', 'arguments'}
                        or not isinstance(item['name'], str) or not isinstance(item['arguments'], dict)):
                    errors.append({'index': index, 'code': 'gateway_request_invalid'})
                    continue
                name = item['name']
                if name not in allowed or name not in catalog['tools']:
                    errors.append({'index': index, 'code': 'gateway_tool_not_admitted'})
                    continue
                try:
                    exact = record.get('exact_tools', {}).get(name, catalog['tools'][name])
                    validate(exact['inputSchema'], item['arguments'])
                except ValidationError as error:
                    errors.append({'index': index, 'code': 'gateway_arguments_invalid',
                                   'validation_errors': argument_validation_details(error)})
                except Exception:
                    errors.append({'index': index, 'code': 'gateway_catalog_invalid'})
            return {'schema': 'capstone-gateway-preflight/1', 'catalog_revision': catalog['revision'],
                    'valid': not errors, 'errors': errors, 'executed': False}

    async def call(self, task_id, document, *, diagnostics=None, retry_of=None):
        """One task-local reuse boundary for direct and composed readonly calls."""
        if not isinstance(document, dict):
            raise GatewayError('gateway_request_invalid')
        policy = document.get('observation_policy')
        if policy is not None and (not isinstance(policy, dict) or set(policy) != {'refresh_reason'}
                or not isinstance(policy['refresh_reason'], str) or not policy['refresh_reason'].strip()
                or len(policy['refresh_reason']) > 512):
            raise GatewayError('gateway_request_invalid')
        base = {k: v for k, v in document.items() if k != 'observation_policy'}
        with self._lock:
            record = self._tasks.get(task_id)
            tool = record['catalog']['tools'].get(base.get('name'), {}) if record and isinstance(base.get('name'), str) else {}
            hints = tool.get('annotations') or {}
            reusable = (hints.get('readOnlyHint') is True and hints.get('idempotentHint') is True
                        and hints.get('destructiveHint') is not True)
            # Operation polling is live even when directly invoked. These are
            # adapter-owned protocol references, not business tool names.
            if isinstance(base.get('arguments'), dict) and any(k in base['arguments'] for k in ('job_ref', 'preparation_ref')):
                reusable = False
        if not reusable:
            return await self._call(task_id, base, diagnostics=diagnostics, retry_of=retry_of)
        key = fingerprint({'name': base.get('name'), 'arguments': base.get('arguments')})
        if record is None:
            raise GatewayError('gateway_task_not_admitted')
        while True:
            with self._lock:
                if self._tasks.get(task_id) is not record:
                    raise GatewayError('gateway_task_not_admitted')
                pending = record.setdefault('read_pending', {})
                previous = pending.get(key)
                if previous is None:
                    pending[key] = owned = Future()
                    break
            await asyncio.shield(asyncio.wrap_future(previous))
        try:
            with self._lock:
                saved = record.setdefault('read_observations', {})
                cached = None if policy else saved.get(key)
                if policy:
                    saved.pop(key, None)
            response = await self._call(task_id, base, diagnostics=diagnostics, retry_of=retry_of,
                                        reused=cached, refresh_reason=policy['refresh_reason'] if policy else None)
            payload = json.loads(response['result_json'])
            structured = payload.get('structuredContent')
            if payload.get('isError') is not True and isinstance(structured, dict) and structured.get('status') == 'ok':
                with self._lock:
                    if self._tasks.get(task_id) is record:
                        saved[key] = deepcopy(response)
            return response
        finally:
            with self._lock:
                pending.pop(key, None)
                owned.set_result(None)

    async def _call(self, task_id, document, *, diagnostics=None, retry_of=None, reused=None, refresh_reason=None):
        from .gateway_diagnostics import checked_diagnostics, diagnostic_id, response_diagnostics
        override = checked_diagnostics(diagnostics)
        if retry_of is not None:
            diagnostic_id(retry_of)
        if (not isinstance(document, dict) or set(document) != {'call_id', 'name', 'arguments'}
                or not isinstance(document.get('call_id'), str)
                or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,256}', document['call_id'])
                or not isinstance(document.get('name'), str)
                or not isinstance(document['arguments'], dict)):
            raise GatewayError('gateway_request_invalid')
        call_id, name = document['call_id'], document['name']
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                raise GatewayError('gateway_task_not_admitted')
            catalog = record['catalog']
            if name not in catalog['tools']:
                raise GatewayError('gateway_request_invalid')
            exact = record.get('exact_tools', {}).get(name, catalog['tools'][name])
            if 'progressive' in catalog and 'inputSchema' not in exact:
                raise GatewayError('gateway_contract_not_loaded')
            properties = exact.get('inputSchema', {}).get('properties', {})
            consumes_job = 'job_ref' in properties or 'job_ref' in document['arguments']
            if name not in record['allowed_tools']:
                raise GatewayError('gateway_tool_not_admitted')
            context = override if override is not None else record['diagnostics']
            if override is not None and (record['diagnostics'] is None or any(
                    override[key] != record['diagnostics'][key] for key in ('task_id', 'run_id', 'trace_id'))):
                raise ValueError('gateway_diagnostics_binding_changed')
            if call_id in record['started']:
                raise GatewayError('gateway_call_already_started')
            if record.get('failure'):
                raise GatewayError(record['failure'])
            operation_key = fingerprint({'name': name, 'arguments': document['arguments']})
            if operation_key in record.get('blocked_requests', {}):
                raise GatewayError('gateway_operation_retry_blocked', record['blocked_requests'][operation_key])
            if consumes_job:
                job_ref = document['arguments'].get('job_ref')
                if ('job_ref' not in properties or not isinstance(job_ref, str)
                        or job_ref not in record.get('operation_refs', set())):
                    raise GatewayError('gateway_tool_not_admitted')
            require_capacity('mcp_call_count', len(record['started']) + 1, 'gateway_call')
            record['started'].add(call_id)
            span = {**(context or {}), 'span_id': uuid4().hex, 'tool_call_id': call_id,
                    'status': 'sending', **({'retry_of': retry_of} if retry_of is not None else {})}
            record['diagnostic_calls'].append(span)
        arguments = deepcopy(document['arguments'])
        started = time.monotonic()
        try:
            if reused is not None:
                result = json.loads(reused['result_json'])
            else:
                result = await self.client.call(name, deepcopy(arguments), catalog,
                    **({'diagnostics': context} if context is not None else {}))
            with self._lock:
                span.update(response_diagnostics(result))
                body = result.get('structuredContent', {})
                failed = result.get('isError') is True or isinstance(body, dict) and body.get('status') in {'error', 'failed', 'denied'}
                span['status'] = 'reused' if reused else 'business_error' if failed else 'received'
                if reused:
                    span['reused_from'] = reused['observation'].get('reused_from', reused['observation']['tool_call_id'])
        except asyncio.CancelledError:
            with self._lock:
                span['status'] = 'cancelled'
            raise
        except GatewayError as error:
            with self._lock:
                span.update(status='adapter_error', failure_phase='gateway_client')
            if str(error) in TASK_STOP_ERRORS:
                with self._lock:
                    if self._tasks.get(task_id) is record:
                        record['failure'] = str(error)
            raise
        except Exception:
            with self._lock:
                span['status'] = 'transport_error'
            raise
        finally:
            with self._lock:
                span['duration_ms'] = (time.monotonic() - started) * 1000
        content = result.get('structuredContent', {})
        data = content.get('data', {}) if isinstance(content, dict) else {}
        successful = (result.get('isError') is not True and isinstance(content, dict)
                      and content.get('status') in {'ok', 'partial'})
        if (consumes_job and successful
                and (not isinstance(data, dict) or data.get('job_ref') != arguments.get('job_ref'))):
            raise GatewayError('gateway_output_invalid')
        body = encode(result).decode()
        observation = {'kind': 'external_gateway_observation', 'task_id': task_id,
            'parent_attempt_id': record['attempt_id'], 'tool_call_id': call_id, 'tool': name,
            'catalog_revision': catalog['revision'], 'tool_schema_sha256': catalog['tool_hashes'][name],
            'arguments_sha256': fingerprint(arguments), 'output_sha256': sha256(body.encode()).hexdigest(),
            'observed_at': reused['observation']['observed_at'] if reused else datetime.now(timezone.utc).isoformat(),
            **({'reused_from': reused['observation'].get('reused_from', reused['observation']['tool_call_id'])} if reused else {}),
            **({'refresh_reason': refresh_reason} if refresh_reason else {})}
        response = {'result_json': body, 'is_error': failed, 'observation': observation}
        require_capacity('mcp_frame_bytes', len(encode(response)), 'gateway_envelope')
        binding_catalog = catalog
        if 'progressive' in catalog:
            # Only declared response continuations justify loading another
            # contract here. Never load schemas for arbitrary business rows.
            targets = set()
            for action in self.view_bindings.candidate_actions(result):
                candidates = [n for n, tool in catalog['tools'].items()
                              if action['tool'] in (n, tool['name']) and n in record['allowed_tools']]
                if len(candidates) == 1:
                    targets.add(candidates[0])
            missing = sorted(targets - record.get('exact_tools', {}).keys())
            for start in range(0, len(missing), limits.tool_active_count):
                try:
                    await self.resolve_contracts(task_id, missing[start:start + limits.tool_active_count])
                except GatewayError as error:
                    # A metadata failure must not erase an already returned
                    # source result. Unresolved continuations remain unbound.
                    span['continuation_contract_error'] = str(error)
                    break
            binding_catalog = {**catalog, 'tools': {**catalog['tools'], **record.get('exact_tools', {})}}
        self.view_bindings.observe(name, arguments, result, binding_catalog)
        classify_contract = getattr(self.client, 'contract_context_entry', None)
        contract_entry = classify_contract(name, arguments, result, catalog) if classify_contract else None
        with self._lock:
            if self._tasks.get(task_id) is not record:
                raise GatewayError('gateway_task_not_admitted')
            record['issued'][call_id] = {'response': deepcopy(response), 'arguments': arguments}
            self._remember_contract_context(contract_entry)
            if failed:
                from .native_tool_diagnostics import tool_execution_diagnostics
                diagnostic = tool_execution_diagnostics(result)
                if diagnostic is not None and (diagnostic.get('automatic_retry') is False or
                        diagnostic.get('result_state') == 'unknown' and (
                            diagnostic.get('request_sent') is True or diagnostic.get('remote_execution_possible') is True)):
                    provenance = content.get('provenance', {}) if isinstance(content, dict) else {}
                    record.setdefault('blocked_requests', {})[operation_key] = (
                        provenance.get('request_id') if isinstance(provenance, dict) else None)
            if successful and isinstance(data, dict):
                # Only explicit operation references at the result's data root
                # grant access. Business rows and nested objects never do.
                for field in ('job_ref', 'preparation_ref'):
                    ref = data.get(field)
                    if isinstance(ref, str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,512}', ref):
                        record.setdefault('operation_refs', set()).add(ref)
        return response

    def diagnostic_calls(self, task_id):
        """Host reads before revoke; durable event persistence is the host's job."""
        with self._lock:
            return deepcopy(self._tasks.get(task_id, {}).get('diagnostic_calls', []))

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
