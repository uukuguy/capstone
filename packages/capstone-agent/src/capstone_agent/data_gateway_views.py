"""Connection-local bindings from admitted gateway observations.

Tool identities come only from returned actions. This cache does not discover
tools or select the first business operation for the model.
"""
from collections import OrderedDict
from copy import deepcopy
import json
import threading
import time
from datetime import datetime
from jsonschema.exceptions import ValidationError
from .data_gateway_mcp import validate as validate_gateway_schema


def view_references(manifest, data, arguments, properties, catalog, parent_identity):
    """Admit the electrical-view protocol's declared outputs and read actions."""
    from .structural_context import VIEW_IDENTITY_FIELDS

    if manifest is not None:
        return {manifest['view_ref']: {key: manifest[key] for key in VIEW_IDENTITY_FIELDS}}
    if (data.get('task_type') == 'view_preparation' and data.get('state') == 'succeeded'
            and isinstance(arguments.get('job_ref'), str)):
        identity = {key: data.get(key) for key in ('model_ref', 'model_revision')}
        ref = data.get('view_ref')
        if not isinstance(ref, str) or not ref:
            return {}
        actions = [data.get('next_action')]
    elif parent_identity and 'objects' in properties and 'expected_model_revision' in properties:
        identity = parent_identity
        ref = None
        actions = []
        results = data.get('results')
        for item in results if isinstance(results, list) else ():
            matches = item.get('matches') if isinstance(item, dict) else None
            for match in matches if isinstance(matches, list) else ():
                if not isinstance(match, dict):
                    continue
                action = match.get('read_action')
                supplied = action.get('arguments') if isinstance(action, dict) else None
                if isinstance(supplied, dict) and supplied.get('view_ref') == match.get('local_view_ref'):
                    actions.append(action)
    elif parent_identity:
        identity = {**parent_identity, **{key: data[key] for key in VIEW_IDENTITY_FIELDS
                                         if isinstance(data.get(key), str) and 0 < len(data[key]) <= 512}}
        return {arguments['view_ref']: identity}
    else:
        return {}
    if any(not isinstance(value, str) or not 0 < len(value) <= 512 for value in identity.values()):
        return {}
    references = {arguments['view_ref']: identity} if ref is None else {}
    for action in actions:
        if not isinstance(action, dict) or not isinstance(action.get('tool'), str):
            continue
        name = action['tool']
        if name not in catalog['tools']:
            name = 'data_gateway_' + name
        supplied = action.get('arguments')
        if (name not in catalog['tools'] or not isinstance(supplied, dict)
                or not isinstance(supplied.get('view_ref'), str)
                or not isinstance(supplied.get('stream'), str) or ref is not None and supplied['view_ref'] != ref):
            continue
        schema = catalog['tools'][name].get('inputSchema')
        if schema is not None:
            if not {'view_ref', 'stream'} <= schema.get('properties', {}).keys():
                continue
            try:
                validate_gateway_schema(schema, supplied)
            except (ValueError, ValidationError):
                continue
        elif 'progressive' not in catalog or set(supplied) - {'view_ref', 'stream', 'limit'}:
            # A later consumer must still load its own exact read contract.
            continue
        references[supplied['view_ref']] = identity
    return references


class GatewayViewBindings:
    def __init__(self):
        self._discovery = None
        self._actions = OrderedDict()
        self._lock = threading.RLock()
        self._revision = None
        self._manifests = OrderedDict()

    @staticmethod
    def _key(arguments):
        return json.dumps(arguments, sort_keys=True, allow_nan=False)

    def discovery(self):
        with self._lock:
            return deepcopy(self._discovery)

    def action(self, arguments):
        with self._lock:
            actions = self._actions.get(self._key(arguments), [])
            return deepcopy(actions[0]) if len(actions) == 1 else None

    def view_action(self, arguments, *, read):
        """Match presentation hints while retaining the exact published call."""
        optional = {'limit'} if read else {'representation', 'view_schema'}
        with self._lock:
            candidates = []
            for bucket in self._actions.values():
                for action in bucket:
                    supplied = action['arguments']
                    # Only the public view contract can use these hints.
                    identity = {'view_ref', 'stream'} if read else {'model_ref'}
                    if not identity <= supplied.keys():
                        continue
                    filtered = {key: value for key, value in arguments.items()
                                if key not in optional or key in supplied}
                    if supplied == filtered and action not in candidates:
                        candidates.append(action)
            return deepcopy(candidates[0]) if len(candidates) == 1 else None

    def restore(self, request):
        """Return one frozen observation only for a fully pinned identity."""
        if not request.get('expected_model_revision') or not request.get('selection_ref') or request.get('refresh_source'):
            return None
        fields = {'expected_model_revision': 'model_revision', 'view_schema': 'schema'}
        with self._lock:
            candidates = []
            for value, opened in self._manifests.values():
                expires = value.get('expires_at')
                if expires is not None:
                    try:
                        expiry = float(expires) if isinstance(expires, (int, float)) else datetime.fromisoformat(expires.replace('Z', '+00:00')).timestamp()
                        if expiry <= time.time():
                            continue
                    except (ValueError, TypeError):
                        continue
                effective = {**opened, **value}
                selection = value.get('overview_coverage', {}).get('source_selection', {})
                for key, source_field in (('selection_profile', 'profile'), ('boundary_policy', 'boundary_policy')):
                    if selection.get(source_field) is not None:
                        effective[key] = selection[source_field]
                if any(effective.get(fields.get(key, key)) != item for key, item in request.items()):
                    continue
                if value.get('target') is not None and request.get('target') != value['target']:
                    continue
                candidates.append(value)
            return deepcopy(candidates[0]) if len(candidates) == 1 else None

    @staticmethod
    def candidate_actions(response):
        """Declared continuations only; arbitrary business rows grant nothing."""
        content = response.get('structuredContent', {})
        if response.get('isError') or content.get('status') not in {'ok', 'partial'}:
            return []
        data = content.get('data')
        if not isinstance(data, dict) or data.get('state') == 'failed':
            return []
        actions = []
        action = data.get('next_action')
        if isinstance(action, dict):
            actions.append(action)
        guidance = content.get('provenance', {}).get('agent_guidance', {})
        following = guidance.get('next_actions', []) if isinstance(guidance, dict) else []
        if isinstance(following, list):
            actions.extend(following)
        streams = data.get('streams', {})
        if data.get('state') == 'ready' and isinstance(streams, dict):
            actions.extend(entry.get('read') for entry in streams.values() if isinstance(entry, dict))
        capabilities = data.get('electrical_views')
        if isinstance(capabilities, dict) and isinstance(data.get('scopes'), list):
            models = capabilities.get('source_grid_models', [])
            if isinstance(models, list):
                actions.extend({'tool': capabilities.get('open_tool'), 'arguments': model['open_arguments']}
                               for model in models if isinstance(model, dict) and isinstance(model.get('open_arguments'), dict))
        return [action for action in actions if isinstance(action, dict)
                and isinstance(action.get('tool'), str) and isinstance(action.get('arguments'), dict)]

    def observe(self, tool, arguments, response, catalog):
        content = response.get('structuredContent', {})
        if response.get('isError') or content.get('status') not in {'ok', 'partial'}:
            if 'job_ref' in arguments:
                with self._lock:
                    self._actions.pop(self._key(arguments), None)
            return None
        data = content.get('data')
        if not isinstance(data, dict):
            return None
        actions = self.candidate_actions(response)
        manifest = None
        with self._lock:
            revision = catalog.get('revision')
            if revision != self._revision:
                self._actions.clear()
                self._discovery = None
                self._manifests.clear()
                self._revision = revision
            if data.get('state') == 'ready' and data.get('schema') in {'gateway-electrical-view/1', 'gateway-electrical-view/2'}:
                # Import here to keep the provider and observation cache free
                # of a module initialization cycle.
                from .grid_electrical_view import checked_manifest, ElectricalViewError
                try:
                    manifest = checked_manifest(data)
                except ElectricalViewError:
                    pass
                else:
                    self._manifests[manifest['view_ref']] = (manifest, deepcopy(arguments))
                    self._manifests.move_to_end(manifest['view_ref'])
                    while len(self._manifests) > 128:
                        self._manifests.popitem(last=False)
            # A completed inspection cannot leave an old poll action live.
            if 'job_ref' in arguments:
                self._actions.pop(self._key(arguments), None)
            capabilities = data.get('electrical_views')
            if isinstance(capabilities, dict) and isinstance(data.get('scopes'), list):
                self._discovery = deepcopy(data)
            if data.get('state') == 'failed':
                actions = []
            for action in actions:
                if (not isinstance(action, dict) or not isinstance(action.get('tool'), str)
                        or not action['tool'] or not isinstance(action.get('arguments'), dict)):
                    continue
                name = action['tool']
                if name not in catalog.get('tools', {}):
                    name = 'data_gateway_' + name
                published = catalog.get('tools', {}).get(name, {})
                if (not isinstance(published.get('inputSchema'), dict)
                        or not isinstance(catalog.get('tool_hashes', {}).get(name), str)):
                    continue
                try:
                    validate_gateway_schema(published['inputSchema'], action['arguments'])
                except (ValueError, ValidationError):
                    continue
                # Guidance can mirror a stream or next action with a purpose
                # or timing hint. These describe the same invocation.
                invocation = {'tool': action['tool'], 'arguments': action['arguments']}
                bucket = self._actions.setdefault(self._key(action['arguments']), [])
                # Two distinct actions suffice to reject ambiguity. Retaining
                # further alternatives cannot make that request selectable.
                if invocation not in bucket and len(bucket) < 2:
                    bucket.append(deepcopy(invocation))
            while len(self._actions) > 2048:
                self._actions.popitem(last=False)
        return manifest
